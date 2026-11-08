"""Binary alert metrics with exact tied-score ROC/AP and optional group weights."""

import numpy as np


def binary_metrics(y_true, scores, threshold, weights=None):
    y = np.asarray(y_true, dtype=bool)
    s = np.asarray(scores, dtype='float64')
    w = np.ones(len(y)) if weights is None else np.asarray(weights, dtype='float64')
    if (
        y.shape != s.shape
        or w.shape != s.shape
        or not np.isfinite(s).all()
        or not np.isfinite(w).all()
        or (w < 0).any()
    ):
        raise ValueError('Metrics require aligned finite scores and nonnegative weights')
    predicted = s >= threshold
    tp = float(w[y & predicted].sum())
    fp = float(w[~y & predicted].sum())
    tn = float(w[~y & ~predicted].sum())
    fn = float(w[y & ~predicted].sum())

    def ratio(a, b):
        return float(a / b) if b else None

    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    # Precision of a detector that raises no alerts is conventionally zero.
    if precision is None:
        precision = 0.0
    result = {
        'rows': len(y),
        'weight': float(w.sum()),
        'threshold': float(threshold),
        'confusion_matrix': {'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp},
        'precision': precision,
        'recall': recall,
        'f1': ratio(2 * tp, 2 * tp + fp + fn),
        'false_positive_rate': ratio(fp, fp + tn),
        'false_negative_rate': ratio(fn, fn + tp),
        'balanced_accuracy': (recall + specificity) / 2 if recall is not None and specificity is not None else None,
        'accuracy': ratio(tp + tn, w.sum()),
        'roc_auc': None,
        'pr_auc_average_precision': None,
        'pr_auc_trapezoid': None,
    }
    positives = w[y].sum()
    negatives = w[~y].sum()
    if positives > 0:
        order = np.argsort(-s, kind='stable')
        sy = y[order]
        sw = w[order]
        ss = s[order]
        ends = np.r_[np.flatnonzero(ss[1:] != ss[:-1]), len(ss) - 1]
        tps = np.cumsum(sw * sy)[ends]
        fps = np.cumsum(sw * ~sy)[ends]
        rec = tps / positives
        prec = np.divide(tps, tps + fps, out=np.zeros_like(tps), where=(tps + fps) > 0)
        result['pr_auc_average_precision'] = float(np.sum(np.diff(np.r_[0.0, rec]) * prec))
        result['pr_auc_trapezoid'] = float(np.trapezoid(np.r_[1.0, prec], np.r_[0.0, rec]))
        if negatives > 0:
            result['roc_auc'] = float(np.trapezoid(np.r_[0.0, rec], np.r_[0.0, fps / negatives]))
    return result


def calibrate_alert(y, scores, candidates=(25.0, 35.0, 45.0, 55.0, 65.0, 75.0)):
    rows = [binary_metrics(y, scores, t) for t in candidates]
    if not rows or any(r['balanced_accuracy'] is None for r in rows):
        raise ValueError('Validation requires both benign and attack observations')
    best = max(rows, key=lambda r: (r['balanced_accuracy'], r['threshold']))
    return best['threshold'], rows
