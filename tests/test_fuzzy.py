import json

import numpy as np
import pandas as pd
import pytest

from fuzzy_network_risk.calibration import fit_config
from fuzzy_network_risk.data import INPUTS, LABEL
from fuzzy_network_risk.engine import LEVELS, MamdaniRiskEngine, config_digest, evaluate_expression
from fuzzy_network_risk.evaluation import binary_metrics, calibrate_alert
from fuzzy_network_risk.membership import centroid, fuzzy_and, fuzzy_or, trapezoid, triangle


@pytest.fixture
def training():
    return pd.DataFrame({c: np.arange(1.0, 101.0) for c in INPUTS})


@pytest.fixture
def config(training):
    return fit_config(training, 'synthetic')


@pytest.fixture
def engine(config):
    return MamdaniRiskEngine(config)


@pytest.fixture
def record():
    return dict(zip(INPUTS, [100.0, 20.0, 50.0, 10.0, 1.0], strict=True))


def test_triangle_analytic():
    np.testing.assert_allclose(triangle([-1, 0, 1, 2, 3, 4, 5], 0, 2, 4), [0, 0, 0.5, 1, 0.5, 0, 0])


def test_trapezoid_analytic():
    np.testing.assert_allclose(trapezoid([-1, 0, 1, 2, 3, 4, 5, 6, 7], 0, 2, 4, 6), [0, 0, 0.5, 1, 1, 1, 0.5, 0, 0])


def test_shoulders_endpoints():
    np.testing.assert_allclose(trapezoid([0, 1, 2, 3], 0, 0, 1, 2), [1, 1, 0, 0])
    np.testing.assert_allclose(triangle([0, 1, 2], 0, 0, 2), [1, 0.5, 0])
    np.testing.assert_allclose(trapezoid([0, 1, 2], 0, 1, 2, 2), [0, 1, 1])


@pytest.mark.parametrize('parameters', [(0, 0, 0, 0), (2, 1, 3, 4), (0, 1, np.inf, np.inf)])
def test_invalid_trapezoid(parameters):
    with pytest.raises(ValueError):
        trapezoid([1], *parameters)


def test_degree_bounds(engine):
    x = pd.DataFrame({c: np.geomspace(1e-10, 1e100, 400) for c in INPUTS})
    prediction = engine.predict_batch(x)
    for terms in prediction['memberships'].values():
        stack = np.stack(list(terms.values()))
        assert ((stack >= 0) & (stack <= 1)).all()
        np.testing.assert_allclose(stack.sum(axis=0), 1)


def test_and_or():
    np.testing.assert_allclose(fuzzy_and([0.2, 0.7], [0.8, 0.4]), [0.2, 0.4])
    np.testing.assert_allclose(fuzzy_or([0.2, 0.7], [0.8, 0.4]), [0.8, 0.7])


def test_nested_expression():
    d = {'x': {'a': np.array([0.2, 0.8])}, 'y': {'b': np.array([0.6, 0.4])}}
    leaf1 = {'feature': 'x', 'term': 'a'}
    leaf2 = {'feature': 'y', 'term': 'b'}
    np.testing.assert_allclose(evaluate_expression({'any': [{'all': [leaf1, leaf2]}, leaf1]}, d), [0.2, 0.8])


def test_centroid_analytic():
    x = np.linspace(0, 100, 201)
    assert centroid(x, triangle(x, 0, 50, 100)) == pytest.approx(50, abs=1e-12)
    assert centroid(x, trapezoid(x, 0, 0, 100, 100)) == pytest.approx(50, abs=1e-12)
    assert centroid(x, triangle(x, 10, 20, 30)) == pytest.approx(20, abs=1e-12)
    assert np.isnan(centroid(x, np.zeros_like(x)))


def test_invalid_centroid_grid():
    with pytest.raises(ValueError):
        centroid([1, 0], [1, 1])


def test_rule_activation_and_mamdani_aggregation(config, record):
    config['rules'] = [
        {
            'id': 'A',
            'antecedent': {'all': [{'feature': 'rate', 'term': 'moderate'}, {'feature': 'volume', 'term': 'few'}]},
            'consequent': 'Low',
            'weight': 1.0,
            'rationale': 'synthetic',
        },
        {
            'id': 'B',
            'antecedent': {'any': [{'feature': 'size', 'term': 'small'}, {'feature': 'balance', 'term': 'balanced'}]},
            'consequent': 'High',
            'weight': 0.7,
            'rationale': 'synthetic',
        },
    ]
    e = MamdaniRiskEngine(config)
    out = e.predict_batch(record)
    d = out['memberships']
    a = min(d['rate']['moderate'][0], d['volume']['few'][0])
    b = max(d['size']['small'][0], d['balance']['balanced'][0]) * 0.7
    np.testing.assert_allclose(out['rule_strengths'][0], [a, b])
    aggregate = np.maximum(np.minimum(a, e.output_sets[0]), np.minimum(b, e.output_sets[2]))
    assert out['risk_score'][0] == pytest.approx(centroid(e.grid, aggregate), abs=1e-12)


def test_duplicate_same_consequent_uses_max(config, record):
    base = {
        'id': 'A',
        'antecedent': {'feature': 'rate', 'term': 'intensive'},
        'consequent': 'High',
        'weight': 1.0,
        'rationale': 'synthetic',
    }
    config['rules'] = [base]
    a = MamdaniRiskEngine(config).predict_one(record)
    config['rules'].append(dict(base, id='B', weight=0.1))
    b = MamdaniRiskEngine(config).predict_one(record)
    assert a['risk_score'] == b['risk_score']


def test_score_bounds_and_zero(engine):
    out = engine.predict_batch(pd.DataFrame({c: [0.0, 1.0, 10.0, 1e300] for c in INPUTS}))
    assert (out['status'] == 'ok').all()
    assert ((out['risk_score'] >= 0) & (out['risk_score'] <= 100)).all()


def test_single_batch_and_determinism(engine, record):
    a = engine.predict_one(record)
    b = engine.predict_one(record)
    assert a == b
    batch = engine.predict_batch([record] * 7, batch_size=3)
    np.testing.assert_allclose(batch['risk_score'], a['risk_score'], rtol=0, atol=0)
    assert a['activated_rules'] and a['membership_degrees'] and a['explanation_data']['message_key'] == 'prediction.ok'
    json.dumps(a, allow_nan=False)


@pytest.mark.parametrize('bad', [None, np.nan, np.inf, -np.inf, -1, 'bad', '12', True])
def test_invalid_input(engine, record, bad):
    record[INPUTS[0]] = bad
    out = engine.predict_one(record)
    assert out['status'] == 'invalid_input' and out['risk_score'] is None and out['risk_level'] is None
    assert not out['activated_rules'] and out['alert'] is None
    assert INPUTS[0] in out['explanation_data']['invalid_features']
    json.dumps(out, allow_nan=False)


def test_unrepresentable_integer_abstains(engine, record):
    record[INPUTS[0]] = 1 << 2000
    assert engine.predict_one(record)['status'] == 'invalid_input'


def test_missing_input(engine, record):
    del record[INPUTS[2]]
    assert engine.predict_one(record)['status'] == 'invalid_input'
    assert engine.predict_one({})['status'] == 'invalid_input'


def test_extreme_saturation(engine):
    huge = {c: np.finfo(float).max for c in INPUTS}
    a = engine.predict_one(huge)
    assert a['status'] == 'ok' and len(a['explanation_data']['outside_training_range']) == 5
    assert all(np.isfinite(list(d.values())).all() for d in a['membership_degrees'].values())


def test_outside_training_range_is_valid(engine, record):
    record[INPUTS[0]] = 1000.0
    out = engine.predict_one(record)
    assert out['status'] == 'ok' and INPUTS[0] in out['explanation_data']['outside_training_range']


def test_no_activation_abstains(config, record):
    config['rules'] = []
    out = MamdaniRiskEngine(config).predict_one(record)
    assert out['status'] == 'no_rule_activation' and out['risk_score'] is None and out['alert'] is None


@pytest.mark.parametrize('cut,level', [(25.0, 'Medium'), (50.0, 'High'), (75.0, 'Critical')])
def test_category_threshold_boundaries(config, record, cut, level):
    # A symmetric output set places the analytic centroid exactly at each cut.
    config['rules'] = [
        {
            'id': 'A',
            'antecedent': {'feature': 'balance', 'term': 'balanced'},
            'consequent': 'Medium',
            'rationale': 'synthetic',
        }
    ]
    config['output']['sets']['Medium'] = {'kind': 'triangle', 'parameters': [cut - 10, cut, cut + 10]}
    out = MamdaniRiskEngine(config).predict_one(record)
    assert out['risk_score'] == pytest.approx(cut) and out['risk_level'] == level


def test_category_consistency(engine, training):
    out = engine.predict_batch(training)
    expected = np.array(LEVELS)[np.searchsorted([25, 50, 75], out['risk_score'], side='right')]
    np.testing.assert_array_equal(out['risk_level'], expected)


def test_label_and_metadata_rejected(engine, record):
    with pytest.raises(ValueError):
        engine.predict_one(dict(record, **{LABEL: 'BENIGN'}))
    with pytest.raises(ValueError):
        engine.predict_one(dict(record, source_row_id=1))


def test_config_cannot_use_label(config):
    config['features']['rate']['column'] = LABEL
    with pytest.raises(ValueError):
        MamdaniRiskEngine(config)


def test_fit_rejects_label(training):
    with pytest.raises(ValueError):
        fit_config(training.assign(**{LABEL: 'BENIGN'}), 'bad')


def test_serialization(engine, tmp_path, record):
    path = tmp_path / 'model.json'
    engine.save(path)
    loaded = MamdaniRiskEngine.load(path)
    assert loaded.model_id == engine.model_id
    assert loaded.predict_one(record) == engine.predict_one(record)


def test_fit_reproducible(training):
    assert config_digest(fit_config(training, 'a')) == config_digest(fit_config(training, 'a'))


def test_zero_heavy_degenerate_training():
    f = pd.DataFrame({c: [0.0] * 12 for c in INPUTS})
    engine = MamdaniRiskEngine(fit_config(f, 'zero'))
    assert engine.predict_one({c: 0.0 for c in INPUTS})['status'] == 'ok'


def test_empty_batch(engine):
    assert len(engine.predict_batch(pd.DataFrame(columns=INPUTS))['risk_score']) == 0


def test_metrics_known_matrix():
    m = binary_metrics([0, 0, 1, 1], [10, 80, 20, 90], 50)
    assert m['confusion_matrix'] == {'tn': 1.0, 'fp': 1.0, 'fn': 1.0, 'tp': 1.0}
    for k in ['precision', 'recall', 'f1', 'false_positive_rate', 'false_negative_rate', 'balanced_accuracy']:
        assert m[k] == 0.5
    assert m['roc_auc'] == pytest.approx(0.75)
    assert m['pr_auc_average_precision'] == pytest.approx(5 / 6)


def test_metrics_ties_and_weighting():
    m = binary_metrics([0, 1], [50, 50], 50)
    assert m['roc_auc'] == 0.5 and m['pr_auc_average_precision'] == 0.5
    w = binary_metrics([0, 0, 1], [10, 80, 90], 50, [0.5, 0.5, 1.0])
    assert w['confusion_matrix'] == {'tn': 0.5, 'fp': 0.5, 'fn': 0.0, 'tp': 1.0}


def test_metric_degenerate_classes():
    m = binary_metrics([0, 0], [1, 2], 50)
    assert m['recall'] is None and m['roc_auc'] is None and m['pr_auc_average_precision'] is None
    assert m['precision'] == 0


def test_calibration_uses_candidates():
    threshold, rows = calibrate_alert([0, 0, 1, 1], [10, 30, 60, 90], candidates=[25, 45, 65])
    assert threshold == 45 and len(rows) == 3


def test_config_rejects_unknown_rule(config):
    config['rules'][0]['antecedent']['all'][0]['term'] = 'not_real'
    with pytest.raises(ValueError):
        MamdaniRiskEngine(config)
