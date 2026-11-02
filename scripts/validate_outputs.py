"""Read-only full output validation; uses local cache, never downloads."""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
from acquire import acquire, ROOT
import sys
sys.path.insert(0,str(ROOT/'src'))
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import duckdb
from fuzzy_network_risk.data import clean, INPUTS, LABEL, validate_schema, observation_ids, partitions, sample_development
from report import render_reports
from cache_integrity import hashes, MANIFEST

def main():
    source = acquire()['train'].data.table
    out = ROOT/'data/processed/v1'
    offset = 0
    null_counts = {c:0 for c in source.column_names if c != LABEL}
    for batch in pq.ParquetFile(out/'cleaned.parquet').iter_batches(batch_size=65536):
        actual = batch.to_pandas()
        expected, counts = clean(source.slice(offset,len(actual)).to_pandas())
        for c in null_counts:
            np.testing.assert_allclose(actual[c].to_numpy(),expected[c].to_numpy(),rtol=0,atol=0,equal_nan=True)
            null_counts[c] += counts[c]
        assert actual[LABEL].tolist() == expected[LABEL].tolist()
        np.testing.assert_array_equal(actual.source_row_id,np.arange(offset,offset+len(actual)))
        ids = observation_ids(expected)
        np.testing.assert_array_equal(actual.observation_group_id,ids)
        np.testing.assert_array_equal(actual.partition,partitions(ids))
        np.testing.assert_array_equal(actual.fuzzy_eligible,expected[INPUTS].notna().all(axis=1) & expected[LABEL].notna())
        offset += len(actual)
    assert offset == len(source)
    schema = pq.read_schema(out/'fuzzy_ready.parquet')
    assert schema.names == INPUTS + [LABEL,'source_row_id','observation_group_id','partition']
    validate_schema(schema.names)
    con=duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET temp_directory='data/interim/duckdb'")
    con.execute("CREATE VIEW cleaned AS SELECT * FROM read_parquet('data/processed/v1/cleaned.parquet')")
    con.execute("CREATE VIEW fuzzy AS SELECT * FROM read_parquet('data/processed/v1/fuzzy_ready.parquet')")
    con.execute("CREATE VIEW dev AS SELECT * FROM read_parquet('data/samples/development_v1.parquet')")
    con.execute("CREATE VIEW manifest AS SELECT * FROM read_parquet('data/processed/v1/split_manifest.parquet')")
    fields=','.join('"'+c+'"' for c in schema.names)
    mismatch=con.execute(f'SELECT count(*) FROM ((SELECT {fields} FROM cleaned WHERE fuzzy_eligible EXCEPT ALL SELECT {fields} FROM fuzzy) UNION ALL (SELECT {fields} FROM fuzzy EXCEPT ALL SELECT {fields} FROM cleaned WHERE fuzzy_eligible))').fetchone()[0]
    assert mismatch == 0
    assert con.execute('SELECT count(*) FROM (SELECT * FROM dev EXCEPT ALL SELECT * FROM fuzzy)').fetchone()[0] == 0
    assert con.execute('SELECT count(*) FROM (SELECT source_row_id,observation_group_id,partition,fuzzy_eligible FROM cleaned EXCEPT ALL SELECT * FROM manifest)').fetchone()[0] == 0
    assert con.execute('SELECT count(*) FROM (SELECT observation_group_id FROM cleaned GROUP BY observation_group_id HAVING count(DISTINCT partition)>1)').fetchone()[0] == 0
    assert con.execute('SELECT count(DISTINCT " Label") FROM dev').fetchone()[0] == 15
    sampling_frame=con.execute('SELECT " Label",source_row_id,partition FROM fuzzy').df()
    rebuilt=sample_development(sampling_frame)
    saved=pd.read_parquet(ROOT/'data/samples/development_v1.parquet',columns=[LABEL,'source_row_id','partition'])
    pd.testing.assert_frame_equal(rebuilt.reset_index(drop=True),saved.reset_index(drop=True))
    result=json.loads((ROOT/'reports/dataset/preprocessing.json').read_text(encoding='utf-8'))
    assert null_counts == result['transformation_cells']
    sessions=json.loads((ROOT/'reports/dataset/session_recovery.json').read_text(encoding='utf-8'))
    assert sessions['status']=='PASS' and sessions['rows_verified']==len(source)
    con.execute("CREATE VIEW sessions AS SELECT * FROM read_parquet('data/processed/v1/source_sessions.parquet')")
    assert con.execute('SELECT count(*) FROM sessions').fetchone()[0]==len(source)
    assert con.execute('SELECT count(DISTINCT source_row_id) FROM sessions').fetchone()[0]==len(source)
    assert con.execute('SELECT count(*) FROM (SELECT source_row_id,observation_group_id,fuzzy_eligible FROM sessions EXCEPT ALL SELECT source_row_id,observation_group_id,fuzzy_eligible FROM manifest)').fetchone()[0]==0
    assert con.execute("SELECT count(*) FROM (SELECT observation_group_id FROM sessions WHERE temporal_partition!='quarantine' GROUP BY observation_group_id HAVING count(DISTINCT temporal_partition)>1)").fetchone()[0]==0
    assert hashes() == json.loads(MANIFEST.read_text(encoding='utf-8'))
    validation={'status':'PASS','all_source_rows_verified':offset,'all_numeric_cells_compared_to_cleaning_rules':offset*len(null_counts),
                'all_labels_preserved':True,'all_group_ids_and_partitions_recomputed':True,
                'fuzzy_output_matches_eligible_cleaned_rows':True,'development_sample_is_subset':True,
                'manifest_matches':True,'groups_crossing_partitions':0,'development_label_count':15,
                'source_cache_sha256_unchanged':True,'selected_inputs':INPUTS,
                'source_file_and_day_recovery_verified':True,'temporal_nonquarantine_groups_crossing_partitions':0,
                'development_sample_exactly_reproduced_from_full_fuzzy_output':True}
    (ROOT/'reports/dataset/validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    render_reports(source,pd.read_csv(ROOT/'reports/dataset/numeric_profile.csv'),
                   pd.read_csv(ROOT/'reports/dataset/classes.csv'),
                   json.loads((ROOT/'reports/dataset/quality.json').read_text()),result,
                   pd.read_parquet(ROOT/'data/samples/development_v1.parquet'))
    print(json.dumps(validation,indent=2),flush=True)

if __name__ == '__main__':
    main()
