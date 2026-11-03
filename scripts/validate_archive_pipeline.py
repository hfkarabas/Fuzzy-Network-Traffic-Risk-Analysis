"""Validate full offline reconstruction against untouched existing v1 outputs."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from itertools import zip_longest
import json
import subprocess
import pyarrow as pa
import pyarrow.parquet as pq
from fuzzy_network_risk.dataset_archive import assert_equal_batches,sha256


def main():
    copied=ROOT/'.tmp/lfs/offline_restore_validation'
    paths=['processed/v1/cleaned.parquet','processed/v1/fuzzy_ready.parquet','processed/v1/split_manifest.parquet',
        'processed/v1/source_sessions.parquet','samples/development_v1.parquet','interim/source_origins.parquet']
    checks=[]
    for relative in paths:
        original=ROOT/'data'/relative; reconstructed=copied/relative
        a=pq.ParquetFile(original); b=pq.ParquetFile(reconstructed)
        assert a.metadata.num_rows==b.metadata.num_rows and a.schema_arrow.names==b.schema_arrow.names
        original_hash=sha256(original); restored_hash=sha256(reconstructed)
        schema_equal=a.schema_arrow.equals(b.schema_arrow,check_metadata=False)
        if original_hash!=restored_hash:
            for left,right in zip_longest(a.iter_batches(batch_size=65536),b.iter_batches(batch_size=65536)):
                assert left is not None and right is not None
                # Only Arrow string/large-string offset widths may differ for
                # derived provenance. Numeric source/processed types stay exact.
                for x,y in zip(left.schema,right.schema):
                    assert x.type==y.type or (pa.types.is_string(x.type) or pa.types.is_large_string(x.type)) and (pa.types.is_string(y.type) or pa.types.is_large_string(y.type))
                right=right.cast(left.schema)
                assert_equal_batches(left,right)
        checks.append({'file':relative,'rows':a.metadata.num_rows,'columns':len(a.schema_arrow),
            'all_values_and_order_equal':True,'physical_field_types_equal':schema_equal,
            'file_bytes_identical':original_hash==restored_hash,'original_sha256':original_hash,'restored_sha256':restored_hash})
        print('Validated offline:',relative,flush=True)
    # Preserve exact hashes of all historical raw cache/processed artifacts.
    historical=json.loads((ROOT/'reports/web/historical_integrity.json').read_text())
    for path,expected in historical.items(): assert sha256(ROOT/path)==expected,path
    # Model/web source and ALL historical reports/configs stay untouched.
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','b7f566c7a54d8467a5833ed7687a3973c346742c'],cwd=ROOT,text=True).splitlines()
    protected=[p for p in tracked if p.startswith(('config/','reports/','src/','web/','scripts/','tests/'))]
    for path in protected:
        old=subprocess.check_output(['git','show','b7f566c:'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==old.replace(b'\r\n',b'\n'),path
    result={'status':'PASS','source_archive_only_restore':True,'downloaded':False,'original_outputs_overwritten':False,
        'files':checks,'source_rows':2830743,'fuzzy_ready_rows':2827761,'development_rows':11720,
        'historical_hashes_unchanged':len(historical),'prior_tracked_source_reports_configs_unchanged':len(protected),
        'limitation':'HF CSV/Arrow byte-integrity validators still require their original optional cache; archived source has its own complete SHA256/bitwise validation. Restore checks logical data, not a promise of identical regenerated Parquet bytes on every software version.'}
    (ROOT/'reports/lfs/pipeline_compatibility.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
