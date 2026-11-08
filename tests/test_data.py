import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from fuzzy_network_risk.data import (
    INPUTS,
    LABEL,
    clean,
    detect_label,
    observation_ids,
    partitions,
    sample_development,
    validate_schema,
)


@pytest.fixture
def frame():
    f = pd.DataFrame({c: [0.0, 1.0, 10.0, 100.0, 1000.0, 3.0] for c in INPUTS})
    f[LABEL] = ['BENIGN', 'Attack', 'Rare', 'BENIGN', 'Attack', 'Rare']
    return f


def test_schema(frame):
    assert validate_schema(frame.columns) == LABEL


@pytest.mark.parametrize('columns', [['x'], ['Label', ' Label'], [' Label', ' Label']])
def test_bad_labels(columns):
    with pytest.raises(ValueError):
        detect_label(columns)


def test_label_detection_whitespace():
    assert detect_label(['value', ' Label']) == ' Label'


def test_missing_feature(frame):
    with pytest.raises(ValueError):
        validate_schema(frame.columns.drop(INPUTS[0]))


def test_duplicate_columns(frame):
    with pytest.raises(ValueError):
        validate_schema(list(frame.columns) + [INPUTS[0]])


def test_no_target_leakage(frame):
    assert LABEL not in INPUTS
    with pytest.raises(ValueError):
        validate_schema(frame.columns, INPUTS + [LABEL])


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf, -1.0, 'broken', None])
def test_invalid_measurement(frame, bad):
    c = INPUTS[0]
    frame[c] = frame[c].astype(object)
    frame.loc[1, c] = bad
    output, counts = clean(frame)
    assert pd.isna(output.loc[1, c])
    assert counts[c] == 1
    assert output[LABEL].equals(frame[LABEL])
    assert len(output) == len(frame)


def test_numeric_string_and_zero(frame):
    c = INPUTS[0]
    frame[c] = ['0', '1', '2', '3', '4', '1e20']
    output, counts = clean(frame)
    assert output[c].iloc[0] == 0 and output[c].iloc[-1] == 1e20
    assert counts[c] == 0


def test_dtype_and_reproducible_cleaning(frame):
    first, _ = clean(frame)
    second, _ = clean(frame)
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first, clean(first)[0])
    assert all(first[c].dtype == np.float64 for c in INPUTS)
    pd.testing.assert_frame_equal(frame, frame.copy())


def test_source_not_mutated(frame):
    frame.loc[0, INPUTS[0]] = -9
    before = frame.copy(deep=True)
    clean(frame)
    pd.testing.assert_frame_equal(frame, before)


def test_duplicate_policy_and_conflicting_labels(frame):
    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    duplicate.loc[len(duplicate) - 1, LABEL] = 'Contradictory'
    cleaned, _ = clean(duplicate)
    ids = observation_ids(cleaned)
    assert len(cleaned) == len(duplicate)
    assert ids[0] == ids[-1]
    assert partitions(ids)[0] == partitions(ids)[-1]


def test_grouping_is_batch_independent(frame):
    ids = observation_ids(clean(frame)[0])
    separate = np.concatenate([observation_ids(clean(frame.iloc[:3])[0]), observation_ids(clean(frame.iloc[3:])[0])])
    np.testing.assert_array_equal(ids, separate)


def test_missing_values_group(frame):
    frame.loc[0, INPUTS[0]] = np.nan
    frame.loc[1, INPUTS[0]] = -1
    for c in INPUTS[1:]:
        frame.loc[1, c] = frame.loc[0, c]
    ids = observation_ids(clean(frame)[0])
    assert ids[0] == ids[1]


def test_deterministic_sampling_and_rare_classes(frame):
    f = pd.concat([frame] * 20, ignore_index=True)
    f['source_row_id'] = np.arange(len(f))
    f['partition'] = partitions(observation_ids(frame).repeat(20))
    a = sample_development(f, per_class=9)
    b = sample_development(f, per_class=9)
    pd.testing.assert_frame_equal(a, b)
    assert set(a[LABEL]) == set(f[LABEL])
    assert not a.source_row_id.duplicated().any()


def test_sampling_is_independent_of_row_order_and_reservoir(frame):
    f = pd.concat([frame] * 100, ignore_index=True)
    f['source_row_id'] = np.arange(len(f))
    f['partition'] = 'train'
    expected = sample_development(f, per_class=20)
    shuffled = sample_development(f.sample(frac=1, random_state=3), per_class=20)
    pd.testing.assert_frame_equal(expected, shuffled)
    f['_priority'] = pd.util.hash_pandas_object(f.source_row_id ^ 20261103, index=False).to_numpy()
    reservoir = f.sort_values('_priority').groupby([LABEL, 'partition'], sort=False).head(20)
    pd.testing.assert_frame_equal(expected, sample_development(reservoir, per_class=20))


def test_round_trip(frame, tmp_path):
    clean_frame, _ = clean(frame)
    clean_frame.loc[0, INPUTS[0]] = np.nan
    path = tmp_path / 'tiny.parquet'
    pq.write_table(pa.Table.from_pandas(clean_frame, preserve_index=False), path)
    pd.testing.assert_frame_equal(clean_frame, pq.read_table(path).to_pandas())


def test_loading_interface(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import acquire
    import huggingface_hub

    import datasets

    (tmp_path / 'reports/dataset').mkdir(parents=True)
    monkeypatch.setattr(acquire, 'ROOT', tmp_path)
    monkeypatch.delenv('HF_HUB_OFFLINE', raising=False)
    monkeypatch.delenv('DATASET_REVISION', raising=False)
    part = datasets.Dataset.from_dict({LABEL: ['BENIGN'], 'value': [1.0]})
    calls = []

    def fake_load(*args, **kwargs):
        calls.append((args, kwargs))
        return datasets.DatasetDict(train=part)

    monkeypatch.setattr(datasets, 'load_dataset', fake_load)
    monkeypatch.setattr(
        huggingface_hub,
        'HfApi',
        lambda: SimpleNamespace(dataset_info=lambda *a, **k: SimpleNamespace(sha='fixture-revision')),
    )
    result = acquire.acquire()
    assert len(result['train']) == 1
    assert calls == [(('c01dsnap/CIC-IDS2017',), {})]
    assert (tmp_path / 'reports/dataset/provenance.json').exists()
