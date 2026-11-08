import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fuzzy_network_risk.data import INPUTS, LABEL
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.policy import PolicyRiskModel
from fuzzy_network_risk.refinement import (
    assignment,
    check_lineage,
    choose_candidate,
    group_weights,
    membership_candidate,
    roles,
    select_policies,
    signature,
)


@pytest.fixture
def frame():
    n = 600
    f = pd.DataFrame(
        {
            INPUTS[0]: np.geomspace(0.1, 1e6, n),
            INPUTS[1]: np.arange(n) % 50 + 1.0,
            INPUTS[2]: np.arange(n) % 1400 + 1.0,
            INPUTS[3]: np.arange(n) % 600.0,
            INPUTS[4]: np.arange(n) % 3.0,
        }
    )
    f[LABEL] = np.where(np.arange(n) % 3, 'BENIGN', 'Attack')
    f['source_row_id'] = np.arange(n)
    f['observation_group_id'] = np.arange(n, dtype='uint64')
    f['signature'] = signature(f[INPUTS].to_numpy())
    f['bucket'] = f.signature.map(assignment)
    return f


def test_lineage_excludes_ids_groups_and_signatures(frame):
    assert check_lineage(frame, [], [], [])
    for ids, groups, sigs in [([0], [], []), ([], [0], []), ([], [], [frame.signature.iloc[0]])]:
        with pytest.raises(ValueError):
            check_lineage(frame, ids, groups, sigs)


def test_signature_projection_and_near_clone():
    a = np.array([[100.0, 10.0, 50.0, 30.0, 1.0]])
    b = a.copy()
    b[:, :4] *= 1.001
    assert signature(a)[0] == signature(b)[0]
    assert signature(a)[0] == signature(a.copy())[0]
    with pytest.raises(ValueError):
        signature([[-1, 1, 1, 1, 1]])
    with pytest.raises(ValueError):
        signature([[1, 1, 1, 1, 1.1]])


def test_group_role_overlap_rejected(frame):
    bad = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    bad.loc[len(bad) - 1, 'bucket'] = 'bad-other-bucket'
    with pytest.raises(ValueError):
        check_lineage(bad, [], [], [])


def test_rotating_roles_are_disjoint_and_complete(frame):
    panel = frame.loc[frame.bucket != 'design']
    assessed = []
    for fold in range(3):
        train, cal, assess = roles(panel, fold)
        assert len(train) + len(cal) + len(assess) == len(panel)
        assert not set(train.signature) & set(cal.signature)
        assert not set(train.signature) & set(assess.signature)
        assert not set(cal.signature) & set(assess.signature)
        assessed.extend(assess.source_row_id)
    assert sorted(assessed) == sorted(panel.source_row_id)


def test_assignment_reproducible_and_seeded(frame):
    assert frame.signature.map(assignment).equals(frame.bucket)
    assert set(frame.bucket) == {'design', '0', '1', '2'}
    assert any(assignment(v) != assignment(v, seed=2) for v in frame.signature)


def test_group_weights(frame):
    duplicated = pd.concat([frame, frame.iloc[:20]], ignore_index=True)
    assert group_weights(duplicated).sum() == pytest.approx(duplicated.signature.nunique())


@pytest.mark.parametrize('candidate', ['A_refit', 'B_membership', 'C_rules'])
def test_training_only_fit_and_serialization(frame, candidate, tmp_path):
    train, cal, _ = roles(frame.loc[frame.bucket != 'design'], 0)
    config = membership_candidate(train, candidate)
    assert config['fit_rows'] == len(train)
    before = json.dumps(config, sort_keys=True)
    cal = cal.copy()
    cal[INPUTS] = 1e200
    cal[LABEL] = 'Changed evaluation truth'
    assert before == json.dumps(membership_candidate(train, candidate), sort_keys=True)
    e = MamdaniRiskEngine(config)
    path = tmp_path / 'candidate.json'
    e.save(path)
    loaded = MamdaniRiskEngine.load(path)
    assert e.model_id == loaded.model_id
    np.testing.assert_array_equal(
        e.predict_batch(train[INPUTS])['risk_score'], loaded.predict_batch(train[INPUTS])['risk_score']
    )
    assert LABEL not in e.columns and len(e.config['rules']) == (18 if candidate == 'C_rules' else 22)


def test_policy_constraints_and_monotonic_thresholds():
    y = [0, 0, 0, 0, 1, 1]
    scores = [10, 20, 30, 40, 35, 90]
    policies, curve = select_policies(y, scores, np.ones(6))
    assert len(curve) > 0
    assert (
        policies['Sensitive']['threshold'] <= policies['Balanced']['threshold'] <= policies['Conservative']['threshold']
    )
    for p in policies.values():
        assert p['calibration_fpr'] <= p['fpr_cap'] + 1e-12


def test_no_informative_policy_is_reported():
    policies, _ = select_policies([0, 1], [50, 50], [1, 1])
    for p in policies.values():
        assert p['threshold'] == 100 and not p['nontrivial_recall_feasible']


def test_policy_identity_and_explicit_alert_override(frame):
    e = MamdaniRiskEngine(membership_candidate(frame, 'A_refit'))
    cfg = {
        'model_id': e.model_id,
        'default_policy': 'Balanced',
        'policies': {'Balanced': {'threshold': 100.0, 'fpr_cap': 0.05}},
    }
    model = PolicyRiskModel(e, cfg)
    r = frame[INPUTS].iloc[0].to_dict()
    raw = e.predict_one(r)
    result = model.predict_one(r)
    assert result['risk_score'] == raw['risk_score'] and result['risk_level'] == raw['risk_level']
    assert result['alert'] is False and result['alert_policy']['threshold'] == 100
    assert result['alert_policy']['target_weighting'] == 'signature_group_weighted'
    bad = deepcopy(cfg)
    bad['model_id'] = 'different'
    with pytest.raises(ValueError):
        PolicyRiskModel(e, bad)


@pytest.mark.parametrize('value', [None, np.nan, np.inf, -np.inf, -1, '12', True])
def test_policy_abstention(frame, value):
    e = MamdaniRiskEngine(membership_candidate(frame, 'A_refit'))
    cfg = {
        'model_id': e.model_id,
        'default_policy': 'Balanced',
        'policies': {'Balanced': {'threshold': 50.0, 'fpr_cap': 0.05}},
    }
    model = PolicyRiskModel(e, cfg)
    record = frame[INPUTS].iloc[0].to_dict()
    record[INPUTS[0]] = value
    out = model.predict_one(record)
    assert out['status'] == 'invalid_input' and out['alert'] is None and out['risk_score'] is None


def test_policy_batch_single_and_explanations(frame):
    e = MamdaniRiskEngine(membership_candidate(frame, 'C_rules'))
    cfg = {
        'model_id': e.model_id,
        'default_policy': 'Balanced',
        'policies': {'Balanced': {'threshold': 50.0, 'fpr_cap': 0.05}},
    }
    model = PolicyRiskModel(e, cfg)
    records = frame[INPUTS].iloc[:8]
    batch = model.predict_batch(records, batch_size=3)
    for i, record in enumerate(records.to_dict(orient='records')):
        single = model.predict_one(record)
        assert single['risk_score'] == batch['risk_score'][i]
        assert single['alert'] == batch['alert'][i]
        assert single['risk_level'] == batch['risk_level'][i]
        strengths = batch['rule_strengths'][i]
        actual = {r['id']: r['strength'] for r in single['activated_rules']}
        for j, r in enumerate(e.config['rules']):
            if strengths[j] > 0:
                assert actual[r['id']] == strengths[j]
        assert single['explanation_data']['dominant_rules'] == [r['id'] for r in single['activated_rules'][:3]]


def test_extreme_score_bounds_coverage_and_continuity(frame):
    for candidate in ['A_refit', 'B_membership', 'C_rules']:
        e = MamdaniRiskEngine(membership_candidate(frame, candidate))
        x = pd.DataFrame({c: [0.0, 1e308] for c in INPUTS})
        p = e.predict_batch(x)
        assert (p['status'] == 'ok').all() and ((p['risk_score'] >= 0) & (p['risk_score'] <= 100)).all()
        assert (p['rule_strengths'] > 0).any(axis=1).all()
        a = e.predict_batch(frame[INPUTS].iloc[:20])['risk_score']
        b = e.predict_batch(frame[INPUTS].iloc[:20] * 1.000001)['risk_score']
        assert np.max(np.abs(a - b)) < 0.01


def test_selection_predeclared_and_deterministic():
    summary = {
        'A_refit': {'balanced_accuracy': 0.55, 'fpr': 0.05},
        'B_membership': {'balanced_accuracy': 0.60, 'fpr': 0.04},
        'C_rules': {'balanced_accuracy': 0.65, 'fpr': 0.10},
    }
    assert choose_candidate(summary, {'B_membership': 0.01, 'C_rules': 0.05}) == 'B_membership'
    assert choose_candidate(summary, {'B_membership': -0.01, 'C_rules': 0.05}) == 'A_frozen'
    assert (
        choose_candidate(dict(reversed(list(summary.items()))), {'B_membership': 0.01, 'C_rules': 0.05})
        == 'B_membership'
    )


def test_backward_compatibility_of_frozen_baseline():
    root = Path(__file__).resolve().parents[1]
    e = MamdaniRiskEngine.load(root / 'config/fuzzy/grouped_v1.json')
    record = dict(zip(INPUTS, [100000.0, 100.0, 6.0, 0.0, 0.0]))
    assert e.predict_one(record)['risk_score'] == pytest.approx(76.02135443342287, abs=1e-12)
    assert e.model_id == 'ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b'
