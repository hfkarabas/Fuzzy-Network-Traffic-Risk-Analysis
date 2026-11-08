"""Small cached data access, Python inference adapter and display serialization."""

import csv
import json
from pathlib import Path

import numpy as np

from .. import __version__
from ..config_integrity import frozen_text_matches
from ..engine import MamdaniRiskEngine
from ..membership import membership
from ..policy import PolicyRiskModel
from .content import FEATURES, LEVELS, POLICIES, TERMS, condition_text, rule_text

ROOT = Path(__file__).resolve().parents[3]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


class WebService:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        config = self.root / 'config/fuzzy/task04'
        self.engine = MamdaniRiskEngine.load(config / 'selected_v4.json')
        self.policy_config = read_json(config / 'selected_policies.json')
        manifest = read_json(config / 'selected_manifest.json')
        self.manifest = manifest
        for filename, key in [('selected_v4.json', 'model_sha256'), ('selected_policies.json', 'policy_sha256')]:
            if not frozen_text_matches((config / filename).read_bytes(), manifest[key]):
                raise ValueError('Frozen configuration content hash mismatch')
        if self.engine.model_id != manifest['model_id']:
            raise ValueError('Frozen model identity mismatch')
        self.models = {name: PolicyRiskModel(self.engine, self.policy_config, name) for name in POLICIES}
        self.catalog = read_json(self.root / 'web/catalog/examples.json')
        if self.catalog['model_id'] != self.engine.model_id:
            raise ValueError('Example catalog model mismatch')
        # Small metrics/JSON only. No datasets library, Arrow, or Parquet access at runtime.
        self.evaluation = self._evaluation()
        self.model = self._metadata()
        self.examples = []
        for item in self.catalog['examples']:
            actual = self.models[item['reference_policy']].predict_one(item['features'])
            if (
                actual['risk_score'] != item['risk_score']
                or actual['risk_level'] != item['risk_level']
                or actual['alert'] != item['alert']
            ):
                raise ValueError('Catalog prediction differs from frozen engine')
            self.examples.append(item)

    def policy_list(self):
        return [
            {
                'id': name,
                **POLICIES[name],
                'threshold': model.threshold,
                'policy_id': model.policy_id,
                'fpr_target': model.settings['fpr_cap'],
                'weighting': 'signature_group_weighted',
            }
            for name, model in self.models.items()
        ]

    def _metadata(self):
        provenance = read_json(self.root / 'reports/dataset/provenance.json')
        with (self.root / 'reports/dataset/classes.csv').open(encoding='utf-8', newline='') as handle:
            class_count = len(list(csv.DictReader(handle)))
        features = []
        for display in FEATURES:
            spec = self.engine.config['features'][display['key']]
            upper = spec['upper']
            # Actual memberships are evaluated in Python. A log display axis for
            # packet size improves readability without changing inference.
            coordinates = np.unique(
                np.r_[np.linspace(0, upper, 241), [v for s in spec['sets'].values() for v in s['parameters']]]
            )
            raw = np.expm1(coordinates) if spec['transform'] == 'log1p' else coordinates
            positions = np.log1p(raw) / np.log1p(upper) if display['key'] == 'size' else coordinates / upper
            curves = [
                {'term': term, 'title': TERMS[term], 'degrees': membership(coordinates, mf).tolist()}
                for term, mf in spec['sets'].items()
            ]
            features.append(
                {
                    **display,
                    'training_min': spec['training_min'],
                    'training_max': spec['training_max'],
                    'transform': spec['transform'],
                    'chart': {
                        'positions': positions.tolist(),
                        'values': raw.tolist(),
                        'curves': curves,
                        'axis_label': 'Display axis: log(1+x)'
                        if display['key'] == 'size' or spec['transform'] == 'log1p'
                        else 'Linear axis',
                    },
                }
            )
        rules = [
            {
                'id': r['id'],
                'conditions': condition_text(r['antecedent']),
                'consequent': r['consequent'],
                'text': rule_text(r['antecedent'], r['consequent']),
            }
            for r in self.engine.config['rules']
        ]
        return {
            'title': 'Fuzzy Logic-Based Network Traffic Risk Analysis',
            'app_version': __version__,
            'model_id': self.engine.model_id,
            'model_version': self.manifest['model_version'],
            'configuration_version': self.manifest['configuration_version'],
            'method': 'Mamdani',
            'and': 'Minimum',
            'or': 'Maximum',
            'implication': 'Minimum clipping',
            'aggregation': 'Maximum',
            'defuzzification': 'Centroid',
            'output_grid_points': len(self.engine.grid),
            'rule_count': len(rules),
            'features': features,
            'rules': rules,
            'terms': TERMS,
            'levels': LEVELS,
            'risk_category_cuts': self.engine.config['risk_level_thresholds'],
            'dataset': {
                'id': provenance['dataset_id'],
                'records': sum(p['rows'] for p in provenance['splits'].values()),
                'columns': len(provenance['splits']['train']['columns']),
                'labels': class_count,
                'revision': provenance['revision'],
            },
            'notice': 'For education and experimentation. Not a reliable operational intrusion detection system.',
        }

    def analyze(self, features, policy):
        result = self.models[policy].predict_one(features)
        result['model_version'] = self.model['model_version']
        result['input_values'] = features
        result['validation_errors'] = []
        result['input_positions'] = {}
        for r in result['activated_rules']:
            r['conditions'] = condition_text(r['antecedent'])
            r['text'] = rule_text(r['antecedent'], r['consequent'])
        if result['status'] == 'ok':
            for f in FEATURES:
                spec = self.engine.config['features'][f['key']]
                value = features[f['column']]
                z = float(np.log1p(value)) if spec['transform'] == 'log1p' else value
                z = min(max(z, 0.0), spec['upper'])
                position = float(np.log1p(z) / np.log1p(spec['upper'])) if f['key'] == 'size' else z / spec['upper']
                result['input_positions'][f['column']] = position
            top = result['activated_rules'][:3]

            def degree_text(value):
                return '<0.001' if 0 < value < 0.001 else f'{value:.3f}'

            result['explanation'] = f'{LEVELS[result["risk_level"]]} risk: {result["risk_score"]:.2f}/100. ' + ' '.join(
                f'{r["id"]} ({degree_text(r["strength"])}): {r["conditions"]}.' for r in top
            )
            result['explanation'] += ' These behaviors do not establish attack type or attack probability.'
        else:
            result['explanation'] = 'Insufficient valid measurements; the system abstained from producing a risk score.'
            result['validation_errors'] = [
                {'field': c, 'message': 'A finite, nonnegative number is required.'}
                for c in result['explanation_data']['invalid_features']
            ]
        return result

    def _evaluation(self):
        old = read_json(self.root / 'reports/fuzzy/metrics.json')
        scenarios = []
        for key, title, description in [
            ('grouped', 'Historical grouped test', 'Class-quota development sample; 91.43% attack traffic.'),
            (
                'day',
                'Historical day-based test',
                'Monday–Wednesday training, Thursday validation, Friday test; scenario shift is present.',
            ),
        ]:
            m = old[key]['row_weighted']
            scenarios.append(
                {
                    'id': key,
                    'title': title,
                    'scope': 'historical_test',
                    'description': description,
                    'weighting': 'Flow-weighted',
                    'metrics': m,
                    'confusion': m['confusion_matrix'],
                    'confusion_weighting': 'Flow counts from the same test',
                    'source': 'reports/fuzzy/metrics.json',
                }
            )
        with (self.root / 'reports/fuzzy/task02b/comparison_summary.csv').open(encoding='utf-8', newline='') as handle:
            summaries = list(csv.DictReader(handle))
        internal = []
        for row in summaries:
            if row['candidate'] != 'A_frozen':
                continue
            keys = [
                'precision',
                'recall',
                'f1',
                'false_positive_rate',
                'false_negative_rate',
                'balanced_accuracy',
                'roc_auc',
                'pr_auc_average_precision',
            ]
            internal.append(
                {
                    'id': row['policy'],
                    'metrics': {k: float(row[k]) for k in keys},
                    'confusion': {k: int(row['row_' + k]) for k in ['tn', 'fp', 'fn', 'tp']},
                    'rows': int(row['benign_rows']) + int(row['attack_rows']),
                    'benign_rows': int(row['benign_rows']),
                    'attack_rows': int(row['attack_rows']),
                    'pooled_row_fpr': float(row['pooled_row_fpr']),
                    'pooled_row_recall': float(row['pooled_row_recall']),
                }
            )
        with (self.root / 'reports/fuzzy/task04/comparison.csv').open(encoding='utf-8', newline='') as handle:
            comparisons = [row for row in csv.DictReader(handle) if row['policy'] == 'Balanced']
        optimization = {
            'version': 'TASK 04',
            'selected_candidate': self.manifest['candidate'],
            'model_id': self.engine.model_id,
            'scope': 'Reused internal validation, not independent testing. Group-weighted mean of three folds.',
            'conclusion': 'No candidate passed the promotion criterion. The scoring model and existing alert policies were retained unchanged.',
            'source': 'reports/fuzzy/task04/comparison.csv',
            'candidates': [
                {
                    'id': r['candidate'],
                    'precision': float(r['precision']),
                    'recall': float(r['recall']),
                    'fpr': float(r['false_positive_rate']),
                    'balanced_accuracy': float(r['balanced_accuracy']),
                    'balanced_accuracy_fold_sd': float(r['balanced_accuracy_fold_sd']),
                    'roc_auc': float(r['roc_auc']),
                    'benign_rows': int(r['benign_rows']),
                    'attack_rows': int(r['attack_rows']),
                }
                for r in comparisons
            ],
        }
        return {
            'historical': scenarios,
            'internal': internal,
            'optimization': optimization,
            'active_model_id': self.engine.model_id,
            'internal_model_id': self.engine.model_id,
            'internal_scope': 'TASK 02B · retained model · signature-group-weighted mean of three folds',
            'internal_confusion_scope': 'Pooled raw flow counts with separate fold thresholds; not the matrix of group-weighted rates.',
            'independent_holdout': False,
            'source': 'reports/fuzzy/task02b/comparison_summary.csv',
            'limitations': [
                'The historical grouped test has a 76% false-positive rate.',
                'The historical day-based test missed almost all attacks at threshold 75.',
                'Internal validation is not independent final testing; no credible untouched holdout exists.',
                'Class/scenario shift, duplicate/near-duplicate dependence and the limited five-input representation remain.',
                'Policy FPR targets are signature-group-weighted; they do not guarantee flow-weighted error rates.',
                'Improvement candidates failed the promotion criterion; the original scoring model was retained.',
            ],
        }
