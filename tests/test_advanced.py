"""Analytical and regression tests for experimental multi-layer fuzzy inference."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from task05_experiment import select

from fuzzy_network_risk.advanced import COLUMNS, NAMES, AdvancedRiskEngine, architecture_config, terms
from fuzzy_network_risk.membership import centroid, membership

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def training():
    rng = np.random.default_rng(5)
    f = pd.DataFrame(rng.integers(1, 200, (80, 8)).astype(float), columns=COLUMNS)
    f[COLUMNS[-1]] = rng.integers(0, 2, len(f))
    f['signature'] = [str(i // 2) for i in range(len(f))]
    f[' Label'] = 'BENIGN'
    return f


@pytest.mark.parametrize('name', NAMES[2:])
def test_fit_serialization_and_single_batch(training, name, tmp_path):
    config = architecture_config(training, name)
    engine = AdvancedRiskEngine(config)
    changed = training.copy()
    changed[' Label'] = 'ATTACK'
    assert config == architecture_config(changed, name)
    engine.save(tmp_path / 'config.json')
    restored = AdvancedRiskEngine.load(tmp_path / 'config.json')
    assert engine.model_id == restored.model_id
    batch = engine.predict_batch(training[COLUMNS], batch_size=7)
    np.testing.assert_array_equal(
        batch['risk_score'], restored.predict_batch(training[COLUMNS], batch_size=100)['risk_score']
    )
    assert (batch['status'] == 'ok').all() and ((batch['risk_score'] >= 0) & (batch['risk_score'] <= 100)).all()
    for i in range(8):
        one = engine.predict_one(training[COLUMNS].iloc[i].to_dict())
        assert one['risk_score'] == batch['risk_score'][i]
        expected = ['Low', 'Medium', 'High', 'Critical'][np.searchsorted([25, 50, 75], one['risk_score'], side='right')]
        assert one['risk_level'] == expected
        for layer, output in one['layers'].items():
            assert output['score'] == batch['layers'][layer]['score'][i]
            for rule in output['activated_rules']:
                assert 0 < rule['strength'] <= 1 and rule['reason_key'] == f'task05.{layer}.{rule["id"]}'
    for values in batch['memberships'].values():
        for degree in values.values():
            assert ((degree >= 0) & (degree <= 1)).all()


def test_layer_min_max_implication_and_centroid(training):
    engine = AdvancedRiskEngine(architecture_config(training, 'C_hierarchy'))
    degrees = {'a': {'high': np.array([0.4, 0.8])}, 'b': {'high': np.array([0.6, 0.3])}}
    rule = {
        'id': 'known',
        'antecedent': {'all': [{'feature': 'a', 'term': 'high'}, {'feature': 'b', 'term': 'high'}]},
        'consequent': 'High',
    }
    score, strength = engine._layer(degrees, [rule], 2)
    np.testing.assert_array_equal(strength[:, 0], [0.4, 0.3])
    expected = centroid(engine.grid, np.minimum(np.array([0.4, 0.3])[:, None], engine.output[2]))
    np.testing.assert_array_equal(score, expected)
    # Identical rules do not accumulate strength under maximum aggregation.
    repeated, _ = engine._layer(degrees, [rule, rule], 2)
    np.testing.assert_array_equal(score, repeated)
    full, _ = engine._layer({'a': {'high': np.array([1.0])}, 'b': {'high': np.array([1.0])}}, [rule], 1)
    assert full[0] == pytest.approx((50 + 70 + 85) / 3, abs=0.01)
    either = deepcopy(rule)
    either['antecedent'] = {'any': rule['antecedent']['all']}
    _, s = engine._layer(degrees, [either], 2)
    np.testing.assert_array_equal(s[:, 0], [0.6, 0.8])


def test_intermediate_scores_really_drive_final_fuzzy_layer(training):
    engine = AdvancedRiskEngine(architecture_config(training, 'C_hierarchy'))
    p = engine.predict_batch(training[COLUMNS].head(2))
    degrees = {
        k: {term: membership(v['score'], spec) for term, spec in engine.config['intermediate_memberships'].items()}
        for k, v in p['layers'].items()
        if k != 'final'
    }
    score, strength = engine._layer(degrees, engine.config['layers']['final'], 2)
    np.testing.assert_array_equal(score, p['risk_score'])
    np.testing.assert_array_equal(strength, p['rule_strengths'])
    assert not np.array_equal(score, np.mean([v['score'] for k, v in p['layers'].items() if k != 'final'], axis=0))


@pytest.mark.parametrize('name', NAMES[2:])
@pytest.mark.parametrize('invalid', [None, np.nan, np.inf, -1, '12', True])
def test_invalid_abstention_all_layers(training, name, invalid):
    engine = AdvancedRiskEngine(architecture_config(training, name))
    record = training[COLUMNS].iloc[0].to_dict()
    record[COLUMNS[0]] = invalid
    result = engine.predict_one(record)
    assert result['status'] == 'invalid_input' and result['risk_score'] is None and not result['activated_rules']
    assert all(v['score'] is None for v in result['layers'].values())


@pytest.mark.parametrize('name', NAMES[2:])
def test_missing_label_rejection_zero_and_extreme(training, name):
    engine = AdvancedRiskEngine(architecture_config(training, name))
    record = {c: 0 for c in COLUMNS}
    assert engine.predict_one(record)['status'] == 'ok'
    large = {c: 1e308 for c in COLUMNS}
    large[COLUMNS[-1]] = 1
    assert 0 <= engine.predict_one(large)['risk_score'] <= 100
    large[COLUMNS[-1]] = 2
    assert engine.predict_one(large)['status'] == 'invalid_input'
    del record[COLUMNS[1]]
    assert engine.predict_one(record)['risk_score'] is None
    record[' Label'] = 'BENIGN'
    with pytest.raises(ValueError, match='remove labels'):
        engine.predict_one(record)
    assert len(engine.predict_batch(pd.DataFrame(columns=COLUMNS))['risk_score']) == 0


def test_missing_module_and_no_final_rules_abstain(training):
    config = architecture_config(training, 'C_hierarchy')
    config['layers']['intensity'] = []
    result = AdvancedRiskEngine(config).predict_one(training[COLUMNS].iloc[0].to_dict())
    assert result['status'] == 'no_rule_activation' and result['risk_score'] is None
    config = architecture_config(training, 'B_flat8')
    config['layers']['final'] = []
    assert AdvancedRiskEngine(config).predict_one(training[COLUMNS].iloc[0].to_dict())['risk_score'] is None


def test_membership_partition_coverage_and_boundary_behavior():
    specs = terms(25, 50, 75, 100)
    x = np.array([0, 25, 37.5, 50, 62.5, 75, 100])
    values = np.stack([membership(x, s) for s in specs.values()])
    np.testing.assert_allclose(values.sum(axis=0), 1)
    assert values[0, 0] == 1 and values[-1, -1] == 1


def test_illegal_subsystem_dependency_rejected(training):
    config = architecture_config(training, 'C_hierarchy')
    config['layers']['timing'][0]['antecedent'] = {'all': [{'feature': 'intensity', 'term': 'high'}]}
    with pytest.raises(ValueError, match='Unknown layer'):
        AdvancedRiskEngine(config)


def test_selection_requires_capture_day_gate_even_with_fold_gains():
    summary = {n: {'recall': 0.2 if n in NAMES[:2] else 0.4, 'fpr': 0.05, 'abstention_rate': 0} for n in NAMES}
    folds = [
        {
            'candidate': n,
            'fold': k,
            'policy': 'Balanced',
            'group_metrics': {'recall': summary[n]['recall'], 'false_positive_rate': 0.05},
        }
        for n in NAMES
        for k in range(3)
    ]
    intervals = {n: {b: {'recall_gain_95': [0.1, 0.2]} for b in NAMES[:2]} for n in NAMES[2:]}
    stress = [
        {'candidate': n, 'day': d, 'group_metrics': {'recall': summary[n]['recall'], 'false_positive_rate': 0.05}}
        for n in NAMES
        for d in ['Tuesday', 'Wednesday', 'Thursday']
    ]
    counts = {'B_flat8': 15, 'C_hierarchy': 34, 'D_behavior': 25}
    assert select(summary, folds, intervals, stress, counts) == 'B_flat8'
    for s in stress:
        if s['candidate'] in NAMES[2:] and s['day'] == 'Tuesday':
            s['group_metrics']['recall'] = 0
    assert select(summary, folds, intervals, stress, counts) == 'A_frozen'


def test_saved_candidates_and_production_compatibility():
    path = ROOT / 'config/fuzzy/task05'
    recommendation = json.loads((path / 'recommendation.json').read_text())
    assert recommendation['selected'] == 'A_frozen' and not recommendation['promotion_gate_passed']
    for name in NAMES[2:]:
        for k in range(3):
            e = AdvancedRiskEngine.load(path / f'{name}_fold{k}.json')
            assert set(e.columns) == set(COLUMNS) and e.config['method'] == 'mamdani-min-max-centroid'
    from fuzzy_network_risk.webapp.service import WebService

    service = WebService()
    assert service.model['configuration_version'] == 'task04-v1'
    assert len(service.engine.columns) == 5


@pytest.mark.parametrize('name', NAMES[2:])
def test_existing_policy_wrapper_preserves_hierarchy_evidence(training, name):
    from fuzzy_network_risk.policy import PolicyRiskModel

    e = AdvancedRiskEngine(architecture_config(training, name))
    record = training[COLUMNS].iloc[0].to_dict()
    settings = {
        'model_id': e.model_id,
        'policies': {
            p: {'threshold': t, 'fpr_cap': cap}
            for p, t, cap in [('Sensitive', 25.0, 0.1), ('Balanced', 50.0, 0.05), ('Conservative', 75.0, 0.01)]
        },
    }
    results = [PolicyRiskModel(e, settings, p).predict_one(record) for p in settings['policies']]
    assert len({r['risk_score'] for r in results}) == 1
    assert all(r['layers'] == results[0]['layers'] for r in results)
    assert all(r['alert'] == (r['risk_score'] >= r['alert_policy']['threshold']) for r in results)


def test_actual_registration_and_expanded_duplicate_protection():
    # Ordinary unit tests do not load a full source dataset. These recorded
    # integrity assertions complement the separate cache-based validation script.
    root = ROOT / 'reports/fuzzy/task05'
    audit = json.loads((root / 'partition_audit.json').read_text())
    assert (
        audit['overlap'] == 0
        and audit['exposed_contamination'] == 0
        and audit['eight_input_duplicate_role_overlap'] == 0
    )
    assert audit['common_valid_rows'] == 60000
    assert set(COLUMNS).issuperset(
        {' Flow Packets/s', ' Total Fwd Packets', ' Packet Length Mean', ' Bwd Packet Length Std', ' Down/Up Ratio'}
    )
