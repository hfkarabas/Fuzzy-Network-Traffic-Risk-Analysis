"""Validate lineage, robustness, diagnostics and saved CV arithmetic without tuning."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from copy import deepcopy
import json
import hashlib
import time
import duckdb
import numpy as np
import pandas as pd
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.policy import PolicyRiskModel
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.refinement import signature,check_lineage,roles,group_weights,membership_candidate,choose_candidate,select_policies
from fuzzy_network_risk.evaluation import binary_metrics
from task02b_experiment import R,C,D,dump,source_hashes

def main():
    data=pd.read_parquet(D/'internal_development.parquet')
    exposed=pd.read_parquet(D/'exposure_manifest.parquet',columns=['source_row_id','observation_group_id','signature'])
    assert check_lineage(data,exposed.source_row_id,exposed.observation_group_id,exposed.signature)
    assert np.array_equal(signature(data[INPUTS].to_numpy()),data.signature.to_numpy())
    for fold in range(3):
        parts=roles(data.loc[data.bucket!='design'],fold)
        assert all(not set(parts[i].signature)&set(parts[j].signature) for i,j in [(0,1),(0,2),(1,2)])
    frozen=json.loads((C/'candidate_plan.json').read_text())
    assert source_hashes()==frozen['code_sha256']
    hashes=json.loads((C/'fold_model_hashes.json').read_text())
    for name,model_id in hashes.items(): assert MamdaniRiskEngine.load(C/(name+'.json')).model_id==model_id
    for fold in range(3):
        train,_,_=roles(data.loc[data.bucket!='design'],fold)
        for name in ['A_refit','B_membership','C_rules']:
            assert MamdaniRiskEngine(membership_candidate(train,name)).model_id==hashes[f'{name}_fold{fold}']
    selection=json.loads((R/'selection.json').read_text())
    recomputed=choose_candidate(selection['selection_inputs'],{k:v['paired_balanced_accuracy_difference_95'][0] for k,v in selection['uncertainty'].items()})
    assert recomputed==selection['selected']
    cv=json.loads((R/'cv_metrics.json').read_text())
    for name in frozen['candidates']:
        predictions=pd.read_parquet(D/f'{name}_oof.parquet')
        for record in [m for m in cv if m['candidate']==name]:
            p=predictions.loc[predictions.fold==record['fold']]
            w=1/p.groupby('signature').source_row_id.transform('size').to_numpy()
            measured=binary_metrics(p.truth.to_numpy(),p.score.to_numpy(),record['threshold'],w)
            for key in ['precision','recall','false_positive_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']:
                assert abs(measured[key]-record['group_metrics'][key])<1e-12
    wrapper=PolicyRiskModel.load(C/'selected_v2.json',C/'selected_policies.json')
    engine=wrapper.engine; design=data.loc[data.bucket=='design'].copy()
    _,calibration,_=roles(data.loc[data.bucket!='design'],0)
    rebuilt_policies,_=select_policies((calibration[LABEL]!='BENIGN').to_numpy(),engine.predict_batch(calibration[INPUTS])['risk_score'],group_weights(calibration))
    assert rebuilt_policies==json.loads((C/'selected_policies.json').read_text())['policies']
    start=time.perf_counter(); p=engine.predict_batch(design[INPUTS]); elapsed=time.perf_counter()-start
    scores=p['risk_score']; records=design[INPUTS].iloc[:100].to_dict(orient='records')
    singles=np.array([wrapper.predict_one(row)['risk_score'] for row in records])
    assert np.array_equal(singles,scores[:100])
    robust={}
    for factor in [.999,1.001]:
        other=engine.predict_batch(design[INPUTS]*factor)['risk_score']
        delta=np.abs(other-scores)
        robust[f'input_multiplier_{factor}']={'mean_absolute_change':float(delta.mean()),'p95':float(np.quantile(delta,.95)),
                                              'max':float(delta.max()),'category_changed_fraction':float((np.searchsorted([25,50,75],other,side='right')!=np.searchsorted([25,50,75],scores,side='right')).mean())}
    for factor in [.99,1.01]:
        cfg=deepcopy(engine.config)
        for f in cfg['features'].values():
            f['upper']*=factor
            for spec in f['sets'].values(): spec['parameters']=[v*factor for v in spec['parameters']]
        other=MamdaniRiskEngine(cfg).predict_batch(design[INPUTS])['risk_score']; delta=np.abs(other-scores)
        robust[f'transformed_membership_coordinates_{factor}']={'mean_absolute_change':float(delta.mean()),'p95':float(np.quantile(delta,.95)),'max':float(delta.max())}
    # Quantify leave-one-rule-out algorithmic sensitivity on a fixed design subset.
    # This is not causal network-security evidence and never feeds selection.
    subset=design.iloc[:2048]; original=engine.predict_batch(subset[INPUTS])['risk_score']
    drop=[]
    for j,r in enumerate(engine.config['rules']):
        cfg=deepcopy(engine.config); cfg['rules']=cfg['rules'][:j]+cfg['rules'][j+1:]
        removed=MamdaniRiskEngine(cfg).predict_batch(subset[INPUTS])['risk_score']
        finite=np.isfinite(removed); delta=original[finite]-removed[finite]
        drop.append({'rule':r['id'],'consequent':r['consequent'],'design_rows':len(subset),'no_coverage_after_removal':int((~finite).sum()),
                     'mean_score_contribution_on_retained_coverage':float(delta.mean()),'max_abs_score_change':float(np.abs(delta).max()),
                     'alerts_changed_at_original_threshold':int(((original>=25)!=(removed>=25)).sum())})
    pd.DataFrame(drop).to_csv(R/'design_rule_removal_sensitivity.csv',index=False)
    cases={
        'zero':[0,0,0,0,0], 'sparse':[.1,2,100,20,1], 'benign_like_bulk':[500,100000,1200,700,2],
        'small_packet_burst':[1e6,2,40,0,0], 'asymmetric':[1000,100,100,50,10],
        'extreme_finite':[1e308]*5, 'missing':[None,2,40,0,0], 'negative':[-1,2,40,0,0],
        'infinity':[np.inf,2,40,0,0], 'nan':[np.nan,2,40,0,0]}
    case_outputs=[]
    for name,values in cases.items():
        result=wrapper.predict_one(dict(zip(INPUTS,values)))
        if name in ['missing','negative','infinity','nan']: assert result['status']=='invalid_input' and result['alert'] is None
        else: assert result['status']=='ok' and 0<=result['risk_score']<=100
        case_outputs.append({'case':name,'synthetic':True,'result':result})
    near=[]
    reference=design[INPUTS].median().to_dict()
    for f in engine.config['features'].values():
        for anchor in f['raw_anchors']:
            a=dict(reference); b=dict(reference)
            a[f['column']]=anchor*(1-1e-6); b[f['column']]=anchor*(1+1e-6)
            near.append(abs(engine.predict_one(a)['risk_score']-engine.predict_one(b)['risk_score']))
    assert max(near)<.01
    robust['near_membership_anchors_max_change_at_2ppm']=max(near)
    examples=[]
    for level in ['Low','Medium','High','Critical']:
        matching=np.flatnonzero(p['risk_level']==level)
        if len(matching):
            row=design.iloc[int(matching[0])]
            examples.append({'requested_category':level,'naturally_observed_in_design':True,'source_row_id':int(row.source_row_id),
                             'input':row[INPUTS].to_dict(),'prediction':wrapper.predict_one(row[INPUTS].to_dict())})
        else: examples.append({'requested_category':level,'naturally_observed_in_design':False,'prediction':None})
    examples.append({'requested_category':'invalid_input','synthetic':True,'prediction':wrapper.predict_one({})})
    dump(R/'explanation_examples.json',examples); dump(R/'robustness_cases.json',case_outputs); dump(R/'robustness.json',robust)
    # Full eligible population composition, still excluding exposed-linked rows.
    c=duckdb.connect(); c.execute("SET memory_limit='1GB'")
    historical=c.execute('''SELECT d.partition AS original_grouped_partition,s.capture_day,s.temporal_partition,
      count(*) AS rows,count(DISTINCT d.observation_group_id) AS original_groups
      FROM read_parquet('data/samples/development_v1.parquet') d
      JOIN read_parquet('data/processed/v1/source_sessions.parquet') s USING(source_row_id)
      GROUP BY ALL ORDER BY original_grouped_partition,capture_day,temporal_partition''').df()
    historical.to_csv(R/'historical_partition_lineage.csv',index=False)
    eligible_metadata=c.execute('''SELECT count(*) rows,count(DISTINCT observation_group_id) original_groups,
      count(DISTINCT signature) signature_groups FROM read_parquet('data/fuzzy_v2/eligible_manifest.parquet')''').df().iloc[0].to_dict()
    dump(R/'eligible_population_groups.json',{k:int(v) for k,v in eligible_metadata.items()})
    counts=c.execute('''SELECT e.capture_day,c." Label" AS label,count(*) AS rows
       FROM read_parquet('data/fuzzy_v2/eligible_manifest.parquet') e JOIN read_parquet('data/processed/v1/cleaned.parquet') c USING(source_row_id)
       GROUP BY ALL ORDER BY e.capture_day,label''').df()
    counts.to_csv(R/'eligible_population_classes.csv',index=False)
    original_policy=[]
    base_oof=pd.read_parquet(D/'A_frozen_oof.parquet')
    for fold,g in base_oof.groupby('fold'):
        original_policy.append({'fold':int(fold),'metrics':binary_metrics(g.truth.to_numpy(),g.score.to_numpy(),25.,1/g.groupby('signature').source_row_id.transform('size').to_numpy())})
    dump(R/'historical_threshold_internal_only.json',original_policy)
    result={'status':'PASS','lineage_checked_rows':len(data),'exposed_contamination':0,'group_overlap':0,
            'all_candidate_hashes_valid':True,'all_36_policy_metrics_reproduced_from_saved_predictions':True,
            'all_nine_train_only_refits_match_saved_models':True,'model_selection_and_final_policies_reproduced':True,
            'single_batch_bitwise_equal':True,'all_four_real_design_categories_available':all(x.get('naturally_observed_in_design',True) for x in examples),
            'selected_model_id':engine.model_id,'inference_rows':len(design),'inference_seconds':elapsed,
            'throughput_rows_per_second':len(design)/elapsed,'scope':'CPU NumPy inference including output arrays; excludes disk IO and diagnostics',
            'max_centroid_workspace_bytes':2048*201*8,'near_boundary_checks':len(near),
            'code_freeze_valid':True,'internal_validation_only':True}
    dump(R/'validation.json',result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': main()
