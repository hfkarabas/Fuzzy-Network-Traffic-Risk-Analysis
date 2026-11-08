"""Vectorized triangular/trapezoidal memberships with explicit shoulder endpoints."""

import numpy as np


def trapezoid(x, a, b, c, d):
    if not all(np.isfinite([a, b, c, d])) or not a <= b <= c <= d or a == d:
        raise ValueError('Trapezoid requires finite a <= b <= c <= d and a < d')
    x = np.asarray(x, dtype='float64')
    left = np.ones_like(x) if a == b else np.clip((x - a) / (b - a), 0, 1)
    right = np.ones_like(x) if c == d else np.clip((d - x) / (d - c), 0, 1)
    return np.where((x >= a) & (x <= d), np.minimum(left, right), 0.0)


def triangle(x, a, b, c):
    if not a <= b <= c or a == c:
        raise ValueError('Triangle requires a <= b <= c and a < c')
    return trapezoid(x, a, b, b, c)


def membership(x, spec):
    if spec['kind'] == 'triangle':
        return triangle(x, *spec['parameters'])
    if spec['kind'] == 'trapezoid':
        return trapezoid(x, *spec['parameters'])
    raise ValueError('Unknown membership kind')


def fuzzy_and(*values):
    return np.minimum.reduce(values)


def fuzzy_or(*values):
    return np.maximum.reduce(values)


def centroid(x, aggregated):
    """Trapezoidal quadrature; zero area returns NaN, never a fabricated low score."""
    x = np.asarray(x, dtype='float64')
    y = np.asarray(aggregated, dtype='float64')
    if x.ndim != 1 or len(x) < 2 or not np.all(np.diff(x) > 0) or y.shape[-1] != len(x):
        raise ValueError('Invalid integration grid')
    area = np.trapezoid(y, x, axis=-1)
    moment = np.trapezoid(y * x, x, axis=-1)
    return np.divide(moment, area, out=np.full_like(area, np.nan), where=area > 0)
