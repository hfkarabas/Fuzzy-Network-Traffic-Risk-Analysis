"""Lossless source semantics, exclusive writes, offline restore and LFS pointers."""

import json
import subprocess
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
import pytest
from restore_dataset_archive import restore
from verify_dataset_archive import verify

from fuzzy_network_risk.data import INPUTS, LABEL
from fuzzy_network_risk.dataset_archive import (
    aligned_batches,
    assert_equal_batches,
    lfs_pointer,
    sha256,
    source_batches,
    verify_archive,
    write_archive,
)


@pytest.fixture
def source(tmp_path):
    columns = {c: pa.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]) for c in INPUTS}
    columns[' raw integer'] = pa.array([-1, 0, 1, 2, 3, 2**62], type=pa.int64())
    columns[' raw float'] = pa.array([np.nan, np.inf, -np.inf, -0.0, None, -1.0], type=pa.float64(), from_pandas=False)
    columns[LABEL] = pa.array(['BENIGN', 'Rare', 'BENIGN', 'Attack', 'BENIGN', 'Ünïcødé ✓ �'])
    table = pa.table(columns).replace_schema_metadata({b'provenance': b'synthetic immutable fixture'})
    path = tmp_path / 'source.arrow'
    with pa.OSFile(str(path), 'wb') as f:
        with ipc.new_stream(f, table.schema) as writer:
            writer.write_table(table, max_chunksize=2)
    return path, table


@pytest.mark.parametrize('byte_split', [False, True])
def test_exact_source_roundtrip(source, tmp_path, byte_split):
    path, table = source
    target = tmp_path / 'source.parquet'
    result = write_archive(source_batches([path]), target, table.schema, byte_split, batch_size=3)
    check = verify_archive([path], target, 6)
    assert result['sha256'] == check['sha256'] and check['columns'] == 8
    assert check['null_cells_preserved'][' raw float'] == 1
    assert check['valid_nan_cells_preserved'][' raw float'] == 1
    assert check['positive_infinite_cells_preserved'][' raw float'] == 1
    assert check['negative_infinite_cells_preserved'][' raw float'] == 1
    restored = pq.read_table(target)
    assert np.signbit(restored[' raw float'][3].as_py())
    assert restored[' raw integer'][-1].as_py() == 2**62
    assert restored[LABEL][-1].as_py() == 'Ünïcødé ✓ �'


def test_existing_dataset_is_never_overwritten(source, tmp_path):
    path, table = source
    target = tmp_path / 'existing.parquet'
    target.write_bytes(b'protected')
    with pytest.raises(FileExistsError):
        write_archive(source_batches([path]), target, table.schema)
    assert target.read_bytes() == b'protected'


def test_alignment_preserves_order_across_input_chunks(source):
    path, table = source
    batches = list(aligned_batches(source_batches([path]), 4))
    assert [len(b) for b in batches] == [4, 2]
    actual = pa.Table.from_batches(batches).combine_chunks().to_batches()[0]
    assert_equal_batches(table.combine_chunks().to_batches()[0], actual)
    with pytest.raises(ValueError):
        list(aligned_batches([], 0))


def test_bitwise_checker_rejects_signed_zero_change(source):
    _, table = source
    changed = table.set_column(
        table.schema.get_field_index(' raw float'),
        ' raw float',
        pa.array([np.nan, np.inf, -np.inf, 0.0, None, -1.0], type=pa.float64(), from_pandas=False),
    )
    with pytest.raises(AssertionError):
        assert_equal_batches(table.to_batches()[0], changed.to_batches()[0])


def test_clone_verifier_rejects_pointer_and_wrong_hash(source, tmp_path):
    path, table = source
    archive = tmp_path / 'source.parquet'
    result = write_archive(source_batches([path]), archive, table.schema)
    manifest = {
        'rows': 6,
        'bytes': result['bytes'],
        'sha256': result['sha256'],
        'labels': result['labels'],
        'columns': len(table.schema),
        'schema': [{'name': f.name, 'type': str(f.type), 'nullable': f.nullable} for f in table.schema],
    }
    assert verify(archive, manifest)['status'] == 'PASS'
    with pytest.raises(ValueError, match='SHA256'):
        verify(archive, {**manifest, 'sha256': '0' * 64})
    pointer = tmp_path / 'pointer'
    pointer.write_text(
        f'version https://git-lfs.github.com/spec/v1\noid sha256:{result["sha256"]}\nsize {result["bytes"]}\n',
        encoding='ascii',
        newline='\n',
    )
    assert lfs_pointer(pointer, result['bytes'], result['sha256'])
    with pytest.raises(ValueError, match='LFS pointer'):
        verify(pointer, manifest)


def test_offline_restore_and_refusal_to_replace_originals(source, tmp_path):
    path, table = source
    archive = tmp_path / 'source.parquet'
    result = write_archive(source_batches([path]), archive, table.schema)
    manifest = {
        **result,
        'columns': len(table.schema),
        'source_files': [
            {
                'source_file': 'synthetic.csv',
                'capture_day': 'Monday',
                'start_row_inclusive': 0,
                'end_row_exclusive': 6,
                'rows': 6,
            }
        ],
    }
    output = tmp_path / 'output'
    restored = restore(archive, manifest, output)
    assert restored['source_rows'] == 6 and not restored['overwritten_existing_files']
    cleaned = pq.read_table(output / 'processed/v1/cleaned.parquet')
    assert cleaned[LABEL].to_pylist() == table[LABEL].to_pylist()
    assert cleaned[' raw float'].null_count == 5
    assert cleaned['source_row_id'].to_pylist() == list(range(6))
    before = sha256(output / 'processed/v1/cleaned.parquet')
    with pytest.raises(FileExistsError):
        restore(archive, manifest, output)
    assert sha256(output / 'processed/v1/cleaned.parquet') == before


def test_repository_tracks_only_canonical_artifact_through_lfs():
    root = Path(__file__).resolve().parents[1]
    canonical = 'datasets/cic_ids2017_v1.parquet'
    result = subprocess.check_output(['git', 'check-attr', 'filter', 'text', '--', canonical], cwd=root, text=True)
    assert 'filter: lfs' in result and 'text: unset' in result
    assert subprocess.run(['git', 'check-ignore', '--no-index', '-q', canonical], cwd=root).returncode == 1
    for path in [
        'datasets/redundant.parquet',
        'data/processed/v1/cleaned.parquet',
        '.cache/copy.arrow',
        '.tmp/duplicate.parquet',
    ]:
        assert subprocess.run(['git', 'check-ignore', '--no-index', '-q', path], cwd=root).returncode == 0


def test_manifest_preserves_full_source_and_quota_gate():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'config/dataset_archive_v1.json').read_text(encoding='utf-8'))
    quota = json.loads((root / 'reports/lfs/quota_check.json').read_text())
    assert manifest['rows'] == 2830743 and manifest['columns'] == 79 and len(manifest['labels']) == 15
    assert sum(manifest['labels'].values()) == manifest['rows']
    assert manifest['bytes'] == quota['selected_object_bytes'] < quota['per_file_limit_conservative_bytes']
    assert quota['file_size_and_current_capacity_compatible'] and not quota['billing_settings_changed']
