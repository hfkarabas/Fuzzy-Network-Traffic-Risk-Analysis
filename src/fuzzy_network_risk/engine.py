"""Explainable CPU Mamdani inference. Target labels are never accepted as inputs."""

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from .data import INPUTS
from .membership import centroid, fuzzy_and, fuzzy_or, membership

LEVELS = ['Low', 'Medium', 'High', 'Critical']


def _numeric_value(value):
    if not isinstance(value, (int, float, np.integer, np.floating)) or isinstance(value, (bool, np.bool_)):
        return np.nan
    try:
        return float(value)
    except (OverflowError, TypeError, ValueError):
        return np.nan


def config_digest(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()


def evaluate_expression(expression, degrees):
    if 'feature' in expression:
        return degrees[expression['feature']][expression['term']]
    if 'all' in expression:
        return fuzzy_and(*(evaluate_expression(e, degrees) for e in expression['all']))
    if 'any' in expression:
        return fuzzy_or(*(evaluate_expression(e, degrees) for e in expression['any']))
    raise ValueError('Invalid antecedent expression')


class MamdaniRiskEngine:
    def __init__(self, config):
        self.config = deepcopy(config)
        self._validate()
        self.model_id = config_digest(self.config)
        self.feature_keys = list(self.config['features'])
        self.columns = [self.config['features'][k]['column'] for k in self.feature_keys]
        self.grid = np.linspace(0, 100, self.config['output']['grid_points'])
        self.output_sets = np.stack([membership(self.grid, self.config['output']['sets'][level]) for level in LEVELS])

    def _validate(self):
        cfg = self.config
        if cfg.get('method') != 'mamdani-min-max-centroid':
            raise ValueError('Unsupported inference method')
        features = cfg['features']
        columns = [v['column'] for v in features.values()]
        if len(columns) != 5 or set(columns) != set(INPUTS):
            raise ValueError('Model must use exactly the five approved behavior inputs')
        if len(set(columns)) != 5:
            raise ValueError('Duplicate feature columns')
        for f in features.values():
            if f['transform'] not in ['identity', 'log1p'] or not np.isfinite(f['upper']) or f['upper'] <= 0:
                raise ValueError('Invalid feature transform/domain')
            for spec in f['sets'].values():
                membership(np.array([0.0, f['upper']]), spec)

        def check(e):
            if set(e) == {'feature', 'term'}:
                if e['feature'] not in features or e['term'] not in features[e['feature']]['sets']:
                    raise ValueError('Unknown rule feature/term')
            elif len(e) == 1 and next(iter(e)) in ['all', 'any'] and len(next(iter(e.values()))) > 0:
                for child in next(iter(e.values())):
                    check(child)
            else:
                raise ValueError('Malformed rule expression')

        ids = []
        for r in cfg['rules']:
            check(r['antecedent'])
            if r['consequent'] not in LEVELS or not 0 < r.get('weight', 1) <= 1:
                raise ValueError('Invalid rule consequent/weight')
            ids.append(r['id'])
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate rule IDs')
        for level in LEVELS:
            membership(np.array([0.0, 100.0]), cfg['output']['sets'][level])
        if not isinstance(cfg['output']['grid_points'], int) or cfg['output']['grid_points'] < 3:
            raise ValueError('Insufficient output quadrature grid')
        cuts = cfg['risk_level_thresholds']
        if len(cuts) != 3 or not 0 < cuts[0] < cuts[1] < cuts[2] < 100:
            raise ValueError('Invalid category thresholds')
        if not 0 <= cfg['alert_threshold'] <= 100:
            raise ValueError('Invalid alert threshold')

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

    def save(self, path):
        Path(path).write_text(json.dumps(self.config, indent=2, allow_nan=False), encoding='utf-8')

    def _coerce(self, records):
        if isinstance(records, Mapping):
            records = [records]
        frame = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
        if not frame.columns.is_unique or set(frame.columns) - set(self.columns):
            raise ValueError('Only the five approved input columns are accepted; remove labels and metadata')
        matrix = np.full((len(frame), 5), np.nan)
        for j, c in enumerate(self.columns):
            if c in frame:
                # Booleans and numeric strings are not physical numerical measurements.
                values = frame[c]
                if values.dtype.kind in 'iuf':
                    matrix[:, j] = values.to_numpy(dtype='float64', na_value=np.nan)
                else:
                    matrix[:, j] = [_numeric_value(v) for v in values]
        return matrix

    def predict_batch(self, records, batch_size=2048):
        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError('batch_size must be positive')
        x = self._coerce(records)
        if not len(x):
            return {
                'risk_score': np.empty(0),
                'risk_level': np.empty(0, dtype=object),
                'status': np.empty(0, dtype=object),
                'rule_strengths': np.empty((0, len(self.config['rules']))),
                'memberships': {},
                'out_of_training_range': np.empty((0, 5), bool),
            }
        chunks = [self._infer(x[i : i + batch_size]) for i in range(0, len(x), batch_size)]
        result = {
            k: np.concatenate([c[k] for c in chunks])
            for k in ['risk_score', 'risk_level', 'status', 'rule_strengths', 'out_of_training_range']
        }
        result['memberships'] = {
            f: {
                term: np.concatenate([c['memberships'][f][term] for c in chunks])
                for term in chunks[0]['memberships'][f]
            }
            for f in self.feature_keys
        }
        return result

    def _infer(self, x, include_output=False):
        valid = (np.isfinite(x) & (x >= 0)).all(axis=1)
        safe = np.where(np.isfinite(x) & (x >= 0), x, 0.0)
        degrees = {}
        outside = np.zeros_like(x, dtype=bool)
        for j, key in enumerate(self.feature_keys):
            f = self.config['features'][key]
            outside[:, j] = (safe[:, j] < f['training_min']) | (safe[:, j] > f['training_max'])
            z = np.log1p(safe[:, j]) if f['transform'] == 'log1p' else safe[:, j]
            z = np.clip(z, 0, f['upper'])
            degrees[key] = {term: np.where(valid, membership(z, spec), 0.0) for term, spec in f['sets'].items()}
        strengths = (
            np.stack(
                [evaluate_expression(r['antecedent'], degrees) * r.get('weight', 1.0) for r in self.config['rules']],
                axis=1,
            )
            if self.config['rules']
            else np.zeros((len(x), 0))
        )
        heights = np.zeros((len(x), 4))
        for j, r in enumerate(self.config['rules']):
            k = LEVELS.index(r['consequent'])
            heights[:, k] = np.maximum(heights[:, k], strengths[:, j])
        aggregate = np.zeros((len(x), len(self.grid)))
        for k in range(4):
            aggregate = np.maximum(aggregate, np.minimum(heights[:, k, None], self.output_sets[k]))
        scores = centroid(self.grid, aggregate)
        scores = np.clip(scores, 0, 100)
        scores[~valid] = np.nan
        status = np.where(~valid, 'invalid_input', np.where(np.isfinite(scores), 'ok', 'no_rule_activation'))
        levels = np.full(len(x), None, dtype=object)
        ok = np.isfinite(scores)
        levels[ok] = np.asarray(LEVELS, dtype=object)[
            np.searchsorted(self.config['risk_level_thresholds'], scores[ok], side='right')
        ]
        result = {
            'risk_score': scores,
            'risk_level': levels,
            'status': status,
            'rule_strengths': strengths,
            'memberships': degrees,
            'out_of_training_range': outside & valid[:, None],
        }
        if include_output:
            result['output_aggregate'] = aggregate
        return result

    def output_visualization(self, record):
        """Read-only single-record view of the actual inference grid/aggregate.

        Normal prediction contracts and numerical operations remain unchanged.
        Invalid/no-rule cases expose no misleading membership/centroid plot.
        """
        matrix = self._coerce(record)
        if len(matrix) != 1:
            raise ValueError('Output visualization requires one record')
        result = self._infer(matrix, include_output=True)
        status = str(result['status'][0])
        valid = status == 'ok'
        return {
            'status': status,
            'model_id': self.model_id,
            'centroid': float(result['risk_score'][0]) if valid else None,
            'grid': self.grid.tolist() if valid else [],
            'curves': [{'level': level, 'degrees': self.output_sets[i].tolist()} for i, level in enumerate(LEVELS)]
            if valid
            else [],
            'aggregate': result['output_aggregate'][0].tolist() if valid else [],
        }

    def predict_one(self, record):
        result = self.predict_batch(record)
        if len(result['status']) != 1:
            raise ValueError('predict_one requires exactly one record')
        status = str(result['status'][0])
        score = float(result['risk_score'][0]) if status == 'ok' else None
        rules = []
        if status == 'ok':
            for j, r in enumerate(self.config['rules']):
                strength = float(result['rule_strengths'][0, j])
                if strength > 0:
                    rules.append(
                        {
                            'id': r['id'],
                            'strength': strength,
                            'consequent': r['consequent'],
                            'antecedent': r['antecedent'],
                            'reason_key': f'rules.{r["id"]}',
                            'rationale_en': r['rationale'],
                        }
                    )
        rules.sort(key=lambda r: (-r['strength'], r['id']))
        memberships = (
            {
                self.config['features'][k]['column']: {term: float(v[0]) for term, v in terms.items()}
                for k, terms in result['memberships'].items()
            }
            if status == 'ok'
            else {}
        )
        issues = []
        if status == 'invalid_input':
            matrix = self._coerce(record)
            issues = [self.columns[j] for j in range(5) if not np.isfinite(matrix[0, j]) or matrix[0, j] < 0]
        outside = [self.columns[j] for j in range(5) if result['out_of_training_range'][0, j]]
        tokens = {
            'message_key': f'prediction.{status}',
            'dominant_rules': [r['id'] for r in rules[:3]],
            'invalid_features': issues,
            'outside_training_range': outside,
            'measurement_caveat_keys': [
                'measurement.integer_direction_ratio',
                'measurement.zero_variation_ambiguous',
                'risk.not_probability',
            ],
            'risk_level_key': f'risk.{str(result["risk_level"][0]).lower()}' if status == 'ok' else None,
        }
        text = (
            (
                f'{result["risk_level"][0]} risk ({score:.2f}/100). Strongest behavior rules: '
                + ', '.join(f'{r["id"]} -> {r["consequent"]} ({r["strength"]:.2f})' for r in rules[:3])
                + '. These patterns do not establish an attack type or probability. The integer direction ratio does not establish absence of responses.'
            )
            if status == 'ok'
            else (
                'Insufficient valid numerical input; no risk score was produced.'
                if status == 'invalid_input'
                else 'No rule activated; the system abstained instead of assigning a low score.'
            )
        )
        return {
            'status': status,
            'risk_score': score,
            'risk_level': result['risk_level'][0],
            'alert': bool(score >= self.config['alert_threshold']) if score is not None else None,
            'activated_rules': rules,
            'membership_degrees': memberships,
            'explanation_data': tokens,
            'explanation': text,
            'model_id': self.model_id,
        }
