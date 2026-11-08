"""Experimental flat and genuinely hierarchical Mamdani architectures.

Independent of the production five-input engine. Every layer uses min AND,
max OR/aggregation, clipped implication and numerical centroid defuzzification.
"""

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import fit_config
from .data import INPUTS
from .engine import LEVELS, _numeric_value, config_digest, evaluate_expression
from .membership import centroid, membership
from .rules import rule

EXTRA = [' Flow Duration', ' Flow IAT Std', ' SYN Flag Count']
COLUMNS = INPUTS + EXTRA
NAMES = ['A_frozen', 'A_refit', 'B_flat8', 'C_hierarchy', 'D_behavior']


def terms(a, b, c, upper):
    return {
        'low': {'kind': 'trapezoid', 'parameters': [0.0, 0.0, a, b]},
        'moderate': {'kind': 'triangle', 'parameters': [a, b, c]},
        'high': {'kind': 'trapezoid', 'parameters': [b, c, upper, upper]},
    }


def fitted_features(training):
    if not {'signature', *COLUMNS}.issubset(training.columns):
        raise ValueError('Training features/provenance required')
    original = fit_config(training[INPUTS], 'task05-training')
    features = deepcopy(original['features'])
    for key, feature in features.items():
        old = list(feature['sets'])
        feature['sets'] = {n: feature['sets'][o] for n, o in zip(['low', 'moderate', 'high'], old)}
    # Same row-quantile reference as fair A_refit; expanded features alone,
    # not simultaneous label-based membership optimization, are investigated.
    for key, column, unit in [('duration', EXTRA[0], 'microseconds'), ('iat', EXTRA[1], 'microseconds')]:
        x = training[column].to_numpy(dtype=float)
        if not (np.isfinite(x) & (x >= 0)).all():
            raise ValueError('Invalid training measurements; no silent imputation')
        ref = x[x > 0] if key == 'iat' and (x > 0).sum() >= 3 else x
        a, b, c = map(float, np.quantile(ref, [0.25, 0.60, 0.90]))
        delta = max(1.0, a * 0.01)
        b = max(b, a + delta)
        c = max(c, b + delta)
        upper = float(np.log1p(max(float(x.max()), c)))
        features[key] = {
            'column': column,
            'unit': unit,
            'transform': 'log1p',
            'upper': upper,
            'training_min': float(x.min()),
            'training_max': float(x.max()),
            'raw_anchors': [a, b, c],
            'anchor_basis': 'training_positive_p25_p60_p90' if key == 'iat' else 'training_p25_p60_p90',
            'sets': terms(*map(float, np.log1p([a, b, c])), upper),
        }
    x = training[EXTRA[2]].to_numpy(dtype=float)
    if not (np.isfinite(x) & np.isin(x, [0.0, 1.0])).all():
        raise ValueError('SYN export not binary; investigate rather than silently reinterpret')
    features['syn'] = {
        'column': EXTRA[2],
        'unit': 'exported 0/1 flag indicator, not attempt rate',
        'transform': 'identity',
        'upper': 1.0,
        'training_min': float(x.min()),
        'training_max': float(x.max()),
        'raw_anchors': [0.0, 0.5, 1.0],
        'anchor_basis': 'physical_binary_export_domain',
        'sets': {
            'absent': {'kind': 'trapezoid', 'parameters': [0.0, 0.0, 0.0, 1.0]},
            'present': {'kind': 'trapezoid', 'parameters': [0.0, 1.0, 1.0, 1.0]},
        },
    }
    return features, original['output']


def r(identifier, conditions, consequent, reason):
    return rule(identifier, conditions, consequent, reason)


def load_rules(prefix='L'):
    return [
        r(
            prefix + '01',
            [('rate', 'low'), ('volume', 'low')],
            'Low',
            'Sparse few-packet exchange; low-rate attacks can overlap.',
        ),
        r(
            prefix + '02',
            [('rate', 'low'), ('volume', 'moderate')],
            'Low',
            'Low intensity with modest volume is weak load evidence.',
        ),
        r(prefix + '03', [('rate', 'low'), ('volume', 'high')], 'Medium', 'Long low-rate transfers need context.'),
        r(
            prefix + '04',
            [('rate', 'moderate'), ('volume', 'low')],
            'Low',
            'Short ordinary exchanges support a routine-load hypothesis.',
        ),
        r(
            prefix + '05',
            [('rate', 'moderate'), ('volume', 'moderate')],
            'Low',
            'Ordinary intensity and volume carry weak load concern.',
        ),
        r(
            prefix + '06',
            [('rate', 'moderate'), ('volume', 'high')],
            'Medium',
            'Sustained packet volume warrants context.',
        ),
        r(prefix + '07', [('rate', 'high'), ('volume', 'low')], 'Low', 'Tiny duration can inflate few-packet rate.'),
        r(
            prefix + '08',
            [('rate', 'high'), ('volume', 'moderate')],
            'Medium',
            'Intensity corroborated by nontrivial volume.',
        ),
        r(
            prefix + '09',
            [('rate', 'high'), ('volume', 'high')],
            'High',
            'Joint high intensity and volume support load concern.',
        ),
    ]


def timing_rules():
    return [
        r('T01', [('duration', 'low')], 'Low', 'Short lifetime provides little long-gap persistence evidence.'),
        r('T02', [('iat', 'low')], 'Low', 'Stable/small inter-arrival spread is weak intermittent-timing evidence.'),
        r(
            'T03',
            [('duration', 'moderate'), ('iat', 'moderate')],
            'Medium',
            'Moderate persistence and variable spacing are ambiguous.',
        ),
        r(
            'T04',
            [('duration', 'high'), ('iat', 'moderate')],
            'Medium',
            'Long lifetime with moderate gaps may be an idle legitimate session.',
        ),
        r(
            'T05',
            [('duration', 'moderate'), ('iat', 'high')],
            'Medium',
            'Large gaps without long persistence require context.',
        ),
        r(
            'T06',
            [('duration', 'high'), ('iat', 'high')],
            'High',
            'Long-lived intermittent activity is a timing concern, not attack attribution.',
        ),
    ]


def connection_rules():
    return [
        r('N01', [('syn', 'absent')], 'Low', 'Absence of exported SYN evidence is not proof of a safe connection.'),
        r('N02', [('balance', 'moderate')], 'Low', 'Exported directional balance counters a forward-heavy hypothesis.'),
        r(
            'N03',
            [('balance', 'high')],
            'Low',
            'Backward-heavy traffic does not support this forward-heavy connection hypothesis.',
        ),
        r(
            'N04',
            [('syn', 'present'), ('balance', 'low'), ('volume', 'low')],
            'Medium',
            'A short SYN-bearing forward-heavy exchange is ambiguous.',
        ),
        r(
            'N05',
            [('syn', 'present'), ('balance', 'low'), ('volume', 'moderate')],
            'Medium',
            'Nontrivial forward-heavy SYN-bearing exchange merits context.',
        ),
        r(
            'N06',
            [('syn', 'present'), ('balance', 'low'), ('volume', 'high')],
            'High',
            'SYN evidence corroborated by high volume and exported forward imbalance. No repeated-attempt claim.',
        ),
    ]


def structure_rules():
    return [
        r('P01', [('size', 'low')], 'Low', 'Small packets alone are not an abnormal response-size pattern.'),
        r(
            'P02',
            [('variation', 'low')],
            'Low',
            'Low response spread can be routine or reflect too few backward packets.',
        ),
        r(
            'P03',
            [('size', 'moderate'), ('variation', 'moderate')],
            'Medium',
            'Moderate response size and spread are ambiguous.',
        ),
        r(
            'P04',
            [('size', 'high'), ('variation', 'moderate')],
            'Medium',
            'Large responses may simply be payload transfer.',
        ),
        r(
            'P05',
            [('size', 'moderate'), ('variation', 'high')],
            'Medium',
            'High spread with moderate mean size warrants context.',
        ),
        r(
            'P06',
            [('size', 'high'), ('variation', 'high')],
            'High',
            'Joint large size and high response variability; benign transfers overlap.',
        ),
    ]


def final_rules(modules, behavior=False):
    rules = [
        r(
            'F01',
            [(m, 'low') for m in modules],
            'Low',
            'All module outputs weakly support their respective concern patterns.',
        )
    ]
    rules.append(
        rule(
            'F02',
            [(m, 'moderate') for m in modules],
            'Medium',
            'Any moderate module is ambiguous behavioral evidence.',
            operator='any',
        )
    )
    rules.append(
        rule(
            'F03',
            [(m, 'high') for m in modules],
            'High' if behavior else 'Medium',
            'A corroborated behavior module can warrant elevated investigation.'
            if behavior
            else 'One elevated dimension needs cross-dimension corroboration.',
            operator='any',
        )
    )
    if behavior:
        for identifier, a, b in [
            ('F04', 'flood', 'intermittent'),
            ('F05', 'flood', 'connection'),
            ('F06', 'intermittent', 'connection'),
        ]:
            rules.append(
                r(
                    identifier,
                    [(a, 'high'), (b, 'high')],
                    'Critical',
                    'Two distinct multi-input behavior hypotheses agree; this is not a named attack diagnosis.',
                )
            )
    else:
        rules.extend(
            [
                r(
                    'F04',
                    [('intensity', 'high'), ('connection', 'high')],
                    'Critical',
                    'Joint load and connection concerns provide corroboration.',
                ),
                r(
                    'F05',
                    [('timing', 'high'), ('structure', 'high')],
                    'High',
                    'Joint long-gap timing and varied-response structure provide corroboration.',
                ),
                r(
                    'F06',
                    [('intensity', 'high'), ('timing', 'high')],
                    'High',
                    'Joint sustained load and intermittent timing merit investigation.',
                ),
                r(
                    'F07',
                    [('connection', 'high'), ('structure', 'high')],
                    'High',
                    'Connection and response structure concerns corroborate each other.',
                ),
            ]
        )
    return rules


def architecture_config(training, name):
    if name not in NAMES[2:]:
        raise ValueError('Only registered experimental architectures')
    features, output = fitted_features(training)
    if name == 'B_flat8':
        rules = load_rules('E') + [
            r(
                'E10',
                [('duration', 'high'), ('iat', 'high'), ('variation', 'high')],
                'High',
                'Long intermittent exchanges with highly varied responses warrant investigation.',
            ),
            r(
                'E11',
                [('size', 'high'), ('variation', 'high'), ('duration', 'high')],
                'High',
                'Large varied responses sustained over a long flow; benign overlap remains.',
            ),
            r(
                'E12',
                [('syn', 'present'), ('balance', 'low'), ('volume', 'high')],
                'High',
                'SYN-bearing high-volume exported forward-heavy traffic.',
            ),
            r(
                'E13',
                [('syn', 'present'), ('balance', 'low'), ('volume', 'low')],
                'Medium',
                'Short handshake-like exchanges are ambiguous, not proof of scanning.',
            ),
            r(
                'E14',
                [('rate', 'high'), ('volume', 'high'), ('size', 'low')],
                'Critical',
                'Repeated small high-rate packets with sustained volume support flooding-like load concern.',
            ),
            r(
                'E15',
                [('duration', 'low'), ('volume', 'low')],
                'Low',
                'A short small exchange supports a routine-transaction hypothesis.',
            ),
        ]
        layers = {'final': rules}
    elif name == 'C_hierarchy':
        layers = {
            'intensity': load_rules(),
            'timing': timing_rules(),
            'connection': connection_rules(),
            'structure': structure_rules(),
        }
        layers['final'] = final_rules(list(layers))
    else:
        flood = [
            r('B01', [('rate', 'low')], 'Low', 'Sparse rate weakens a high-rate flooding hypothesis.'),
            r('B02', [('volume', 'low')], 'Low', 'Few-packet bursts are not sustained floods.'),
            r(
                'B03',
                [('rate', 'moderate'), ('volume', 'moderate')],
                'Low',
                'Ordinary load provides weak flooding evidence.',
            ),
            r(
                'B04',
                [('rate', 'moderate'), ('volume', 'high')],
                'Medium',
                'Volume without high intensity is ambiguous.',
            ),
            r('B05', [('rate', 'high'), ('volume', 'moderate')], 'Medium', 'Intensity corroborated by modest volume.'),
            r(
                'B06',
                [('rate', 'high'), ('volume', 'high')],
                'High',
                'Sustained high-rate packet load supports flooding-like concern.',
            ),
        ]
        intermittent = timing_rules() + [
            r(
                'T07',
                [('duration', 'high'), ('iat', 'high'), ('variation', 'high'), ('size', 'high')],
                'Critical',
                'Persistent intermittent exchanges with large varied responses corroborate a resource-occupation-like behavior; ordinary downloads can overlap.',
            )
        ]
        layers = {'flood': flood, 'intermittent': intermittent, 'connection': connection_rules()}
        layers['final'] = final_rules(list(layers), behavior=True)
    return {
        'version': 'task05-architecture-v1',
        'name': name,
        'method': 'mamdani-min-max-centroid',
        'seed': 20261105,
        'features': features,
        'layers': layers,
        'output': output,
        'fit_rows': len(training),
        'fit_signature_groups': training.signature.nunique(),
        'risk_category_cuts': [25.0, 50.0, 75.0],
        'intermediate_memberships': terms(25.0, 50.0, 75.0, 100.0),
        'batch_size': 1024,
        'invalid': 'abstain_all_layers_no_imputation',
        'score_meaning': 'behavioral_index_not_probability',
    }


class AdvancedRiskEngine:
    def __init__(self, config):
        self.config = deepcopy(config)
        self._validate()
        self.model_id = config_digest(self.config)
        self.columns = [v['column'] for v in self.config['features'].values()]
        self.grid = np.linspace(0, 100, self.config['output']['grid_points'])
        self.output = np.stack([membership(self.grid, self.config['output']['sets'][level]) for level in LEVELS])

    def _validate(self):
        c = self.config
        if (
            c.get('method') != 'mamdani-min-max-centroid'
            or set(f['column'] for f in c['features'].values()) != set(COLUMNS)
            or len(c['features']) != 8
        ):
            raise ValueError('Exactly eight approved behavior inputs required')
        if c['output']['grid_points'] < 3 or c['risk_category_cuts'] != [25.0, 50.0, 75.0]:
            raise ValueError('Invalid output domain')
        for f in c['features'].values():
            if f['transform'] not in ['identity', 'log1p'] or not np.isfinite(f['upper']) or f['upper'] <= 0:
                raise ValueError('Invalid transform/domain')
            for spec in f['sets'].values():
                membership(np.array([0.0, f['upper']]), spec)
        for s in c['output']['sets'].values():
            membership(np.array([0.0, 100.0]), s)
        for s in c['intermediate_memberships'].values():
            membership(np.array([0.0, 100.0]), s)
        layers = c['layers']
        if not layers or list(layers)[-1] != 'final':
            raise ValueError('Final layer must follow acyclic independent subsystems')
        for layer, rules in layers.items():
            allowed = (
                {k: set(v['sets']) for k, v in c['features'].items()}
                if len(layers) == 1 or layer != 'final'
                else {k: set(c['intermediate_memberships']) for k in layers if k != 'final'}
            )

            def check(e):
                if set(e) == {'feature', 'term'}:
                    if e['feature'] not in allowed or e['term'] not in allowed[e['feature']]:
                        raise ValueError('Unknown layer feature/term')
                elif len(e) == 1 and next(iter(e)) in ['all', 'any'] and next(iter(e.values())):
                    for child in next(iter(e.values())):
                        check(child)
                else:
                    raise ValueError('Malformed fuzzy expression')

            ids = []
            for r in rules:
                check(r['antecedent'])
                ids.append(r['id'])
                if r['consequent'] not in LEVELS or not 0 < r.get('weight', 1) <= 1:
                    raise ValueError('Invalid rule output/weight')
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate layer rule IDs')

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

    def save(self, path):
        Path(path).write_text(json.dumps(self.config, indent=2, allow_nan=False), encoding='utf-8')

    def _coerce(self, records):
        if isinstance(records, Mapping):
            records = [records]
        f = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
        if not f.columns.is_unique or set(f.columns) - set(self.columns):
            raise ValueError('Only approved numerical inputs; remove labels and provenance')
        x = np.full((len(f), 8), np.nan)
        for j, c in enumerate(self.columns):
            if c in f:
                values = f[c]
                x[:, j] = (
                    values.to_numpy(dtype=float, na_value=np.nan)
                    if values.dtype.kind in 'iuf'
                    else [_numeric_value(v) for v in values]
                )
        return x

    def _layer(self, degrees, rules, n):
        strengths = (
            np.stack([evaluate_expression(r['antecedent'], degrees) * r.get('weight', 1.0) for r in rules], axis=1)
            if rules
            else np.zeros((n, 0))
        )
        aggregate = np.zeros((n, len(self.grid)))
        for i, level in enumerate(LEVELS):
            indices = [j for j, r in enumerate(rules) if r['consequent'] == level]
            height = strengths[:, indices].max(axis=1) if indices else np.zeros(n)
            aggregate = np.maximum(aggregate, np.minimum(height[:, None], self.output[i]))
        return centroid(self.grid, aggregate), strengths

    def _infer(self, x):
        valid = (np.isfinite(x) & (x >= 0)).all(axis=1)
        # Exported SYN is an indicator domain, unlike other nonnegative features.
        syn = list(self.config['features']).index('syn')
        valid &= x[:, syn] <= 1
        safe = np.where(np.isfinite(x) & (x >= 0), x, 0.0)
        degrees = {}
        outside = np.zeros_like(x, dtype=bool)
        for j, (k, f) in enumerate(self.config['features'].items()):
            z = np.log1p(safe[:, j]) if f['transform'] == 'log1p' else safe[:, j]
            z = np.clip(z, 0, f['upper'])
            outside[:, j] = (safe[:, j] < f['training_min']) | (safe[:, j] > f['training_max'])
            degrees[k] = {t: np.where(valid, membership(z, s), 0.0) for t, s in f['sets'].items()}
        layers = {}
        intermediate = {}
        for name, rules in self.config['layers'].items():
            layer_degrees = intermediate if name == 'final' and len(self.config['layers']) > 1 else degrees
            score, strengths = self._layer(layer_degrees, rules, len(x))
            score = np.clip(score, 0, 100)
            score[~valid] = np.nan
            layers[name] = {'score': score, 'strengths': strengths}
            if name != 'final':
                intermediate[name] = {
                    t: np.where(np.isfinite(score), membership(np.nan_to_num(score), s), 0.0)
                    for t, s in self.config['intermediate_memberships'].items()
                }
        # A missing subsystem output abstains the final layer; zero memberships
        # cannot silently substitute a fabricated Low intermediate score.
        ready = valid.copy()
        for name in intermediate:
            ready &= np.isfinite(layers[name]['score'])
        score = layers['final']['score']
        score[~ready] = np.nan
        status = np.where(~valid, 'invalid_input', np.where(np.isfinite(score), 'ok', 'no_rule_activation'))
        level = np.full(len(x), None, dtype=object)
        ok = np.isfinite(score)
        level[ok] = np.asarray(LEVELS, dtype=object)[np.searchsorted([25.0, 50.0, 75.0], score[ok], side='right')]
        return {
            'risk_score': score,
            'risk_level': level,
            'status': status,
            'memberships': degrees,
            'intermediate_memberships': intermediate,
            'layers': layers,
            'rule_strengths': layers['final']['strengths'],
            'out_of_training_range': outside & valid[:, None],
        }

    def predict_batch(self, records, batch_size=1024):
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError('Positive integer batch size required')
        x = self._coerce(records)
        if not len(x):
            return self._infer(x)
        parts = [self._infer(x[i : i + batch_size]) for i in range(0, len(x), batch_size)]

        def combine(items):
            if isinstance(items[0], dict):
                return {k: combine([v[k] for v in items]) for k in items[0]}
            return np.concatenate(items)

        return combine(parts)

    def predict_one(self, record):
        p = self.predict_batch(record)
        if len(p['status']) != 1:
            raise ValueError('Exactly one record required')
        ok = p['status'][0] == 'ok'
        layers = {}
        for name, result in p['layers'].items():
            rules = [
                {
                    'id': r['id'],
                    'strength': float(result['strengths'][0, j]),
                    'consequent': r['consequent'],
                    'antecedent': r['antecedent'],
                    'rationale_en': r['rationale'],
                    'reason_key': f'task05.{name}.{r["id"]}',
                }
                for j, r in enumerate(self.config['layers'][name])
                if result['strengths'][0, j] > 0
            ]
            rules.sort(key=lambda r: (-r['strength'], r['id']))
            layers[name] = {
                'score': float(result['score'][0]) if np.isfinite(result['score'][0]) else None,
                'activated_rules': rules,
                'membership_degrees': {t: float(v[0]) for t, v in p['intermediate_memberships'].get(name, {}).items()},
            }
        score = float(p['risk_score'][0]) if ok else None
        return {
            'status': str(p['status'][0]),
            'risk_score': score,
            'risk_level': str(p['risk_level'][0]) if ok else None,
            'model_id': self.model_id,
            'architecture': self.config['name'],
            'membership_degrees': {
                self.config['features'][k]['column']: {t: float(v[0]) for t, v in terms.items()}
                for k, terms in p['memberships'].items()
            }
            if ok
            else {},
            'layers': layers,
            'activated_rules': layers['final']['activated_rules'] if ok else [],
            'explanation_data': {
                'message_key': 'task05.prediction.' + str(p['status'][0]),
                'layer_order': list(layers),
                'outside_training_range': [c for c, b in zip(self.columns, p['out_of_training_range'][0]) if b],
            },
            'explanation': (
                'Behavioral risk '
                + str(round(score, 2))
                + '; inspect module and final rule paths. Not an attack probability or attack attribution.'
            )
            if ok
            else 'Insufficient valid measurements or rule coverage; abstained.',
        }
