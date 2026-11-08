"""The fixture comparator tolerates ULP noise only, never semantic changes."""

import pytest
from json_compare import assert_json_close, json_differences


def test_last_ulp_float_noise_is_accepted():
    expected = {'input_positions': {' Flow Packets/s': 0.011440515912416904}, 'risk_score': 51.80923685003131}
    actual = {'input_positions': {' Flow Packets/s': 0.011440515912416906}, 'risk_score': 51.809236850031304}
    assert_json_close(actual, expected)


@pytest.mark.parametrize(
    'actual,expected',
    [
        ({'risk_score': 51.81}, {'risk_score': 51.80923685}),  # score drift beyond tolerance
        ({'alert': False}, {'alert': True}),  # alert decision
        ({'alert': 1}, {'alert': True}),  # bool is not a number
        ({'risk_level': 'Medium'}, {'risk_level': 'High'}),  # linguistic level
        ({'risk_score': None}, {'risk_score': 0.0}),  # abstention vs score
        ({'count': 3}, {'count': 4}),  # integers are exact
        ({'rules': ['R01']}, {'rules': ['R01', 'R02']}),  # list length
        ({'a': 1}, {'a': 1, 'b': 2}),  # missing key
        ({'a': 1, 'b': 2}, {'a': 1}),  # unexpected key
        ([{'x': [1.0, 2.0]}], [{'x': [1.0, 2.1]}]),  # nested difference
    ],
)
def test_semantic_differences_are_rejected(actual, expected):
    assert json_differences(actual, expected)
    with pytest.raises(AssertionError):
        assert_json_close(actual, expected)


def test_nan_matches_only_nan():
    assert not json_differences(float('nan'), float('nan'))
    assert json_differences(0.0, float('nan'))
