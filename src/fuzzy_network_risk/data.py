"""Pure, testable data rules. No fitted transformations or inference engine."""

import numpy as np
import pandas as pd

SEED = 20261103
INPUTS = [' Flow Packets/s', ' Total Fwd Packets', ' Packet Length Mean', ' Bwd Packet Length Std', ' Down/Up Ratio']
LABEL = ' Label'


def detect_label(columns):
    matches = [c for c in columns if c.strip().casefold() == 'label']
    if len(matches) != 1:
        raise ValueError('Expected exactly one Label column')
    return matches[0]


def validate_schema(columns, inputs=INPUTS):
    if len(columns) != len(set(columns)):
        raise ValueError('Duplicate column names')
    label = detect_label(columns)
    if label in inputs or any(c.strip().casefold() == 'label' for c in inputs):
        raise ValueError('Target leakage into fuzzy inputs')
    if not set(inputs).issubset(columns):
        raise ValueError('Missing fuzzy input columns')
    return label


def clean(frame):
    """Retain every row; null invalid measurements, keep labels verbatim.

    Negative window values include -1 unknown sentinels; all negative numeric
    measurements are unavailable rather than imputed. Original rows remain in HF.
    """
    label = detect_label(frame.columns)
    result = frame.copy()
    counts = {}
    for c in frame.columns:
        if c == label:
            continue
        numeric = pd.to_numeric(frame[c], errors='coerce').astype('float64')
        invalid = ~np.isfinite(numeric) | (numeric < 0)
        counts[c] = int(invalid.sum())
        result[c] = numeric.mask(invalid)
    return result, counts


def observation_ids(frame):
    """Conservative grouping: identical input observations always share an ID.

    Pandas 64-bit hashes can merge unrelated observations through collisions;
    this cannot split identical observations between evaluation partitions.
    The full pipeline independently counts exact duplicates using all columns.
    """
    columns = [c for c in frame if c != detect_label(frame.columns)]
    return pd.util.hash_pandas_object(frame[columns], index=False).to_numpy(dtype='uint64')


def partitions(ids, seed=SEED):
    # SplitMix64 provides deterministic mixing, avoiding modulo artifacts.
    with np.errstate(over='ignore'):
        z = np.asarray(ids, dtype='uint64') + np.uint64(seed)
        z = (z ^ (z >> 30)) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> 27)) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> 31)
    bucket = z % 100
    return np.where(bucket < 70, 'train', np.where(bucket < 85, 'validation', 'test'))


def sample_development(frame, per_class=1000, seed=SEED):
    """Uniform hash-priority sample within label AND partition, preserving rare strata.

    The streaming pipeline passes a capped reservoir with precomputed priorities;
    synthetic/unit callers can supply an ordinary frame with source row IDs.
    """
    frame = frame.copy()
    if '_priority' not in frame:
        frame['_priority'] = pd.util.hash_pandas_object(frame.source_row_id ^ seed, index=False).to_numpy()
    parts = []
    for (_, partition), group in frame.groupby([LABEL, 'partition'], sort=True):
        proportion = {'train': 0.70, 'validation': 0.15, 'test': 0.15}[partition]
        n = min(len(group), max(1, round(per_class * proportion)))
        parts.append(group.nsmallest(n, '_priority'))
    result = pd.concat(parts).sort_values('source_row_id').reset_index(drop=True) if parts else frame.iloc[:0].copy()
    return result.drop(columns='_priority')
