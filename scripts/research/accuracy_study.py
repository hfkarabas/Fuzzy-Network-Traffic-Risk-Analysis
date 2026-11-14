"""Compare calibrated alert thresholds and training-only fuzzy rule weights."""

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from fuzzy_network_risk.advanced import COLUMNS, AdvancedRiskEngine, architecture_config
from fuzzy_network_risk.calibration import fit_config
from fuzzy_network_risk.data import INPUTS, LABEL
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.evaluation import binary_metrics
from fuzzy_network_risk.refinement import check_lineage, group_weights, roles, threshold_curve

CONFIG = ROOT / 'config/fuzzy/task04'
EXPOSURE = ROOT / 'data/fuzzy_v2/exposure_manifest.parquet'
EXPECTED_CACHE = 'a207592da666d8aac5b966145102278123b901f02447405b23aff5615c7aac2f'
MAX_CALIBRATION_FPR = 0.10
MIN_RECALL_GAIN = 0.05
MODELS = ('frozen', 'refit', 'weighted', 'hierarchy')


def truth(frame):
    return frame[LABEL].ne('BENIGN').to_numpy()


def fit_rule_weights(engine, training):
    """Attenuate rules whose training activations contradict their risk direction."""
    y = truth(training)
    if y.all() or not y.any():
        raise ValueError('Rule weighting requires both classes in training')
    prediction = engine.predict_batch(training[INPUTS])
    if not (prediction['status'] == 'ok').all():
        raise ValueError('Training requires valid scores')
    activations = prediction['rule_strengths']
    weights = group_weights(training)
    attack = np.average(activations[y], axis=0, weights=weights[y])
    benign = np.average(activations[~y], axis=0, weights=weights[~y])
    # Absolute activation differences limit the impact of rare rules.
    config = deepcopy(engine.config)
    config['version'] = 'accuracy-study-weighted-v1'
    for rule, delta in zip(config['rules'], attack - benign, strict=True):
        direction = {'Low': -1, 'Medium': 0, 'High': 1, 'Critical': 1}[rule['consequent']]
        rule['weight'] = float(1 - min(0.5, max(0.0, -direction * delta)))
    return MamdaniRiskEngine(config)


def select_threshold(y, scores, weights, objective):
    curve = threshold_curve(y, scores, weights).copy()
    if objective == 'balanced':
        curve = curve.loc[curve.fpr <= MAX_CALIBRATION_FPR + 1e-12].copy()
        curve['objective'] = (1 + curve.recall - curve.fpr) / 2
    elif objective == 'raw':
        curve['objective'] = (curve.tp + curve.tn) / weights.sum()
    else:
        raise ValueError('Unknown objective')
    if curve.empty:
        raise ValueError('No threshold satisfies the calibration constraint')
    return float(curve.sort_values(['objective', 'fpr', 'threshold'],
                                  ascending=[False, True, False]).iloc[0].threshold)


def infer(engine, frame, columns):
    result = engine.predict_batch(frame[columns])
    if not (result['status'] == 'ok').all():
        raise ValueError('Evaluation cohort contains unscorable records')
    return result['risk_score']


def evaluate_split(train, calibration, assess, partition):
    for field in ('source_row_id', 'signature', 'observation_group_id'):
        groups = [set(frame[field]) for frame in (train, calibration, assess)]
        if any(groups[i] & groups[j] for i, j in ((0, 1), (0, 2), (1, 2))):
            raise ValueError(f'Partition overlap on {field}')
    if any(not truth(frame).any() or truth(frame).all() for frame in (train, calibration, assess)):
        raise ValueError('Every role must contain both classes')
    frozen = MamdaniRiskEngine.load(CONFIG / 'selected_v4.json')
    deployed = json.loads((CONFIG / 'selected_policies.json').read_text(encoding='utf-8'))
    if deployed['model_id'] != frozen.model_id:
        raise ValueError('Frozen scoring model and policies disagree')
    refit = MamdaniRiskEngine(fit_config(train[INPUTS], 'accuracy-study'))
    models = {
        'frozen': frozen,
        'refit': refit,
        'weighted': fit_rule_weights(refit, train),
        'hierarchy': AdvancedRiskEngine(architecture_config(train, 'C_hierarchy')),
    }
    y_cal, y_assess = truth(calibration), truth(assess)
    w_cal, w_assess = group_weights(calibration), group_weights(assess)
    rows = []
    for name, engine in models.items():
        columns = COLUMNS if name == 'hierarchy' else INPUTS
        cal = infer(engine, calibration, columns)
        scores = infer(engine, assess, columns)
        options = {
            'balanced': select_threshold(y_cal, cal, w_cal, 'balanced'),
            'raw': select_threshold(y_cal, cal, np.ones(len(cal)), 'raw'),
        }
        if name == 'frozen':
            options['deployed'] = deployed['policies'][deployed['default_policy']]['threshold']
            options['always_benign'] = 100.0
        for policy, threshold in options.items():
            rows.append({
                'partition': partition, 'model': name, 'policy': policy,
                'model_id': engine.model_id,
                'calibration': binary_metrics(y_cal, cal, threshold, w_cal),
                'group_metrics': binary_metrics(y_assess, scores, threshold, w_assess),
                'row_metrics': binary_metrics(y_assess, scores, threshold),
            })
    return rows, {
        'partition': partition,
        'training_rows': len(train), 'calibration_rows': len(calibration),
        'assessment_rows': len(assess),
        'assessment_attacks': int(y_assess.sum()),
        'assessment_benign': int((~y_assess).sum()),
        'weighted_model': models['weighted'].config,
    }


def summarize(rows):
    fields = ('accuracy', 'balanced_accuracy', 'recall', 'false_positive_rate',
              'precision', 'f1', 'roc_auc', 'pr_auc_average_precision')
    summary = {}
    for model, policy in dict.fromkeys((r['model'], r['policy']) for r in rows):
        folds = [r for r in rows if r['partition'].startswith('fold')
                 and r['model'] == model and r['policy'] == policy]
        summary[f'{model}/{policy}'] = {
            'group_fold_mean': {key: float(np.mean([r['group_metrics'][key] for r in folds]))
                                for key in fields},
            'raw_fold_mean': {key: float(np.mean([r['row_metrics'][key] for r in folds]))
                              for key in fields},
            'pooled_raw_confusion': {
                key: int(sum(r['row_metrics']['confusion_matrix'][key] for r in folds))
                for key in ('tn', 'fp', 'fn', 'tp')
            },
        }
    return summary


def decision(rows, summary):
    """Require gains beyond both recalibration alone and the matching clean refit."""
    candidate = summary['weighted/balanced']['group_fold_mean']
    baselines = [summary[f'{name}/balanced']['group_fold_mean'] for name in ('frozen', 'refit')]
    internal_pass = all(
        candidate['recall'] >= baseline['recall'] + MIN_RECALL_GAIN
        and candidate['balanced_accuracy'] > baseline['balanced_accuracy']
        for baseline in baselines
    )
    day_rows = [r for r in rows if r['partition'].startswith('day_') and r['policy'] == 'balanced']
    refit = {r['partition']: r['group_metrics'] for r in day_rows if r['model'] == 'refit'}
    candidate_days = [r for r in day_rows if r['model'] == 'weighted']
    stability_pass = len(candidate_days) == 3 and all(
        row['group_metrics']['false_positive_rate'] <= MAX_CALIBRATION_FPR
        and row['group_metrics']['recall'] >= max(0.05, refit[row['partition']]['recall'] - 0.02)
        for row in candidate_days
    )
    return {'weighted_internal_gain': internal_pass, 'weighted_day_stability': stability_pass,
            'eligible_for_independent_validation': internal_pass and stability_pass,
            'production_change': False}


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def run(cache):
    cache_hash = sha256(cache)
    if cache_hash != EXPECTED_CACHE:
        raise ValueError('Use the original TASK05 eligible research cache')
    provenance = ['source_row_id', 'observation_group_id', 'signature']
    exposure_hash = sha256(EXPOSURE)
    data = pd.read_parquet(cache, columns=[*provenance, 'bucket', 'capture_day', LABEL, *COLUMNS])
    exposed = pd.read_parquet(EXPOSURE, columns=provenance)
    check_lineage(data, *(exposed[column] for column in provenance))
    if data.capture_day.eq('Friday').any():
        raise ValueError('Friday assessment records are excluded')
    panel = data.loc[data.bucket != 'design']
    results, splits = [], []
    for k in range(3):
        rows, split = evaluate_split(*roles(panel, k), f'fold_{k}')
        results.extend(rows)
        splits.append(split)
    for day in ('Tuesday', 'Wednesday', 'Thursday'):
        assess = panel.loc[panel.capture_day == day]
        rest = panel.loc[panel.capture_day != day]
        for key in provenance:
            rest = rest.loc[~rest[key].isin(assess[key])]
        split = rest.signature.map(
            lambda key: int(hashlib.sha256(f'{key}|task05-day'.encode()).hexdigest()[:8], 16) % 2
        )
        rows, info = evaluate_split(rest.loc[split == 0], rest.loc[split == 1], assess, f'day_{day}')
        results.extend(rows)
        splits.append(info)
    summary = summarize(results)
    return {
        'assessment_type': 'reused internal development, including capture-day stress',
        'cache_sha256': cache_hash, 'exposure_manifest_sha256': exposure_hash,
        'script_sha256': sha256(Path(__file__)),
        'frozen_config_sha256': sha256(CONFIG / 'selected_v4.json'),
        'frozen_policies_sha256': sha256(CONFIG / 'selected_policies.json'),
        'independent_test': False, 'splits': splits,
        'metrics': results, 'summary': summary, 'decision': decision(results, summary),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=ROOT / '.tmp/task05/research.parquet')
    parser.add_argument('--output', type=Path, required=True, help='New JSON report path')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('--output already exists')
    result = run(args.cache)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
