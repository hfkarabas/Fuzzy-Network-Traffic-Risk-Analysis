"""Apply a versioned operating policy without mutating fuzzy scoring parameters."""

import json
from pathlib import Path

import numpy as np

from .engine import MamdaniRiskEngine, config_digest


class PolicyRiskModel:
    def __init__(self, engine, policy_config, policy=None):
        if policy_config['model_id'] != engine.model_id:
            raise ValueError('Policy/model identity mismatch')
        self.engine = engine
        self.name = policy or policy_config['default_policy']
        if self.name not in policy_config['policies']:
            raise ValueError('Unknown operating policy')
        self.settings = dict(policy_config['policies'][self.name])
        self.threshold = float(self.settings['threshold'])
        if not np.isfinite(self.threshold) or not 0 <= self.threshold <= 100:
            raise ValueError('Invalid policy threshold')
        self.policy_id = config_digest({'model_id': engine.model_id, 'name': self.name, 'settings': self.settings})

    @classmethod
    def load(cls, model_path, policy_path, policy=None):
        return cls(
            MamdaniRiskEngine.load(model_path), json.loads(Path(policy_path).read_text(encoding='utf-8')), policy
        )

    def predict_one(self, record):
        result = self.engine.predict_one(record)
        result['alert'] = bool(result['risk_score'] >= self.threshold) if result['status'] == 'ok' else None
        result['alert_policy'] = {
            'name': self.name,
            'threshold': self.threshold,
            'policy_id': self.policy_id,
            'calibration_fpr_target': self.settings['fpr_cap'],
            'target_weighting': 'signature_group_weighted',
            'target_is_not_a_guarantee': True,
        }
        return result

    def predict_batch(self, records, batch_size=2048):
        result = self.engine.predict_batch(records, batch_size)
        alerts = np.full(len(result['risk_score']), None, dtype=object)
        valid = result['status'] == 'ok'
        alerts[valid] = result['risk_score'][valid] >= self.threshold
        result['alert'] = alerts
        result['policy_id'] = self.policy_id
        return result
