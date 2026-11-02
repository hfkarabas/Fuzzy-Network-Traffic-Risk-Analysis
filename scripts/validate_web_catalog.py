"""Offline provenance check for the tiny tracked catalog against eligible design rows."""
from pathlib import Path
import hashlib
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    catalog=json.loads((ROOT/'web/catalog/examples.json').read_text(encoding='utf-8'))
    source=ROOT/catalog['source_artifact']
    with source.open('rb') as handle: assert hashlib.file_digest(handle,'sha256').hexdigest()==catalog['source_sha256']
    ids=[e['source_row_id'] for e in catalog['examples']]
    frame=pd.read_parquet(source,filters=[('source_row_id','in',ids)]).set_index('source_row_id')
    assert len(ids)==len(set(ids))==len(frame)
    for example in catalog['examples']:
        row=frame.loc[example['source_row_id']]
        assert row.bucket=='design' and row.capture_day!='Friday'
        assert row[' Label']==example['dataset_label']
        assert str(row.observation_group_id)==example['observation_group_id'] and row.signature==example['signature']
        for column,value in example['features'].items(): assert row[column]==value
    result={'status':'PASS','real_rows_verified':len(ids),'all_values_labels_and_provenance_exactly_match':True,
            'all_records_in_eligible_design_panel':True,'source_sha256':catalog['source_sha256'],
            'runtime_requires_source_parquet':False,'unavailable_categories':catalog['unavailable_categories']}
    (ROOT/'reports/web/catalog_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
