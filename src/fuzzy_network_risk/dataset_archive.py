"""Lossless source distribution and offline derivation, independent of models."""
from collections import Counter
from itertools import zip_longest
from pathlib import Path
import hashlib
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

LABEL=' Label'
BATCH_SIZE=65536


def sha256(path):
    with Path(path).open('rb') as handle: return hashlib.file_digest(handle,'sha256').hexdigest()


def source_batches(paths):
    """Read existing datasets-library Arrow streams without downloading anything."""
    for path in paths:
        with pa.memory_map(str(path),'r') as handle:
            yield from ipc.open_stream(handle)


def aligned_batches(batches,batch_size=BATCH_SIZE):
    if not isinstance(batch_size,int) or batch_size<1: raise ValueError('Positive batch size required')
    pending=[]; count=0
    for batch in batches:
        if not len(batch): continue
        pending.append(batch); count+=len(batch)
        if count>=batch_size:
            table=pa.Table.from_batches(pending).combine_chunks()
            while len(table)>=batch_size:
                yield table.slice(0,batch_size).to_batches()[0]
                table=table.slice(batch_size)
            pending=table.to_batches(); count=len(table)
    if count: yield pa.Table.from_batches(pending).combine_chunks().to_batches()[0]


def archive_options(byte_split=True):
    return {'compression':'zstd','compression_level':9,
            'use_dictionary':[LABEL] if byte_split else True,
            'use_byte_stream_split':byte_split,'version':'2.6','write_statistics':True}


def write_archive(batches,path,schema,byte_split=True,batch_size=BATCH_SIZE):
    """Exclusive create: an existing archive is never replaced."""
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    rows=0; labels=Counter()
    with path.open('xb') as handle:
        with pq.ParquetWriter(handle,schema,**archive_options(byte_split)) as writer:
            for batch in aligned_batches(batches,batch_size):
                if not batch.schema.equals(schema,check_metadata=True): raise ValueError('Source schema changed')
                writer.write_batch(batch,row_group_size=batch_size)
                rows+=len(batch)
                labels.update({v['values']:v['counts'] for v in pc.value_counts(batch.column(schema.get_field_index(LABEL))).to_pylist()})
    return {'rows':rows,'labels':dict(labels),'bytes':path.stat().st_size,'sha256':sha256(path)}


def assert_equal_batches(left,right):
    """Check null masks, exact integer/string values, and valid float64 bits.

    Float-bit equality distinguishes signed zero and preserves valid NaN payloads,
    infinities and negative measurements. Null values have no meaningful payload.
    """
    if len(left)!=len(right) or not left.schema.equals(right.schema,check_metadata=True):
        raise ValueError('Row count or schema mismatch')
    for i,field in enumerate(left.schema):
        a=left.column(i); b=right.column(i)
        mask=a.is_null().to_numpy(zero_copy_only=False)
        np.testing.assert_array_equal(mask,b.is_null().to_numpy(zero_copy_only=False),err_msg=field.name)
        if pa.types.is_floating(field.type):
            x=a.to_numpy(zero_copy_only=False); y=b.to_numpy(zero_copy_only=False)
            uint='uint64' if field.type.bit_width==64 else 'uint32'
            np.testing.assert_array_equal(x.view(uint)[~mask],y.view(uint)[~mask],err_msg=field.name)
        else:
            if not bool(pc.all(pc.fill_null(pc.equal(a,b),True)).as_py()): raise ValueError('Value mismatch: '+field.name)


def verify_archive(paths,archive,expected_rows=None):
    file=pq.ParquetFile(archive); rows=0; labels=Counter(); nonfinite=Counter(); negative=Counter()
    nulls=Counter(); nans=Counter(); positive_inf=Counter(); negative_inf=Counter()
    for source,actual in zip_longest(aligned_batches(source_batches(paths)),file.iter_batches(batch_size=BATCH_SIZE)):
        if source is None or actual is None: raise ValueError('Missing or extra batch')
        assert_equal_batches(source,actual); rows+=len(source)
        labels.update({v['values']:v['counts'] for v in pc.value_counts(actual.column(actual.schema.get_field_index(LABEL))).to_pylist()})
        for i,f in enumerate(actual.schema):
            nulls[f.name]+=actual.column(i).null_count
            if f.name==LABEL: continue
            a=actual.column(i).to_numpy(zero_copy_only=False)
            if pa.types.is_floating(f.type):
                valid=~actual.column(i).is_null().to_numpy(zero_copy_only=False)
                nonfinite[f.name]+=int((~np.isfinite(a)&valid).sum())
                nans[f.name]+=int((np.isnan(a)&valid).sum())
                positive_inf[f.name]+=int(np.isposinf(a).sum()); negative_inf[f.name]+=int(np.isneginf(a).sum())
            negative[f.name]+=int((a<0).sum())
    if expected_rows is not None and rows!=expected_rows: raise ValueError('Unexpected source rows')
    return {'status':'PASS','rows':rows,'columns':len(file.schema_arrow),'labels':dict(labels),
            'schema_including_metadata_equal':True,'all_values_and_row_order_exact':True,
            'float_bits_null_masks_signed_zero_preserved':True,
            'null_cells_preserved':{k:v for k,v in nulls.items() if v},
            'valid_nan_cells_preserved':{k:v for k,v in nans.items() if v},
            'positive_infinite_cells_preserved':{k:v for k,v in positive_inf.items() if v},
            'negative_infinite_cells_preserved':{k:v for k,v in negative_inf.items() if v},
            'nonfinite_cells_preserved':{k:v for k,v in nonfinite.items() if v},
            'negative_cells_preserved':{k:v for k,v in negative.items() if v},
            'sha256':sha256(archive),'bytes':Path(archive).stat().st_size}


def lfs_pointer(path,size,oid):
    """Validate only; never stages files or uploads objects."""
    content=Path(path).read_text(encoding='ascii')
    expected=f'version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {size}\n'
    return content==expected
