"""Offline, bounded reconstruction of existing v1 data paths from Git LFS source.

Writes only into an empty destination. Existing original outputs are never
overwritten. No download, source repair, model fitting or remote Git operation.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import argparse
from collections import Counter
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb
from fuzzy_network_risk.data import clean,observation_ids,partitions,sample_development,INPUTS,LABEL,SEED
from fuzzy_network_risk.dataset_archive import sha256


def restore(archive,manifest,destination,verify_hash=True):
    archive=Path(archive); destination=Path(destination)
    if verify_hash and sha256(archive)!=manifest['sha256']:
        raise ValueError('Archive hash mismatch or LFS pointer not downloaded')
    source=pq.ParquetFile(archive)
    if source.metadata.num_rows!=manifest['rows'] or len(source.schema_arrow)!=manifest['columns']:
        raise ValueError('Archive dimensions differ')
    if destination.exists() and any(destination.iterdir()): raise FileExistsError('Destination must be empty; original data is never overwritten')
    processed=destination/'processed/v1'; samples=destination/'samples'; interim=destination/'interim'
    for path in [processed,samples,interim]: path.mkdir(parents=True,exist_ok=True)
    writers={}; offset=0; reservoir=None; transformed=Counter()
    for batch in source.iter_batches(batch_size=65536):
        f,counts=clean(batch.to_pandas()); transformed.update(counts)
        ids=observation_ids(f)
        f['source_row_id']=np.arange(offset,offset+len(f),dtype='int64'); f['observation_group_id']=ids
        f['partition']=partitions(ids,SEED); f['fuzzy_eligible']=f[INPUTS].notna().all(axis=1)&f[LABEL].notna()
        fuzzy=f.loc[f.fuzzy_eligible,INPUTS+[LABEL,'source_row_id','observation_group_id','partition']].copy()
        for name,frame in [('cleaned',f),('fuzzy_ready',fuzzy)]:
            table=pa.Table.from_pandas(frame,preserve_index=False)
            if name not in writers: writers[name]=pq.ParquetWriter(processed/(name+'.parquet'),table.schema,compression='zstd')
            writers[name].write_table(table)
        fuzzy['_priority']=pd.util.hash_pandas_object(fuzzy.source_row_id^SEED,index=False).to_numpy()
        candidate=pd.concat([reservoir,fuzzy],ignore_index=True) if reservoir is not None else fuzzy
        reservoir=candidate.sort_values('_priority').groupby([LABEL,'partition'],sort=False).head(1000)
        offset+=len(f)
    for writer in writers.values(): writer.close()
    assert offset==manifest['rows']
    development=sample_development(reservoir,1000,SEED)
    development.to_parquet(samples/'development_v1.parquet',index=False)
    # Ordered source ranges are tracked metadata, avoiding redundant source CSVs.
    origins=manifest['source_files']; expected_start=0; origin_rows=[]
    for origin in origins:
        if origin['start_row_inclusive']!=expected_start or origin['end_row_exclusive']-expected_start!=origin['rows']:
            raise ValueError('Invalid source-file range metadata')
        origin_rows.append({'start_row':expected_start,'end_row':origin['end_row_exclusive'],
            'source_file':origin['source_file'],'capture_day':origin['capture_day']})
        expected_start=origin['end_row_exclusive']
    assert expected_start==offset
    con=duckdb.connect(); con.execute("SET memory_limit='1GB'"); con.execute('SET threads=2')
    # File paths are passed as relation parameters, not interpolated into SQL.
    con.read_parquet(str(processed/'cleaned.parquet')).create_view('cleaned')
    con.register('origin_ranges',pd.DataFrame(origin_rows))
    con.sql('SELECT source_row_id,observation_group_id,partition,fuzzy_eligible FROM cleaned').write_parquet(str(processed/'split_manifest.parquet'),compression='zstd')
    con.execute('''CREATE VIEW origins AS SELECT c.source_row_id,r.source_file,r.capture_day FROM cleaned c
        JOIN origin_ranges r ON c.source_row_id>=r.start_row AND c.source_row_id<r.end_row''')
    con.sql('SELECT * FROM origins ORDER BY source_row_id').write_parquet(str(interim/'source_origins.parquet'),compression='zstd')
    con.execute('''CREATE VIEW nominal AS SELECT o.*,c.observation_group_id,c.fuzzy_eligible,
        CASE WHEN o.capture_day IN ('Monday','Tuesday','Wednesday') THEN 'train'
        WHEN o.capture_day='Thursday' THEN 'validation' ELSE 'test' END AS nominal_temporal_partition
        FROM origins o JOIN cleaned c USING(source_row_id)''')
    con.sql('''SELECT n.*,CASE WHEN g.partitions>1 THEN 'quarantine' ELSE nominal_temporal_partition END AS temporal_partition
        FROM nominal n JOIN (SELECT observation_group_id,count(DISTINCT nominal_temporal_partition) partitions
        FROM nominal GROUP BY observation_group_id) g USING(observation_group_id) ORDER BY source_row_id''').write_parquet(str(processed/'source_sessions.parquet'),compression='zstd')
    result={'status':'PASS','source_rows':offset,'source_columns':manifest['columns'],
        'fuzzy_ready_rows':pq.read_metadata(processed/'fuzzy_ready.parquet').num_rows,
        'development_rows':len(development),'transformation_cells':dict(transformed),'seed':SEED,
        'destination':str(destination),'downloaded':False,'overwritten_existing_files':False,
        'note':'Logical values/schema/IDs/partitions reproduced. Parquet byte hashes may vary with writer row groups and software; original file hashes remain historical provenance.'}
    con.close()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--destination',default='data')
    args=parser.parse_args()
    manifest=json.loads((ROOT/'config/dataset_archive_v1.json').read_text(encoding='utf-8'))
    result=restore(ROOT/manifest['artifact'],manifest,ROOT/args.destination)
    print(json.dumps(result,indent=2,ensure_ascii=False))
