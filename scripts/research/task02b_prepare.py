"""Metadata/signature exclusion before any eligible feature or label diagnostics."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import hashlib
import duckdb
from fuzzy_network_risk.data import INPUTS
from fuzzy_network_risk.refinement import assignment,check_lineage,SEED

REPORT=ROOT/'reports/fuzzy/task02b'
DATA=ROOT/'data/fuzzy_v2'

def prepare():
    protocol=json.loads((ROOT/'config/fuzzy/task02b_protocol.json').read_text())
    c=duckdb.connect(); c.execute("SET memory_limit='1GB'"); c.execute('SET threads=2'); c.execute("SET temp_directory='data/interim/duckdb'")
    c.execute("CREATE VIEW f AS SELECT * FROM read_parquet('data/processed/v1/fuzzy_ready.parquet')")
    c.execute("CREATE VIEW s AS SELECT * FROM read_parquet('data/processed/v1/source_sessions.parquet')")
    c.execute("CREATE VIEW d AS SELECT source_row_id,partition FROM read_parquet('data/samples/development_v1.parquet')")
    components=[f'CAST(CAST(floor(ln(1+f."{col}")/.1+.5) AS BIGINT) AS VARCHAR)' for col in INPUTS[:4]]
    components.append('CAST(CAST(f." Down/Up Ratio" AS BIGINT) AS VARCHAR)')
    expression="concat_ws(':',"+','.join(components)+')'
    # Exposure construction selects NO target labels, scores, errors or attack classes.
    c.execute(f'''CREATE TABLE lineage AS SELECT f.source_row_id,f.observation_group_id,s.source_file,s.capture_day,
      s.temporal_partition,f.partition AS old_grouped_partition,{expression} AS signature,
      (s.capture_day='Friday' OR coalesce(d.partition='test',false)) AS exposed_record
      FROM f JOIN s USING(source_row_id) LEFT JOIN d USING(source_row_id)''')
    assert c.execute('SELECT count(*) FROM (SELECT observation_group_id FROM lineage GROUP BY observation_group_id HAVING count(DISTINCT signature)>1)').fetchone()[0]==0
    c.execute('CREATE TABLE blocked_signatures AS SELECT DISTINCT signature FROM lineage WHERE exposed_record')
    c.execute('CREATE TABLE blocked_groups AS SELECT DISTINCT observation_group_id FROM lineage WHERE exposed_record')
    c.execute('''CREATE TABLE eligible AS SELECT l.* FROM lineage l
      ANTI JOIN blocked_signatures b USING(signature) ANTI JOIN blocked_groups g USING(observation_group_id)''')
    c.execute("COPY (SELECT * FROM lineage WHERE exposed_record) TO 'data/fuzzy_v2/exposure_manifest.parquet' (FORMAT PARQUET,COMPRESSION ZSTD)")
    c.execute("COPY (SELECT * FROM eligible ORDER BY source_row_id) TO 'data/fuzzy_v2/eligible_manifest.parquet' (FORMAT PARQUET,COMPRESSION ZSTD)")
    c.execute(f"CREATE TABLE sampled AS SELECT *,sha256(CAST(source_row_id AS VARCHAR)||'|{SEED}') AS priority FROM eligible ORDER BY priority LIMIT {protocol['maximum_sample_rows']}")
    selected=c.execute('SELECT * EXCLUDE(priority) FROM sampled ORDER BY source_row_id').df()
    selected['bucket']=selected.signature.map(assignment)
    # Audited assertions against metadata-only exposure, before joining labels.
    exposed=c.execute('SELECT source_row_id,observation_group_id,signature FROM lineage WHERE exposed_record').df()
    check_lineage(selected,exposed.source_row_id,exposed.observation_group_id,exposed.signature)
    assert not selected.capture_day.eq('Friday').any()
    c.register('selected',selected)
    extra=[' Flow Duration',' Flow IAT Mean',' Flow IAT Std','Flow Bytes/s',' Total Backward Packets',
           ' SYN Flag Count',' ACK Flag Count',' PSH Flag Count',' Fwd Header Length',' min_seg_size_forward']
    columns=','.join('c."'+col+'"' for col in INPUTS+extra+[' Label'])
    # Only now access source labels/extra features, exclusively for eligible rows.
    development=c.execute(f"SELECT sel.*,{columns} FROM selected sel JOIN read_parquet('data/processed/v1/cleaned.parquet') c USING(source_row_id) ORDER BY source_row_id").df()
    development.to_parquet(DATA/'internal_development.parquet',index=False)
    selected.to_parquet(DATA/'sample_lineage.parquet',index=False)
    counts=development.groupby(['bucket','capture_day',' Label']).size().rename('rows').reset_index()
    counts.to_csv(REPORT/'partition_classes.csv',index=False)
    totals={name:int(c.execute(f'SELECT count(*) FROM {name}').fetchone()[0]) for name in ['lineage','blocked_signatures','blocked_groups','eligible']}
    totals['direct_exposed_records']=int(c.execute('SELECT count(*) FROM lineage WHERE exposed_record').fetchone()[0])
    totals['excluded_rows']=totals['lineage']-totals['eligible']
    totals['additional_linked_rows_excluded']=totals['excluded_rows']-totals['direct_exposed_records']
    totals['sample_rows']=len(development); totals['sample_groups']=development.signature.nunique()
    totals['role_counts']=development.bucket.value_counts().to_dict()
    totals['eligible_day_counts']=c.execute('SELECT capture_day,count(*) rows FROM eligible GROUP BY capture_day ORDER BY capture_day').df().to_dict(orient='records')
    totals['protocol_sha256']=hashlib.sha256((ROOT/'config/fuzzy/task02b_protocol.json').read_bytes()).hexdigest()
    totals['excluded_test_labels_read']=False; totals['independent_holdout']=False
    totals['group_overlap']=0; totals['sample_manifest_sha256']=hashlib.sha256((DATA/'sample_lineage.parquet').read_bytes()).hexdigest()
    (REPORT/'lineage.json').write_text(json.dumps(totals,indent=2),encoding='utf-8')
    print(json.dumps(totals,indent=2),flush=True)

if __name__=='__main__': prepare()
