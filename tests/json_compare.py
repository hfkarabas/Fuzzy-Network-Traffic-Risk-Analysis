"""Structural comparison of JSON-like values with a floating-point tolerance.

Committed fixtures were captured on one platform. Transcendental functions such
as ``log1p`` may differ in the last unit of precision (ULP) between NumPy builds,
C libraries and CPU instruction sets, so bit-exact equality of derived floats is
not a portable regression criterion. Everything that is not a float is compared
exactly: keys, list lengths, strings, booleans (alerts), ``None`` (abstentions)
and integers (counts).
"""
import math

# Far below any modelled quantity (scores are reported to 2 decimals, membership
# degrees to 3) and far above cross-platform rounding noise (~1e-16 relative).
REL_TOL = 1e-9
ABS_TOL = 1e-12


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def json_differences(actual, expected, path='$', rel_tol=REL_TOL, abs_tol=ABS_TOL):
    """Return a list of human-readable differences; empty means equivalent."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f'{path}: expected object, got {type(actual).__name__}']
        problems = []
        missing, extra = expected.keys() - actual.keys(), actual.keys() - expected.keys()
        if missing:
            problems.append(f'{path}: missing keys {sorted(missing)}')
        if extra:
            problems.append(f'{path}: unexpected keys {sorted(extra)}')
        for key in expected.keys() & actual.keys():
            problems += json_differences(actual[key], expected[key], f'{path}.{key}', rel_tol, abs_tol)
        return problems
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)):
            return [f'{path}: expected array, got {type(actual).__name__}']
        if len(actual) != len(expected):
            return [f'{path}: expected {len(expected)} items, got {len(actual)}']
        problems = []
        for index, (a, e) in enumerate(zip(actual, expected)):
            problems += json_differences(a, e, f'{path}[{index}]', rel_tol, abs_tol)
        return problems
    if _is_number(expected) and _is_number(actual) and (isinstance(expected, float) or isinstance(actual, float)):
        if math.isnan(expected) or math.isnan(actual):
            return [] if math.isnan(expected) and math.isnan(actual) else [f'{path}: {actual!r} != {expected!r}']
        if math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol):
            return []
        return [f'{path}: {actual!r} != {expected!r} (beyond rel={rel_tol}, abs={abs_tol})']
    if type(actual) is not type(expected) or actual != expected:
        return [f'{path}: {actual!r} != {expected!r}']
    return []


def assert_json_close(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL):
    problems = json_differences(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol)
    assert not problems, 'JSON values differ:\n' + '\n'.join(problems[:20])
