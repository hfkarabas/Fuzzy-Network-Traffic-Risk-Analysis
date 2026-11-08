"""Recover coarse capture-day provenance from the already-downloaded source CSVs.

This is metadata recovery, NOT an alternate dataset acquisition route. Every
numerical value and label is checked against the required datasets-loaded table.
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_DATASETS_OFFLINE']='1'
from acquire import acquire, ROOT
import sys
sys.path.insert(0,str(ROOT/'src'))
from fuzzy_network_risk.data import LABEL
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb

def recover(table=None):
    if table is None:
        table=acquire()['train'].data.table
    prov=json.loads((ROOT/'reports/dataset/provenance.json').read_text(encoding='utf-8'))
    files=list(prov['splits']['train']['download_checksums'])
    snapshot=ROOT/'.cache/huggingface/hub/datasets--c01dsnap--CIC-IDS2017/snapshots'/prov['revision']
    offset=0
    origins=[]
    writer=None
    intermediate=ROOT/'data/interim/source_origins.parquet'
    for url in files:
        name=url.rsplit('/',1)[1]
        day=name.split('-')[0]
        before=offset
        dtypes={f.name:('str' if f.name==LABEL else str(f.type)) for f in table.schema}
        for frame in pd.read_csv(snapshot/name,chunksize=65536,dtype=dtypes,encoding_errors='replace'):
            expected=table.slice(offset,len(frame)).to_pandas()
            assert list(frame.columns)==table.column_names
            assert frame[LABEL].tolist()==expected[LABEL].tolist()
            for c in table.column_names:
                if c!=LABEL:
                    np.testing.assert_allclose(frame[c].to_numpy(),expected[c].to_numpy(),rtol=0,atol=0,equal_nan=True)
            metadata=pd.DataFrame({'source_row_id':np.arange(offset,offset+len(frame),dtype='int64'),
                                   'source_file':name,'capture_day':day})
            arrow=pa.Table.from_pandas(metadata,preserve_index=False)
            if writer is None:
                writer=pq.ParquetWriter(intermediate,arrow.schema,compression='zstd')
            writer.write_table(arrow)
            offset+=len(frame)
        origins.append({'source_file':name,'capture_day':day,'start_row_inclusive':before,'end_row_exclusive':offset,'rows':offset-before})
        print(f'Verified source origin: {name}, {offset-before:,} rows',flush=True)
    writer.close()
    assert offset==len(table)
    con=duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET temp_directory='data/interim/duckdb'")
    con.execute('''CREATE VIEW nominal AS SELECT o.*, m.observation_group_id,m.fuzzy_eligible,
      CASE WHEN capture_day IN ('Monday','Tuesday','Wednesday') THEN 'train'
           WHEN capture_day='Thursday' THEN 'validation' ELSE 'test' END AS nominal_temporal_partition
      FROM read_parquet('data/interim/source_origins.parquet') o
      JOIN read_parquet('data/processed/v1/split_manifest.parquet') m USING(source_row_id)''')
    con.execute('''COPY (SELECT n.*, CASE WHEN g.partitions>1 THEN 'quarantine'
      ELSE nominal_temporal_partition END AS temporal_partition FROM nominal n JOIN
      (SELECT observation_group_id,count(DISTINCT nominal_temporal_partition) partitions FROM nominal GROUP BY observation_group_id) g
      USING(observation_group_id) ORDER BY source_row_id)
      TO 'data/processed/v1/source_sessions.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)''')
    counts=con.execute("SELECT temporal_partition,count(*) AS rows,sum(fuzzy_eligible::INTEGER) AS fuzzy_eligible_rows FROM read_parquet('data/processed/v1/source_sessions.parquet') GROUP BY temporal_partition ORDER BY temporal_partition").df()
    counts.to_csv(ROOT/'reports/dataset/temporal_partitions.csv',index=False)
    groups=con.execute("SELECT count(*) FROM (SELECT observation_group_id FROM read_parquet('data/processed/v1/source_sessions.parquet') WHERE temporal_partition!='quarantine' GROUP BY observation_group_id HAVING count(DISTINCT temporal_partition)>1)").fetchone()[0]
    assert groups==0
    con.execute('''COPY (SELECT s.capture_day,s.temporal_partition,c." Label" AS Label,count(*) AS rows
      FROM read_parquet('data/processed/v1/source_sessions.parquet') s JOIN read_parquet('data/processed/v1/cleaned.parquet') c USING(source_row_id)
      GROUP BY ALL ORDER BY capture_day,temporal_partition,Label) TO 'reports/dataset/temporal_classes.csv' (HEADER, DELIMITER ',')''')
    pd.DataFrame(origins).to_csv(ROOT/'reports/dataset/source_files.csv',index=False)
    result={'status':'PASS','rows_verified':offset,'all_original_numeric_values_and_labels_exactly_matched':True,
            'source_files':len(origins),'nonquarantined_groups_crossing_temporal_partitions':int(groups),
            'policy':'Monday/Tuesday/Wednesday train; Thursday validation; Friday test; entire groups spanning nominal partitions quarantined',
            'counts':counts.to_dict(orient='records')}
    (ROOT/'reports/dataset/session_recovery.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    recover()
