"""TASK04 synthetic tests plus small versioned-artifact integrity checks."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fuzzy_network_risk.calibration import fit_config
from fuzzy_network_risk.data import INPUTS
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.optimization import CANDIDATES, candidate_config, context_rules, select_model
from fuzzy_network_risk.refinement import check_lineage, roles
from fuzzy_network_risk.webapp.api import create_app

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / 'config/fuzzy/task04'


@pytest.fixture
def training():
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(rng.integers(1, 100, (50, 5)), columns=INPUTS)
    frame['signature'] = [str(i // 2) for i in range(50)]
    frame[' Label'] = 'BENIGN'
    return frame


@pytest.mark.parametrize('name', CANDIDATES)
def test_candidates_roundtrip_deterministic_and_label_independent(training, name, tmp_path):
    frozen = fit_config(training[INPUTS], 'synthetic')
    config = candidate_config(training, name, frozen)
    changed = training.copy()
    changed[' Label'] = 'ATTACK'
    assert config == candidate_config(changed, name, frozen)
    engine = MamdaniRiskEngine(config)
    engine.save(tmp_path / 'model.json')
    restored = MamdaniRiskEngine.load(tmp_path / 'model.json')
    assert restored.model_id == engine.model_id
    batch = engine.predict_batch(training[INPUTS])
    np.testing.assert_array_equal(batch['risk_score'], restored.predict_batch(training[INPUTS])['risk_score'])
    assert np.isfinite(batch['risk_score']).all()
    assert ((batch['risk_score'] >= 0) & (batch['risk_score'] <= 100)).all()
    for _, row in training.head(5).iterrows():
        one = engine.predict_one(row[INPUTS].to_dict())
        assert one['risk_score'] == engine.predict_batch(row[INPUTS].to_dict())['risk_score'][0]
        for rule in one['activated_rules']:
            assert 0 < rule['strength'] <= 1 and rule['reason_key'] == 'rules.' + rule['id']


def test_group_reference_is_training_only_and_duplicate_robust(training):
    base = fit_config(training[INPUTS], 'test')
    a = candidate_config(training, 'B_group_membership', base)
    # Equal identical signature rows cannot change its representative when
    # the original signature has identical measurements.
    original = training.copy()
    original.loc[original.signature == '0', INPUTS] = original.loc[0, INPUTS].to_numpy()
    repeated = pd.concat([original, original.iloc[[0] * 100]])
    b = candidate_config(original, 'B_group_membership', base)
    c = candidate_config(repeated, 'B_group_membership', base)
    assert all(b['features'][k]['raw_anchors'] == c['features'][k]['raw_anchors'] for k in b['features'])
    assert a['reference_rows'] == training.signature.nunique()
    assert a['features']['rate']['training_max'] == training[INPUTS[0]].max()


def test_only_declared_rule_changes(training):
    base = fit_config(training[INPUTS], 'test')
    original = deepcopy(base['rules'])
    rules = context_rules(base['rules'])
    assert base['rules'] == original and len(rules) == 22
    assert [a['id'] for a in rules] == [a['id'] for a in original]
    changed = [a['id'] for a, b in zip(rules, original, strict=True) if a != b]
    assert changed == ['R07', 'R10', 'R11', 'R19']
    assert next(r for r in rules if r['id'] == 'R10')['antecedent']['all'][-1] == {'feature': 'volume', 'term': 'many'}


def test_selection_needs_both_baselines_and_uncertainty():
    summary = {n: {'balanced_accuracy': 0.5, 'fpr': 0.05, 'recall': 0.05} for n in CANDIDATES}
    intervals = {
        n: {b: {'paired_balanced_accuracy_difference_95': [0.01, 0.1]} for b in CANDIDATES[:2]} for n in CANDIDATES[2:]
    }
    assert select_model(summary, intervals) == 'A_frozen'
    summary['B_group_membership']['balanced_accuracy'] = 0.6
    assert select_model(summary, intervals) == 'B_group_membership'
    intervals['B_group_membership']['A_frozen']['paired_balanced_accuracy_difference_95'][0] = -0.01
    assert select_model(summary, intervals) == 'A_frozen'


def test_roles_and_exposure_rejection():
    frame = pd.DataFrame(
        {
            'signature': ['a', 'b', 'c'],
            'observation_group_id': [1, 2, 3],
            'source_row_id': [1, 2, 3],
            'bucket': ['0', '1', '2'],
        }
    )
    for fold in range(3):
        a, b, c = roles(frame, fold)
        assert not set(a.signature) & set(b.signature) and not set(a.signature) & set(c.signature)
    assert check_lineage(frame, [9], [9], ['z'])
    for ids, groups, sigs in [([1], [], []), ([], [1], []), ([], [], ['a'])]:
        with pytest.raises(ValueError):
            check_lineage(frame, ids, groups, sigs)


def test_frozen_model_and_policies_remain_byte_identical():
    assert (C / 'selected_v4.json').read_bytes() == (ROOT / 'config/fuzzy/task02b/selected_v2.json').read_bytes()
    assert (C / 'selected_policies.json').read_bytes() == (
        ROOT / 'config/fuzzy/task02b/selected_policies.json'
    ).read_bytes()
    manifest = json.loads((C / 'selected_manifest.json').read_text(encoding='utf-8'))
    assert manifest['candidate'] == 'A_frozen' and not manifest['independent_test']


@pytest.mark.parametrize('name', CANDIDATES)
def test_all_saved_candidates_load_and_reject_invalid(name):
    for fold in range(3):
        engine = MamdaniRiskEngine.load(C / f'{name}_fold{fold}.json')
        for value in [None, np.nan, np.inf, -1]:
            out = engine.predict_one({c: value for c in INPUTS})
            assert out['risk_score'] is None
        out = engine.predict_one({c: 1e308 for c in INPUTS})
        assert 0 <= out['risk_score'] <= 100


def test_web_version_metrics_and_existing_api_contract():
    with TestClient(create_app()) as client:
        service = client.app.state.service
        model = client.get('/api/model').json()
        assert client.get('/api/health').json()['configuration_version'] == model['configuration_version']
        assert model['configuration_version'] == 'task04-v1' and 'TASK 04' in model['model_version']
        evidence = client.get('/api/evaluation').json()
        assert evidence['optimization']['model_id'] == model['model_id']
        assert len(evidence['optimization']['candidates']) == 5
        csv = pd.read_csv(ROOT / 'reports/fuzzy/task04/comparison.csv')
        for row in evidence['optimization']['candidates']:
            actual = csv.loc[(csv.candidate == row['id']) & (csv.policy == 'Balanced')].iloc[0]
            assert np.isclose(row['recall'], actual.recall)
        example = client.get('/api/examples').json()['examples'][0]
        results = [
            client.post('/api/analyze', json={'features': example['features'], 'policy': p}).json()
            for p in service.models
        ]
        assert len({r['risk_score'] for r in results}) == 1
        assert all(r['model_id'] == model['model_id'] for r in results)


def test_web_rejects_policy_file_changed_without_manifest(tmp_path):
    from fuzzy_network_risk.webapp.service import WebService

    destination = tmp_path / 'config/fuzzy/task04'
    destination.mkdir(parents=True)
    for name in ['selected_v4.json', 'selected_policies.json', 'selected_manifest.json']:
        shutil.copyfile(C / name, destination / name)
    with (destination / 'selected_policies.json').open('a') as handle:
        handle.write(' ')
    with pytest.raises(ValueError, match='content hash mismatch'):
        WebService(tmp_path)
