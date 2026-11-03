"""Read-only downloaded-object verification; no network, fitting or data writes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
from collections import Counter
import json
import pyarrow.compute as pc
import pyarrow.parquet as pq
from fuzzy_network_risk.dataset_archive import sha256,LABEL


def verify(archive,manifest):
    archive=Path(archive)
    with archive.open('rb') as f:
        if f.read(4)!=b'PAR1': raise ValueError('Parquet content is absent or this is an LFS pointer; finish the GitHub Desktop LFS download first')
    if archive.stat().st_size!=manifest['bytes'] or sha256(archive)!=manifest['sha256']:
        raise ValueError('Archive size/SHA256 mismatch')
    file=pq.ParquetFile(archive)
    schema=[{'name':f.name,'type':str(f.type),'nullable':f.nullable} for f in file.schema_arrow]
    if schema!=manifest['schema'] or file.metadata.num_rows!=manifest['rows']:
        raise ValueError('Source schema/count mismatch')
    counts=Counter()
    for batch in file.iter_batches(batch_size=65536,columns=[LABEL]):
        counts.update({v['values']:v['counts'] for v in pc.value_counts(batch.column(0)).to_pylist()})
    if dict(counts)!=manifest['labels']: raise ValueError('Label counts differ')
    return {'status':'PASS','rows':file.metadata.num_rows,'columns':len(schema),'labels':dict(counts),
            'bytes':archive.stat().st_size,'sha256':manifest['sha256'],'downloaded':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--manifest',default='config/dataset_archive_v1.json')
    args=parser.parse_args(); manifest=json.loads((ROOT/args.manifest).read_text(encoding='utf-8'))
    print(json.dumps(verify(ROOT/manifest['artifact'],manifest),indent=2,ensure_ascii=False))
