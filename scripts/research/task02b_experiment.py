"""Limited predeclared candidates; nested group-role internal validation only."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import argparse
from copy import deepcopy
import hashlib
import json
import time
import numpy as np
import pandas as pd
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.engine import MamdaniRiskEngine,config_digest
from fuzzy_network_risk.evaluation import binary_metrics
from fuzzy_network_risk.refinement import (roles,membership_candidate,select_policies,group_weights,choose_candidate,SEED)

R=ROOT/'reports/fuzzy/task02b'; C=ROOT/'config/fuzzy/task02b'; D=ROOT/'data/fuzzy_v2'
NAMES=['A_frozen','A_refit','B_membership','C_rules']

def dump(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def source_hashes():
    names=['src/fuzzy_network_risk/engine.py','src/fuzzy_network_risk/membership.py',
           'src/fuzzy_network_risk/calibration.py','src/fuzzy_network_risk/rules.py',
           'src/fuzzy_network_risk/evaluation.py','src/fuzzy_network_risk/refinement.py',
           'scripts/research/task02b_prepare.py','scripts/research/task02b_diagnostics.py','scripts/research/task02b_experiment.py',
           'config/fuzzy/task02b_protocol.json']
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}

def freeze():
    if (C/'candidate_plan.json').exists(): raise ValueError('Candidate plan already frozen; use a new experiment version for changes')
    diagnostics=json.loads((R/'design_diagnostics.json').read_text())
    plan={'experiment':'task02b-v2-1','seed':SEED,'candidates':NAMES,
          'design_rows':diagnostics['design_rows'],
          'B_changes':'Training-BENIGN p25/p75/p95 reference anchors, explicit packet-size 16/64/256-byte and volume 2/4/16 floors, unchanged 22 rules',
          'C_changes':'B memberships, 18 explicit rules. Remove broad small/uniform and few/small/forward concern; demote sparse-many and intensive-few baselines; require volume corroboration for critical and varied-large response patterns.',
          'design_evidence':'R06/R07/R10/R11/R19 co-activate frequently on benign design flows; sparse-rate benign and attack score distributions overlap. Co-activation is association, not a causal attribution.',
          'D_decision':'Not implemented: duration rank correlation 0.965 with existing inputs; IAT 0.966-0.999; bytes/s algebraically tied to rate/size. Low-redundancy flags and segment size have unstable cross-day associations or collection-artifact concerns. Five inputs are not proven sufficient, but adding a feature is not yet defensible.',
          'supplemental_stress':'After selection only: leave Wednesday out of sampled non-design panel; remove all its signature groups from other days; use other groups in two deterministic buckets for train/calibration. Not used for selection; internal scenario-shift validation only.',
          'selection_protocol':json.loads((ROOT/'config/fuzzy/task02b_protocol.json').read_text()),
          'code_sha256':source_hashes()}
    dump(C/'candidate_plan.json',plan)
    print('Frozen limited candidate plan before comparison assessment.',flush=True)

def summarize(engine,frame,threshold):
    start=time.perf_counter(); p=engine.predict_batch(frame[INPUTS]); seconds=time.perf_counter()-start
    valid=p['status']=='ok'; y=(frame[LABEL]!='BENIGN').to_numpy(); w=group_weights(frame)
    result=binary_metrics(y[valid],p['risk_score'][valid],threshold,w[valid])
    result['row_metrics']=binary_metrics(y[valid],p['risk_score'][valid],threshold)
    result['benign_support']=int((~y).sum()); result['attack_support']=int(y.sum())
    result['abstention_rate']=float((~valid).mean()); result['rule_coverage']=float((p['rule_strengths']>0).any(axis=1).mean())
    return result,p,seconds

def bootstrap(groups,predictions,candidate,baseline='A_refit',iterations=500):
    """Paired resampling of group sufficient statistics, preserving duplicate ties."""
    names=[baseline,candidate]; matrices=[]
    base=predictions[names[0]].sort_values('source_row_id').reset_index(drop=True)
    for name in names:
        f=predictions[name].sort_values('source_row_id').reset_index(drop=True)
        assert base.source_row_id.equals(f.source_row_id)
        y=f.truth.to_numpy(dtype=bool); alert=f.alert.to_numpy(dtype=bool)
        w=1/f.groupby('signature').source_row_id.transform('size').to_numpy()
        components=pd.DataFrame({'signature':f.signature,'tp':w*(y&alert),'fn':w*(y&~alert),'fp':w*(~y&alert),'tn':w*(~y&~alert)})
        matrices.append(components.groupby('signature',sort=True)[['tp','fn','fp','tn']].sum().to_numpy())
    a,b=matrices; rng=np.random.default_rng(SEED); differences=[]; candidate_values=[]
    for _ in range(iterations):
        idx=rng.integers(0,len(a),size=len(a))
        def accuracy(m):
            tp,fn,fp,tn=m[idx].sum(axis=0)
            return (tp/(tp+fn)+tn/(tn+fp))/2
        aa=accuracy(a); bb=accuracy(b)
        differences.append(bb-aa); candidate_values.append(bb)
    return {'resamples':iterations,'groups':len(a),'paired_balanced_accuracy_difference_95':list(map(float,np.quantile(differences,[.025,.975]))),
            'candidate_balanced_accuracy_95':list(map(float,np.quantile(candidate_values,[.025,.975]))),
            'scope':'conditional fitted-fold internal validation; no host/day or model-selection uncertainty'}

def compare():
    plan=json.loads((C/'candidate_plan.json').read_text())
    assert source_hashes()==plan['code_sha256'],'Experiment source changed after registration'
    data=pd.read_parquet(D/'internal_development.parquet'); panel=data.loc[data.bucket!='design']
    frozen=MamdaniRiskEngine.load(ROOT/'config/fuzzy/grouped_v1.json')
    metrics=[]; predictions={name:[] for name in NAMES}; policies_out={}; hashes={}
    for fold in range(3):
        train,calibration,assessment=roles(panel,fold)
        assert not (set(train.signature)&set(calibration.signature) or set(train.signature)&set(assessment.signature) or set(calibration.signature)&set(assessment.signature))
        for name in NAMES:
            config=deepcopy(frozen.config) if name=='A_frozen' else membership_candidate(train,name)
            engine=MamdaniRiskEngine(config)
            engine.save(C/f'{name}_fold{fold}.json'); hashes[f'{name}_fold{fold}']=engine.model_id
            cp=engine.predict_batch(calibration[INPUTS]); cy=(calibration[LABEL]!='BENIGN').to_numpy()
            policies,curve=select_policies(cy,cp['risk_score'],group_weights(calibration))
            curve.to_csv(D/f'{name}_fold{fold}_calibration_curve.csv',index=False)
            policies_out[f'{name}_fold{fold}']=policies
            start=time.perf_counter(); ap=engine.predict_batch(assessment[INPUTS]); seconds=time.perf_counter()-start
            scores=ap['risk_score']; truth=(assessment[LABEL]!='BENIGN').to_numpy(); valid=ap['status']=='ok'
            for policy,settings in policies.items():
                t=settings['threshold']; wm=binary_metrics(truth[valid],scores[valid],t,group_weights(assessment)[valid]); rm=binary_metrics(truth[valid],scores[valid],t)
                metrics.append({'candidate':name,'fold':fold,'policy':policy,'model_id':engine.model_id,'threshold':t,
                                'train_rows':len(train),'calibration_rows':len(calibration),'assessment_rows':len(assessment),
                                'benign_support':int((~truth).sum()),'attack_support':int(truth.sum()),'signature_groups':assessment.signature.nunique(),
                                'group_metrics':wm,'row_metrics':rm,'calibration_policy':settings,
                                'rule_coverage':float((ap['rule_strengths']>0).any(axis=1).mean()),'abstention_rate':float((~valid).mean()),
                                'inference_seconds':seconds,'rules':len(config['rules'])})
            predictions[name].append(pd.DataFrame({'source_row_id':assessment.source_row_id,'signature':assessment.signature,
                                                   'capture_day':assessment.capture_day,'truth':truth,'score':scores,
                                                   'alert':scores>=policies['Balanced']['threshold'],'fold':fold}))
            print(f'{name}, fold {fold}: completed internal assessment',flush=True)
    for name,parts in predictions.items():
        predictions[name]=pd.concat(parts).sort_values('source_row_id').reset_index(drop=True)
        predictions[name].to_parquet(D/f'{name}_oof.parquet',index=False)
    summary={}
    for name in NAMES:
        values=[r for r in metrics if r['candidate']==name and r['policy']=='Balanced']
        summary[name]={'balanced_accuracy':float(np.mean([r['group_metrics']['balanced_accuracy'] for r in values])),
                       'fpr':float(np.mean([r['group_metrics']['false_positive_rate'] for r in values])),
                       'recall':float(np.mean([r['group_metrics']['recall'] for r in values]))}
    uncertainty={name:bootstrap(None,predictions,name) for name in ['A_refit','B_membership','C_rules']}
    selected=choose_candidate(summary,{name:v['paired_balanced_accuracy_difference_95'][0] for name,v in uncertainty.items()})
    dump(R/'cv_metrics.json',metrics); dump(R/'cv_summary.json',summary); dump(R/'uncertainty.json',uncertainty)
    dump(C/'fold_policies.json',policies_out); dump(C/'fold_model_hashes.json',hashes)
    dump(R/'selection.json',{'selected':selected,'protocol':'config/fuzzy/task02b_protocol.json',
                            'selection_inputs':summary,'uncertainty':uncertainty,
                            'interpretation':'internal model-selection evidence only; no independent final test'})
    # Compact parallel CSV for inspection, with raw and group metrics retained in JSON.
    rows=[]
    for r in metrics:
        rows.append({k:r[k] for k in ['candidate','fold','policy','threshold','benign_support','attack_support','signature_groups','rule_coverage','abstention_rate']} |
                    {k:r['group_metrics'][k] for k in ['precision','recall','f1','false_positive_rate','false_negative_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']} |
                    r['row_metrics']['confusion_matrix'])
    pd.DataFrame(rows).to_csv(R/'candidate_metrics.csv',index=False)
    print(json.dumps({'selected':selected,'summary':summary,'uncertainty':uncertainty},indent=2),flush=True)

def finalize():
    data=pd.read_parquet(D/'internal_development.parquet'); panel=data.loc[data.bucket!='design']
    selected=json.loads((R/'selection.json').read_text())['selected']
    # One declared role split for the educational integration configuration.
    # Its calibration panel is never used for membership fitting. CV metrics are
    # about fold-specific models, NOT a fresh test of this integration artifact.
    train,calibration,_=roles(panel,0)
    config=json.loads((ROOT/'config/fuzzy/grouped_v1.json').read_text()) if selected=='A_frozen' else membership_candidate(train,selected)
    engine=MamdaniRiskEngine(config); cp=engine.predict_batch(calibration[INPUTS])
    policies,_=select_policies((calibration[LABEL]!='BENIGN').to_numpy(),cp['risk_score'],group_weights(calibration))
    # Copy the selected model verbatim (including old threshold if baseline won);
    # explicit operating policies are applied separately without silently mutating it.
    engine.save(C/'selected_v2.json')
    dump(C/'selected_policies.json',{'model_id':engine.model_id,'policies':policies,'default_policy':'Balanced',
                                    'apply_alert':'score >= selected policy threshold; engine embedded threshold is historical metadata',
                                    'training_bucket':'historical A_frozen' if selected=='A_frozen' else '2','calibration_bucket':'1',
                                    'independent_test':False})
    dump(C/'selected_manifest.json',{'candidate':selected,'model_id':engine.model_id,'source_code_sha256':source_hashes(),
                                   'rule_count':len(config['rules']),'feature_count':5,'evidence':'internal rotating group-role validation'})
    # Supplemental day holdout is post-selection descriptive stability, not a new
    # tuning round. Original held-out signatures are removed from all other days.
    validation=panel.loc[panel.capture_day=='Wednesday']
    rest=panel.loc[(panel.capture_day!='Wednesday')&~panel.signature.isin(validation.signature)]
    group_hash=rest.signature.map(lambda s:int(hashlib.sha256((s+'|day-stress').encode()).hexdigest()[:8],16)%2)
    st=rest.loc[group_hash==0]; sc=rest.loc[group_hash==1]
    stress={}
    for name in ['A_refit',selected] if selected!='A_refit' else ['A_refit']:
        cfg=json.loads((ROOT/'config/fuzzy/grouped_v1.json').read_text()) if name=='A_frozen' else membership_candidate(st,name)
        e=MamdaniRiskEngine(cfg); pred=e.predict_batch(sc[INPUTS]); pol,_=select_policies((sc[LABEL]!='BENIGN').to_numpy(),pred['risk_score'],group_weights(sc))
        m,_,_=summarize(e,validation,pol['Balanced']['threshold'])
        stress[name]={'metrics':m,'train_rows':len(st),'calibration_rows':len(sc),'assessment_rows':len(validation),
                      'policy':pol['Balanced'],'unseen_labels':sorted(set(validation[LABEL])-set(st[LABEL])),
                      'interpretation':'internal leave-Wednesday-out stress only; not used for selection'}
    dump(R/'day_stress.json',stress)
    print('Frozen selected model and three explicit operating policies.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['freeze','compare','finalize'])
    args=parser.parse_args(); {'freeze':freeze,'compare':compare,'finalize':finalize}[args.phase]()
