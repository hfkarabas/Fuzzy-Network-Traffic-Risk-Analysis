"""Bounded registered architecture comparison on eligible development only."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import argparse
import hashlib
import json
import time
import numpy as np
import pandas as pd
from fuzzy_network_risk.advanced import AdvancedRiskEngine,architecture_config,COLUMNS,NAMES
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.calibration import fit_config
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.evaluation import binary_metrics
from fuzzy_network_risk.refinement import roles,group_weights,select_policies,check_lineage
from task05_research import R,C,T,dump,digest

SOURCES=['scripts/research/task05_experiment.py','scripts/research/task05_research.py','src/fuzzy_network_risk/advanced.py',
         'src/fuzzy_network_risk/membership.py','src/fuzzy_network_risk/engine.py',
         'src/fuzzy_network_risk/refinement.py','src/fuzzy_network_risk/evaluation.py',
         'src/fuzzy_network_risk/calibration.py','src/fuzzy_network_risk/rules.py']


def engine_for(training,name):
    if name=='A_frozen': return MamdaniRiskEngine.load(ROOT/'config/fuzzy/task04/selected_v4.json')
    if name=='A_refit': return MamdaniRiskEngine(fit_config(training[INPUTS],'task05-A_refit'))
    return AdvancedRiskEngine(architecture_config(training,name))


def columns(name): return INPUTS if name in NAMES[:2] else COLUMNS


def freeze():
    if (C/'protocol.json').exists(): raise ValueError('Registration already exists; never overwrite')
    dump(C/'protocol.json',{'version':'task05-architecture-v1','seed':20261105,'candidates':NAMES,
        'features_A':INPUTS,'features_B_C_D':COLUMNS,
        'hypotheses':'B expanded flat 15 rules; C four independently defuzzified modules then 7 final rules; D three behavior modules then 6 final rules. Exact rules are in frozen advanced.py. No outcome-driven iteration.',
        'membership':'Training row p25/p60/p90; positive subset for variation/IAT, log1p rate/volume/variation/duration/IAT; 0/1 SYN domain, integer ratio 0/1/2; domain final-layer 25/50/75 anchors. No labels fit boundaries.',
        'feature_reasoning':'Retain baseline dimensions and add persistence, spacing spread and exported SYN. Timing redundancy does not preclude a conditional hypothesis; zero-heavy SYN is supplemental, never conclusive alone. Other flags, active/idle, bytes and packet measures audited, not additional search candidates.',
        'population':'Same eligible 60k development; design excluded, three fixed train/calibration/assessment signature roles on 45958 records. Prior adaptive development reuse, not independent testing.',
        'policies':'Existing calibration-only max signature-weighted recall at FPR caps Sensitive10%, Balanced5%, Conservative1%. Exact ties unchanged. Raw row metrics also reported.',
        'promotion':'Balanced mean group recall >= BOTH A_frozen and A_refit +0.05, each fold recall >= A_frozen-0.02, mean group FPR<=0.075 and each fold<=0.10, no abstentions, paired signature-bootstrap recall gain lower95>0 vs both. Additionally every Tuesday/Wednesday/Thursday group-disjoint day stress has FPR<=0.10 and recall>=day-clean A_refit-0.02. Prefer fewer rules/layers within 0.02 mean recall among passing candidates; otherwise retain current production.',
        'day_stress':'Predeclared auxiliary stability gate: exclude entire assessment day and all its signatures from other days; split remaining signatures by SHA256 task05-day suffix for training/calibration. A_frozen remains historically warm, never called day-clean.',
        'uncertainty':'500 paired signature-group resamples, fixed seed; conditional fitted-fold recall difference, no day/session or adaptive-search correction.',
        'independent_holdout':False,'search_budget':'Three new architecture hypotheses only; no post-outcome refitting/rule changes. Failed candidates remain recorded.',
        'research_cache_sha256':digest(T/'research.parquet'),
        'source_sha256':{f:digest(ROOT/f) for f in SOURCES}})
    print('TASK05 architecture/promotion protocol frozen before candidate assessment.',flush=True)


def paired_recall(predictions,name,baseline):
    a=predictions[baseline].sort_values('source_row_id'); b=predictions[name].sort_values('source_row_id')
    assert a.source_row_id.equals(b.source_row_id)
    matrices=[]
    for f in [a,b]:
        w=group_weights(f); y=f.truth.to_numpy(); alert=f.alert.to_numpy()
        values=pd.DataFrame({'signature':f.signature,'tp':w*y*alert,'positive':w*y})
        matrices.append(values.groupby('signature',sort=True)[['tp','positive']].sum().to_numpy())
    x,z=matrices; rng=np.random.default_rng(20261105); differences=[]
    for _ in range(500):
        idx=rng.integers(0,len(x),len(x)); aa=x[idx].sum(axis=0); bb=z[idx].sum(axis=0)
        differences.append(float(bb[0]/bb[1]-aa[0]/aa[1]))
    return {'recall_gain_95':list(map(float,np.quantile(differences,[.025,.975]))),'resamples':500,'groups':len(x),
            'scope':'conditional fitted internal folds; adaptive reuse and host/day dependence excluded'}


def select(summary,folds,intervals,stress,rule_counts):
    passing=[]
    for name in NAMES[2:]:
        s=summary[name]
        if s['fpr']>.075 or s['abstention_rate']>0: continue
        if any(s['recall']<summary[b]['recall']+.05 or intervals[name][b]['recall_gain_95'][0]<=0 for b in NAMES[:2]): continue
        assessments=[m for m in folds if m['candidate']==name and m['policy']=='Balanced']
        if any(m['group_metrics']['false_positive_rate']>.10 or m['group_metrics']['recall']<next(
            a['group_metrics']['recall'] for a in folds if a['candidate']=='A_frozen' and a['policy']=='Balanced' and a['fold']==m['fold'])-.02 for m in assessments): continue
        checks=[v for v in stress if v['candidate']==name]
        if len(checks)!=3 or any(v['group_metrics']['false_positive_rate']>.10 or v['group_metrics']['recall']<next(
            a['group_metrics']['recall'] for a in stress if a['candidate']=='A_refit' and a['day']==v['day'])-.02 for v in checks): continue
        passing.append(name)
    if not passing: return 'A_frozen'
    maximum=max(summary[n]['recall'] for n in passing)
    close=[n for n in passing if summary[n]['recall']>=maximum-.02]
    return min(close,key=lambda n:(rule_counts[n],NAMES.index(n)))


def evaluate():
    protocol=json.loads((C/'protocol.json').read_text(encoding='utf-8'))
    assert protocol['source_sha256']=={f:digest(ROOT/f) for f in SOURCES}
    assert protocol['research_cache_sha256']==digest(T/'research.parquet')
    data=pd.read_parquet(T/'research.parquet'); panel=data.loc[data.bucket!='design']
    assert (np.isfinite(data[COLUMNS].to_numpy())&(data[COLUMNS].to_numpy()>=0)).all()
    exposed=pd.read_parquet(ROOT/'data/fuzzy_v2/exposure_manifest.parquet',columns=['source_row_id','observation_group_id','signature'])
    check_lineage(data,exposed.source_row_id,exposed.observation_group_id,exposed.signature); del exposed
    # Expanded representation contains all five original inputs, so exact
    # eight-dimensional duplicates cannot evade the protected original signature.
    assert panel.groupby(COLUMNS,dropna=False).bucket.nunique().max()==1
    metrics=[]; predictions={n:[] for n in NAMES}; policies_out={}; counts={}; fits=[]
    for fold in range(3):
        train,cal,assess=roles(panel,fold)
        for a,b in [(train,cal),(train,assess),(cal,assess)]:
            assert not set(a.signature)&set(b.signature) and not set(a.observation_group_id)&set(b.observation_group_id)
        fits.append({'fold':fold,'training_rows':len(train),'calibration_rows':len(cal),'assessment_rows':len(assess),
            'benign_rows':int((assess[LABEL]=='BENIGN').sum()),'attack_rows':int((assess[LABEL]!='BENIGN').sum()),
            'assessment_days':assess.capture_day.value_counts().to_dict(),
            'unseen_labels':sorted(set(assess[LABEL])-set(train[LABEL]))})
        for name in NAMES:
            engine=engine_for(train,name); engine.save(C/f'{name}_fold{fold}.json')
            rule_count=len(engine.config['rules']) if name in NAMES[:2] else sum(map(len,engine.config['layers'].values()))
            counts[name]=rule_count
            cp=engine.predict_batch(cal[columns(name)]); assert (cp['status']=='ok').all()
            policies,curve=select_policies((cal[LABEL]!='BENIGN').to_numpy(),cp['risk_score'],group_weights(cal))
            curve.to_csv(T/f'{name}_{fold}_calibration.csv',index=False); policies_out[f'{name}_{fold}']=policies
            start=time.perf_counter(); p=engine.predict_batch(assess[columns(name)]); elapsed=time.perf_counter()-start
            assert (p['status']=='ok').all(),'Coverage defect; do not silently filter abstentions'
            y=(assess[LABEL]!='BENIGN').to_numpy(); w=group_weights(assess)
            for policy,settings in policies.items():
                metrics.append({'candidate':name,'fold':fold,'policy':policy,'threshold':settings['threshold'],'model_id':engine.model_id,
                    'group_metrics':binary_metrics(y,p['risk_score'],settings['threshold'],w),
                    'row_metrics':binary_metrics(y,p['risk_score'],settings['threshold']),
                    'rule_coverage':float((p['rule_strengths']>0).any(axis=1).mean()),'abstention_rate':float((p['status']!='ok').mean()),
                    'rules':rule_count,'inference_seconds':elapsed,'rows_per_second':len(assess)/elapsed})
            predictions[name].append(pd.DataFrame({'source_row_id':assess.source_row_id,'signature':assess.signature,
                'capture_day':assess.capture_day,'label':assess[LABEL],'truth':y,'score':p['risk_score'],
                'alert':p['risk_score']>=policies['Balanced']['threshold'],'fold':fold}))
            print(name,'fold',fold,'complete',flush=True)
    for name in NAMES:
        predictions[name]=pd.concat(predictions[name]).sort_values('source_row_id').reset_index(drop=True)
        predictions[name].to_parquet(T/f'{name}_oof.parquet',index=False)
    intervals={n:{b:paired_recall(predictions,n,b) for b in NAMES[:2]} for n in NAMES[2:]}
    summary={}; table=[]
    for name in NAMES:
        for policy in ['Sensitive','Balanced','Conservative']:
            rows=[m for m in metrics if m['candidate']==name and m['policy']==policy]
            row={'candidate':name,'policy':policy,'rules':counts[name],'benign_rows':sum(m['row_metrics']['confusion_matrix']['tn']+m['row_metrics']['confusion_matrix']['fp'] for m in rows),
                'attack_rows':sum(m['row_metrics']['confusion_matrix']['tp']+m['row_metrics']['confusion_matrix']['fn'] for m in rows)}
            for k in ['precision','recall','f1','false_positive_rate','false_negative_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']:
                values=[m['group_metrics'][k] for m in rows]; row[k]=float(np.mean(values)); row[k+'_fold_sd']=float(np.std(values,ddof=1))
            for k in ['tn','fp','fn','tp']: row['row_'+k]=int(sum(m['row_metrics']['confusion_matrix'][k] for m in rows))
            row['pooled_row_fpr']=row['row_fp']/(row['row_fp']+row['row_tn']); row['pooled_row_recall']=row['row_tp']/(row['row_tp']+row['row_fn'])
            row['rule_coverage']=float(np.mean([m['rule_coverage'] for m in rows])); row['abstention_rate']=float(np.mean([m['abstention_rate'] for m in rows]))
            row['rows_per_second']=float(np.mean([m['rows_per_second'] for m in rows])); table.append(row)
            if policy=='Balanced': summary[name]={'recall':row['recall'],'fpr':row['false_positive_rate'],'abstention_rate':row['abstention_rate']}
    # Auxiliary day stability is registered for ALL candidates, never a search.
    stress=[]
    for day in ['Tuesday','Wednesday','Thursday']:
        assess=panel.loc[panel.capture_day==day]
        rest=panel.loc[(panel.capture_day!=day)&~panel.signature.isin(assess.signature)]
        split=rest.signature.map(lambda s:int(hashlib.sha256((s+'|task05-day').encode()).hexdigest()[:8],16)%2)
        train=rest.loc[split==0]; cal=rest.loc[split==1]
        for name in NAMES:
            e=engine_for(train,name); cp=e.predict_batch(cal[columns(name)]); assert (cp['status']=='ok').all()
            policies,_=select_policies((cal[LABEL]!='BENIGN').to_numpy(),cp['risk_score'],group_weights(cal))
            ap=e.predict_batch(assess[columns(name)]); assert (ap['status']=='ok').all()
            truth=(assess[LABEL]!='BENIGN').to_numpy(); threshold=policies['Balanced']['threshold']
            stress.append({'candidate':name,'day':day,'training_rows':len(train),'calibration_rows':len(cal),'assessment_rows':len(assess),
                'threshold':threshold,'group_metrics':binary_metrics(truth,ap['risk_score'],threshold,group_weights(assess)),
                'row_metrics':binary_metrics(truth,ap['risk_score'],threshold),
                'unseen_labels':sorted(set(assess[LABEL])-set(train[LABEL])),
                'caveat':'Internal day stress; A_frozen historical fit remains warm.'})
            print(name,'day stress',day,'complete',flush=True)
    selected=select(summary,metrics,intervals,stress,counts)
    best=max(NAMES[2:],key=lambda n:summary[n]['recall'])
    dump(R/'metrics.json',metrics); dump(R/'uncertainty.json',intervals); dump(R/'day_stress.json',stress)
    dump(R/'summary.json',summary); dump(R/'partition_audit.json',{'folds':fits,'overlap':0,'exposed_contamination':0,'eight_input_duplicate_role_overlap':0,'common_valid_rows':len(data)})
    dump(C/'fold_policies.json',policies_out); pd.DataFrame(table).to_csv(R/'comparison.csv',index=False)
    dump(R/'selection.json',{'selected':selected,'highest_internal_recall_experiment':best,'production_change_authorized_by_gate':selected!='A_frozen',
        'criterion':protocol['promotion'],'protocol_sha256':digest(C/'protocol.json'),
        'scope':'reused development validation plus registered internal day stress; no independent holdout'})
    # Keep experimental configs even when rejected. Retained production files
    # stay in their original location; a research decision manifest references them.
    dump(C/'recommendation.json',{'selected':selected,'production_model':'config/fuzzy/task04/selected_v4.json' if selected=='A_frozen' else f'config/fuzzy/task05/{selected}_fold0.json',
        'experimental_models':[f'config/fuzzy/task05/{n}_fold{k}.json' for n in NAMES for k in range(3)],
        'promotion_gate_passed':selected!='A_frozen','independent_test':False})
    print(json.dumps({'selected':selected,'summary':summary,'rule_counts':counts},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['freeze','evaluate']); args=parser.parse_args()
    {'freeze':freeze,'evaluate':evaluate}[args.phase]()
