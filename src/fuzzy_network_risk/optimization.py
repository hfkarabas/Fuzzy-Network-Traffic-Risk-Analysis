"""TASK04 bounded, auditable fuzzy candidates; no evaluation-data fitting."""

from copy import deepcopy

import numpy as np

from .calibration import KEYS, fit_config
from .data import INPUTS

CANDIDATES = ['A_frozen', 'A_refit', 'B_group_membership', 'C_context_rules', 'D_combined']


def context_rules(rules):
    """Preserve rules/IDs except the explicitly documented context changes."""
    result = deepcopy(rules)
    for r in result:
        if r['id'] == 'R07':
            r['consequent'] = 'Low'
            r['rationale'] = (
                'Few-packet rate spikes can be short-duration artifacts; require corroborating volume before escalation.'
            )
        if r['id'] == 'R19':
            r['consequent'] = 'Low'
            r['rationale'] = (
                'Small forward-only short transactions alone are weak risk evidence; scans can evade this conservative choice.'
            )
        if r['id'] in ['R10', 'R11']:
            r['antecedent']['all'].append({'feature': 'volume', 'term': 'many'})
            r['rationale'] += ' TASK04 additionally requires many forward packets; tiny bursts alone are insufficient.'
    return result


def candidate_config(training, name, frozen):
    if name not in CANDIDATES:
        raise ValueError('Unknown TASK04 candidate')
    if name == 'A_frozen':
        return deepcopy(frozen)
    if not {'signature', *INPUTS}.issubset(training.columns):
        raise ValueError('Training provenance and exact inputs required')
    # Equal-signature reference prevents heavily repeated flows from defining
    # linguistic anchors. Median of each group is a physical feature measurement,
    # not a label-derived score. The group ID is never an inference input.
    reference = training[INPUTS]
    if name in ['B_group_membership', 'D_combined']:
        reference = training.groupby('signature', sort=True)[INPUTS].median()
    config = fit_config(reference, 'task04-' + name)
    config['version'] = 'task04-v1-' + name
    config['fit_rows'] = len(training)
    config['reference_rows'] = len(reference)
    config['reference_basis'] = (
        'equal_signature_medians' if name in ['B_group_membership', 'D_combined'] else 'training_rows'
    )
    for key, column in zip(KEYS, INPUTS, strict=True):
        config['features'][key]['training_min'] = float(training[column].min())
        config['features'][key]['training_max'] = float(training[column].max())
        f = config['features'][key]
        upper = float(np.log1p(training[column].max())) if f['transform'] == 'log1p' else float(training[column].max())
        f['upper'] = max(upper, f['upper'])
        high = list(f['sets'])[-1]
        f['sets'][high]['parameters'][-2:] = [f['upper'], f['upper']]
    if name in ['C_context_rules', 'D_combined']:
        config['rules'] = context_rules(config['rules'])
    return config


def select_model(summary, intervals):
    """Require practical and paired-bootstrap gain over both comparison baselines."""
    baselines = ['A_refit', 'A_frozen']
    eligible = []
    for name in CANDIDATES[2:]:
        s = summary[name]
        if s['fpr'] > 0.075:
            continue
        if all(
            s['balanced_accuracy'] - summary[b]['balanced_accuracy'] >= 0.02
            and intervals[name][b]['paired_balanced_accuracy_difference_95'][0] > 0
            for b in baselines
        ):
            eligible.append(name)
    return (
        max(eligible, key=lambda n: (summary[n]['balanced_accuracy'], -CANDIDATES.index(n))) if eligible else 'A_frozen'
    )
