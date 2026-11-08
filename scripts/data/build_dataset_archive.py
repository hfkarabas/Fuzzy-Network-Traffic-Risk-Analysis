"""Inventory and create one complete lossless source Parquet from local HF cache."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import csv
import json
import platform
import subprocess
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
from fuzzy_network_risk.dataset_archive import source_batches,aligned_batches,write_archive,verify_archive,sha256,LABEL

R=ROOT/'reports/lfs'; T=ROOT/'.tmp/lfs'
ARCHIVE=ROOT/'datasets/cic_ids2017_v1.parquet'
MANIFEST=ROOT/'config/dataset_archive_v1.json'


def dump(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def inventory():
    rows=[]
    roots=[ROOT/'data',ROOT/'.cache/huggingface',ROOT/'.tmp/task04',ROOT/'.tmp/task05',ROOT/'.tmp/lfs',ROOT/'datasets']
    for root in roots:
        for path in sorted(root.rglob('*')):
            if not path.is_file(): continue
            relative=path.relative_to(ROOT).as_posix()
            if path.suffix not in ['.parquet','.arrow','.csv'] and path.parent.name!='blobs': continue
            kind=path.suffix.lstrip('.')
            if not kind:
                with path.open('rb') as f: magic=f.read(4)
                kind='CSV source blob' if magic.startswith(b' Des') or path.stat().st_size>10000 else 'metadata blob'
            if relative=='datasets/cic_ids2017_v1.parquet': role='SELECTED canonical complete lossless source; one LFS object'
            elif relative.startswith('.tmp/lfs/'): role='temporary archive/restore verification copy; do not track'
            elif 'snapshots/' in relative: role='alias of cached source blob; do not duplicate'
            elif '/blobs/' in relative: role='original CSV source bytes or metadata; preserve locally, do not track'
            elif kind=='arrow': role='datasets-library parsed source; canonical archive input, not tracked'
            elif relative.startswith('data/processed/v1/cleaned'): role='derived cleaned values/types; not lossless raw source'
            elif relative.startswith('data/processed'): role='derived projection/manifest; reproducible from source'
            elif 'predictions' in relative or 'oof' in relative or 'curve' in relative or 'scores' in relative: role='experiment output; do not track'
            else: role='derived sample/provenance/research cache; do not track'
            item={'path':relative,'bytes':path.stat().st_size,'format':kind,'is_alias':path.is_symlink(),
                  'role':role}
            if kind=='parquet':
                meta=pq.read_metadata(path); item.update(rows=meta.num_rows,columns=meta.num_columns)
            rows.append(item)
    dump(R/'inventory.json',rows)
    with (R/'inventory.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['path','bytes','format','is_alias','role','rows','columns'])
        writer.writeheader(); writer.writerows(rows)
    return rows


def main():
    R.mkdir(parents=True,exist_ok=True); T.mkdir(parents=True,exist_ok=True)
    if MANIFEST.exists(): raise FileExistsError('Manifest already frozen; use verify_dataset_archive.py instead. No source or archive is replaced.')
    inv=inventory()
    provenance=json.loads((ROOT/'reports/dataset/provenance.json').read_text(encoding='utf-8'))
    expected=json.loads((ROOT/'reports/dataset/source_integrity.json').read_text())
    paths=sorted(ROOT/p['path'] for p in expected if p['path'].endswith('.arrow'))
    assert len(paths)==4
    for path in paths:
        entry=next(p for p in expected if p['path']==path.relative_to(ROOT).as_posix())
        assert path.stat().st_size==entry['bytes'] and sha256(path)==entry['sha256']
    first=next(source_batches(paths)); schema=first.schema
    assert schema.names==provenance['splits']['train']['columns']
    pilot=[]
    for path in paths: pilot.append(next(aligned_batches(source_batches([path]))))
    results=[]
    for byte_split in [False,True]:
        path=T/('pilot_split.parquet' if byte_split else 'pilot_dictionary.parquet')
        result=({'rows':sum(map(len,pilot)),'bytes':path.stat().st_size,'sha256':sha256(path)}
                if path.exists() else write_archive(iter(pilot),path,schema,byte_split))
        # Pilot validates actual data including nulls and metadata before full work.
        actual=list(pq.ParquetFile(path).iter_batches(batch_size=65536))
        from fuzzy_network_risk.dataset_archive import assert_equal_batches
        for a,b in zip(pilot,actual): assert_equal_batches(a,b)
        result.update(byte_stream_split=byte_split,scope='262144 source rows; first 65536 from each Arrow shard, compression comparison only')
        results.append(result)
    dump(R/'compression_pilot.json',results)
    selected=min(results,key=lambda r:r['bytes'])['byte_stream_split']
    result=({'rows':pq.read_metadata(ARCHIVE).num_rows,'bytes':ARCHIVE.stat().st_size,'sha256':sha256(ARCHIVE)}
            if ARCHIVE.exists() else write_archive(source_batches(paths),ARCHIVE,schema,selected))
    check=verify_archive(paths,ARCHIVE,provenance['splits']['train']['rows'])
    classes={row['Label']:int(row['count']) for row in csv.DictReader((ROOT/'reports/dataset/classes.csv').open(encoding='utf-8'))}
    assert classes==check['labels'] and check['columns']==79
    result['labels']=check['labels']
    assert result['sha256']==check['sha256']
    origins=list(csv.DictReader((ROOT/'reports/dataset/source_files.csv').open(encoding='utf-8')))
    for row in origins:
        for key in ['start_row_inclusive','end_row_exclusive','rows']: row[key]=int(row[key])
    dataset=provenance['splits']['train']
    manifest={'version':'cic-ids2017-source-v1','artifact':ARCHIVE.relative_to(ROOT).as_posix(),
        'dataset_id':provenance['dataset_id'],'source_revision':provenance['revision'],'split':'train',
        'source_fingerprint':dataset['fingerprint'],'rows':result['rows'],'columns':len(schema),
        'schema':[{'name':f.name,'type':str(f.type),'nullable':f.nullable} for f in schema],
        'sha256':result['sha256'],'bytes':result['bytes'],'labels':result['labels'],
        'compression':'ZSTD level 9','byte_stream_split':selected,'row_group_rows':65536,
        'source_files':origins,'row_id':'zero-based original row position; never sorted or deduplicated',
        'preservation':'All parsed source values/types/labels, null masks, valid float bits and original Arrow schema metadata; not byte-identical original CSV text.',
        'software':{'python':platform.python_version(),'pyarrow':pa.__version__},
        'source_arrow_hashes':{p.name:sha256(p) for p in paths}}
    with MANIFEST.open('x',encoding='utf-8') as f: json.dump(manifest,f,indent=2,ensure_ascii=False,allow_nan=False)
    dump(R/'integrity.json',check)
    print(json.dumps({'archive':str(ARCHIVE),'bytes':result['bytes'],'rows':result['rows'],'columns':len(schema),'sha256':result['sha256'],'pilot':results},indent=2),flush=True)


if __name__=='__main__': main()
