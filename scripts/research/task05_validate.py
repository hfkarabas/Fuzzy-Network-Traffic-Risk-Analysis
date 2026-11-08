"""Reproduce model fitting, calibration, metrics, selection and preservation."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import hashlib
import subprocess
import numpy as np
import pandas as pd
from fuzzy_network_risk.advanced import NAMES,AdvancedRiskEngine
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.data import LABEL
from fuzzy_network_risk.refinement import roles,group_weights,select_policies,check_lineage
from fuzzy_network_risk.evaluation import binary_metrics
from task05_experiment import SOURCES,engine_for,columns,select
from task05_research import R,C,T,dump,digest


def main():
    protocol=json.loads((C/'protocol.json').read_text(encoding='utf-8'))
    assert protocol['source_sha256']=={f:digest(ROOT/f) for f in SOURCES}
    assert protocol['research_cache_sha256']==digest(T/'research.parquet')
    frame=pd.read_parquet(T/'research.parquet'); panel=frame.loc[frame.bucket!='design']
    exposure=pd.read_parquet(ROOT/'data/fuzzy_v2/exposure_manifest.parquet',columns=['source_row_id','observation_group_id','signature'])
    check_lineage(frame,exposure.source_row_id,exposure.observation_group_id,exposure.signature)
    assert not frame.capture_day.eq('Friday').any()
    metrics=json.loads((R/'metrics.json').read_text()); policies=json.loads((C/'fold_policies.json').read_text())
    verified=0
    for fold in range(3):
        train,cal,assess=roles(panel,fold)
        for name in NAMES:
            engine=(MamdaniRiskEngine if name in NAMES[:2] else AdvancedRiskEngine).load(C/f'{name}_fold{fold}.json')
            assert engine.config==engine_for(train,name).config
            cp=engine.predict_batch(cal[columns(name)]); truth=(cal[LABEL]!='BENIGN').to_numpy()
            fitted,_=select_policies(truth,cp['risk_score'],group_weights(cal)); assert fitted==policies[f'{name}_{fold}']
            ap=engine.predict_batch(assess[columns(name)])
            saved=pd.read_parquet(T/f'{name}_oof.parquet'); saved=saved.loc[saved.fold==fold].sort_values('source_row_id')
            np.testing.assert_array_equal(assess.source_row_id,saved.source_row_id)
            np.testing.assert_array_equal(ap['risk_score'],saved.score)
            for m in [m for m in metrics if m['candidate']==name and m['fold']==fold]:
                for key,w in [('group_metrics',group_weights(assess)),('row_metrics',None)]:
                    result=binary_metrics((assess[LABEL]!='BENIGN').to_numpy(),ap['risk_score'],m['threshold'],w)
                    for k,v in result.items():
                        if isinstance(v,(float,int)): assert np.isclose(v,m[key][k],atol=1e-12)
                    for k,v in result['confusion_matrix'].items(): assert np.isclose(v,m[key]['confusion_matrix'][k])
                verified+=1
    summary=json.loads((R/'summary.json').read_text()); uncertainty=json.loads((R/'uncertainty.json').read_text())
    stress=json.loads((R/'day_stress.json').read_text()); counts={n:next(m['rules'] for m in metrics if m['candidate']==n) for n in NAMES}
    for day in ['Tuesday','Wednesday','Thursday']:
        assess=panel.loc[panel.capture_day==day]
        rest=panel.loc[(panel.capture_day!=day)&~panel.signature.isin(assess.signature)]
        split=rest.signature.map(lambda s:int(hashlib.sha256((s+'|task05-day').encode()).hexdigest()[:8],16)%2)
        train=rest.loc[split==0]; cal=rest.loc[split==1]
        for name in NAMES:
            e=engine_for(train,name); cp=e.predict_batch(cal[columns(name)])
            settings,_=select_policies((cal[LABEL]!='BENIGN').to_numpy(),cp['risk_score'],group_weights(cal))
            ap=e.predict_batch(assess[columns(name)]); threshold=settings['Balanced']['threshold']
            saved=next(s for s in stress if s['candidate']==name and s['day']==day)
            assert threshold==saved['threshold']
            for key,w in [('group_metrics',group_weights(assess)),('row_metrics',None)]:
                reproduced=binary_metrics((assess[LABEL]!='BENIGN').to_numpy(),ap['risk_score'],threshold,w)
                for k,v in reproduced.items():
                    if isinstance(v,(float,int)): assert np.isclose(v,saved[key][k],atol=1e-12)
    assert select(summary,metrics,uncertainty,stress,counts)==json.loads((R/'selection.json').read_text())['selected']
    original=json.loads((ROOT/'reports/web/historical_integrity.json').read_text())
    for path,sha in original.items(): assert digest(ROOT/path)==sha,path
    # TASK01-04 tracked source, models, reports, tests and full web app are protected.
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','4390c850944c2222a5f26a440d285f61b6e99bc6'],cwd=ROOT,text=True).splitlines()
    protected=[p for p in tracked if p.startswith(('config/','reports/','web/','src/','scripts/','tests/'))]
    for path in protected:
        baseline=subprocess.check_output(['git','show','4390c85:'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==baseline.replace(b'\r\n',b'\n'),path
    dump(R/'reproduction.json',{'status':'PASS','all_15_training_only_models_reproduced':True,
        'all_15_calibration_policy_sets_reproduced':True,'assessment_scores_bitwise_reproduced':True,
        'policy_metric_rows_reproduced':verified,'selection_reproduced':True,'exposed_contamination':0,
        'all_15_day_stress_metric_sets_reproduced':True,
        'historical_artifact_hashes_unchanged':len(original),'prior_tracked_files_unchanged':len(protected),
        'entire_production_web_source_unchanged':True,'source_data_unchanged':True,
        'protocol_sha256':digest(C/'protocol.json')})
    print((R/'reproduction.json').read_text())


if __name__=='__main__': main()
