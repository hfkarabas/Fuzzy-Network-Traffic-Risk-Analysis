"""Training-only numerical stability and persisted-model reproducibility checks."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from run_fuzzy import connect,query,CONFIG,REPORT,write_json
from fuzzy_network_risk.data import INPUTS
from fuzzy_network_risk.engine import MamdaniRiskEngine,config_digest
import json
import numpy as np
import pandas as pd
import time

def main():
    c=connect(); result={}
    frozen=json.loads((CONFIG/'frozen_manifest.json').read_text())
    # Verify ratio semantics from existing train data only. File origins and raw
    # packet counts are never passed to inference or used to fit memberships.
    semantics=c.execute('''SELECT count(*) AS rows,
      sum((c." Down/Up Ratio"=floor(c." Total Backward Packets"/c." Total Fwd Packets"))::INTEGER) AS floor_ratio_matches
      FROM read_parquet('data/processed/v1/cleaned.parquet') c JOIN sessions s USING(source_row_id)
      WHERE s.temporal_partition='train' AND c.fuzzy_eligible''').df().iloc[0].to_dict()
    for scenario in ['grouped','day']:
        e=MamdaniRiskEngine.load(CONFIG/f'{scenario}_v1.json')
        assert e.model_id==frozen['models'][scenario]
        training=c.execute('SELECT * FROM ('+query(scenario,'train')+') LIMIT 256').df()[INPUTS]
        batch=e.predict_batch(training)
        scores=np.array([e.predict_one(r)['risk_score'] for r in training.to_dict(orient='records')])
        assert np.array_equal(scores,batch['risk_score'])
        fine_config=json.loads(json.dumps(e.config)); fine_config['output']['grid_points']=2001
        fine=MamdaniRiskEngine(fine_config).predict_batch(training)['risk_score']
        error=np.abs(fine-scores)
        assert error.max()<.05,'Centroid quadrature error too large'
        # Two small training-only repeats check determinism, not hyperparameters.
        again=MamdaniRiskEngine.load(CONFIG/f'{scenario}_v1.json').predict_batch(training,batch_size=31)
        assert np.array_equal(again['risk_score'],scores)
        start=time.perf_counter()
        for r in training.iloc[:100].to_dict(orient='records'): e.predict_one(r)
        milliseconds=(time.perf_counter()-start)*10
        result[scenario]={'model_id':e.model_id,'training_rows_checked':len(training),
                          'single_batch_bitwise_identical':True,'reload_and_batch_size_reproducible':True,
                          'quadrature_max_absolute_error_vs_2001_grid':float(error.max()),
                          'quadrature_mean_absolute_error':float(error.mean()),
                          'single_record_mean_milliseconds_100_training_flows':milliseconds,
                          'inference_features_exact':list(e.columns)}
    result['training_semantics_check']={k:int(v) for k,v in semantics.items()}
    result['source_artifact_integrity']='Verified separately by scripts/task02_integrity.py'
    write_json(REPORT/'numerical_validation.json',result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': main()
