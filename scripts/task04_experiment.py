"""Registered bounded TASK04 experiments. Never read exposed labels or scores."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
from copy import deepcopy
import hashlib
import json
import time
import numpy as np
import pandas as pd
from fuzzy_network_risk.data import INPUTS, LABEL
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.evaluation import binary_metrics
from fuzzy_network_risk.refinement import roles, group_weights, select_policies, check_lineage
from fuzzy_network_risk.optimization import candidate_config, select_model, CANDIDATES
from task02b_experiment import bootstrap

R = ROOT/'reports/fuzzy/task04'
C = ROOT/'config/fuzzy/task04'
T = ROOT/'.tmp/task04'
FILES = ['src/fuzzy_network_risk/optimization.py', 'scripts/task04_experiment.py',
         'src/fuzzy_network_risk/engine.py', 'src/fuzzy_network_risk/refinement.py',
         'src/fuzzy_network_risk/calibration.py', 'src/fuzzy_network_risk/rules.py',
         'src/fuzzy_network_risk/membership.py', 'src/fuzzy_network_risk/evaluation.py',
         'scripts/task02b_experiment.py']


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def freeze():
    for directory in [R, C, T]: directory.mkdir(parents=True, exist_ok=True)
    path = C/'protocol.json'
    if path.exists(): raise ValueError('Registration already exists; do not overwrite')
    dump(path, {'version':'task04-v1', 'seed':20261104,
        'candidates':CANDIDATES, 'rules':22, 'features':INPUTS,
        'B':'Training-only equal-signature median reference p25/p60/p90; original rules.',
        'C':'Training-row reference; R07/R19 Low; R10/R11 require volume many. Preserve R14/R16 varied-large response hypotheses and all other rules.',
        'D':'Exactly B plus C; no further search.',
        'feature_enhanced':'Not registered: existing design audit finds duration/IAT/header redundant, flags unstable by day, bytes/s algebraically coupled; five inputs retained, sufficiency not established.',
        'rationale':'Prior design-only diagnostics show R07/R10/R11/R19 frequent benign activation. Retain response-variability hypotheses lost by earlier broad demotion. Association is not causation.',
        'population':'Existing eligible 60,000 rows; 14,042 design rows excluded from assessment. Same three group-role rotations on 45,958 rows. Reused development validation, not independent testing.',
        'selection':'Mean Balanced-policy group-weighted BA; FPR<=0.075; >=0.02 gain over BOTH A_refit and active A_frozen; paired signature-bootstrap lower95>0 against both. Ties prefer earlier simpler candidate. Otherwise retain A_frozen and its policies verbatim.',
        'policies':'Calibration-only maximum signature-weighted recall at FPR caps 0.10/0.05/0.01, unchanged tie rules. Report raw row rates as well.',
        'uncertainty':'500 paired signature resamples; conditional on fitted folds, not selection-adjusted or host/day-independent.',
        'stress':'After selection only, leave each Tuesday/Wednesday/Thursday out, remove linked signatures from training/calibration; no reselection.',
        'limitations':'Prior TASK02B assessment reused adaptively. Original frozen memberships overlap development. No untouched holdout; no independent performance claim.',
        'source_sha256':{f:digest(ROOT/f) for f in FILES},
        'data_sha256':digest(ROOT/'data/fuzzy_v2/internal_development.parquet')})
    print('Protocol frozen before TASK04 candidate results.')


def compare():
    protocol = json.loads((C/'protocol.json').read_text(encoding='utf-8'))
    assert protocol['source_sha256']=={f:digest(ROOT/f) for f in FILES}
    assert protocol['data_sha256']==digest(ROOT/'data/fuzzy_v2/internal_development.parquet')
    data = pd.read_parquet(ROOT/'data/fuzzy_v2/internal_development.parquet')
    exposed = pd.read_parquet(ROOT/'data/fuzzy_v2/exposure_manifest.parquet', columns=['source_row_id','observation_group_id','signature'])
    check_lineage(data, exposed.source_row_id, exposed.observation_group_id, exposed.signature)
    assert not data.capture_day.eq('Friday').any()
    del exposed
    panel = data.loc[data.bucket!='design']
    frozen = MamdaniRiskEngine.load(ROOT/'config/fuzzy/task02b/selected_v2.json')
    result=[]; predictions={n:[] for n in CANDIDATES}; policy_records={}; supports=[]
    for fold in range(3):
        train, calibration, assessment = roles(panel, fold)
        for a,b in [(train,calibration),(train,assessment),(calibration,assessment)]:
            assert not set(a.signature)&set(b.signature)
            assert not set(a.observation_group_id)&set(b.observation_group_id)
        supports.append({'fold':fold,'train':len(train),'calibration':len(calibration),'assessment':len(assessment),
                         'assessment_groups':assessment.signature.nunique(),
                         'assessment_days':assessment.capture_day.value_counts().to_dict(),
                         'unseen_assessment_labels':sorted(set(assessment[LABEL])-set(train[LABEL]))})
        for name in CANDIDATES:
            config = candidate_config(train, name, frozen.config)
            engine = MamdaniRiskEngine(config); engine.save(C/f'{name}_fold{fold}.json')
            cp = engine.predict_batch(calibration[INPUTS])
            policies,curve = select_policies((calibration[LABEL]!='BENIGN').to_numpy(),cp['risk_score'],group_weights(calibration))
            curve.to_csv(T/f'{name}_{fold}_curve.csv',index=False)
            policy_records[f'{name}_{fold}']=policies
            start=time.perf_counter(); pred=engine.predict_batch(assessment[INPUTS]); elapsed=time.perf_counter()-start
            assert (pred['status']=='ok').all()
            truth=(assessment[LABEL]!='BENIGN').to_numpy(); scores=pred['risk_score']
            for policy,settings in policies.items():
                result.append({'candidate':name,'fold':fold,'policy':policy,'model_id':engine.model_id,
                    'threshold':settings['threshold'],'group_metrics':binary_metrics(truth,scores,settings['threshold'],group_weights(assessment)),
                    'row_metrics':binary_metrics(truth,scores,settings['threshold']),
                    'benign_support':int((~truth).sum()),'attack_support':int(truth.sum()),
                    'rule_coverage':float((pred['rule_strengths']>0).any(axis=1).mean()),'abstention_rate':0.,
                    'inference_seconds':elapsed})
            predictions[name].append(pd.DataFrame({'source_row_id':assessment.source_row_id,'signature':assessment.signature,
                'capture_day':assessment.capture_day,'label':assessment[LABEL], 'truth':truth,'score':scores,
                'alert':scores>=policies['Balanced']['threshold'],'fold':fold}))
            print(name,fold,'completed',flush=True)
    for name in CANDIDATES:
        predictions[name]=pd.concat(predictions[name]).sort_values('source_row_id').reset_index(drop=True)
        predictions[name].to_parquet(T/f'{name}_oof.parquet',index=False)
    summary={}
    for name in CANDIDATES:
        rows=[r for r in result if r['candidate']==name and r['policy']=='Balanced']
        summary[name]={key:float(np.mean([r['group_metrics'][metric] for r in rows])) for key,metric in
                       [('balanced_accuracy','balanced_accuracy'),('fpr','false_positive_rate'),('recall','recall')]}
    intervals={n:{b:bootstrap(None,predictions,n,baseline=b) for b in ['A_refit','A_frozen']} for n in CANDIDATES[2:]}
    selected=select_model(summary,intervals)
    dump(R/'metrics.json',result); dump(R/'summary.json',summary); dump(R/'uncertainty.json',intervals)
    dump(C/'fold_policies.json',policy_records); dump(R/'partition_audit.json',{'status':'PASS','sample_rows':len(data),
        'assessment_rows':len(panel),'design_rows':len(data)-len(panel),'exposed_contamination':0,'group_overlap':0,
        'folds':supports,'independent_holdout':False,'source_sha256':protocol['data_sha256']})
    dump(R/'selection.json',{'candidate':selected,'criterion':protocol['selection'],'summary':summary,
                             'scope':'reused internal validation; no independent test','protocol_sha256':digest(C/'protocol.json')})
    rows=[]
    for name in CANDIDATES:
        for policy in ['Sensitive','Balanced','Conservative']:
            parts=[r for r in result if r['candidate']==name and r['policy']==policy]
            row={'candidate':name,'policy':policy,'benign_rows':sum(r['benign_support'] for r in parts),
                 'attack_rows':sum(r['attack_support'] for r in parts)}
            for metric in ['precision','recall','f1','false_positive_rate','false_negative_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']:
                values=[r['group_metrics'][metric] for r in parts]
                row[metric]=float(np.mean(values)); row[metric+'_fold_sd']=float(np.std(values,ddof=1))
            for key in ['tn','fp','fn','tp']: row['row_'+key]=int(sum(r['row_metrics']['confusion_matrix'][key] for r in parts))
            row['pooled_row_fpr']=row['row_fp']/(row['row_fp']+row['row_tn'])
            row['pooled_row_recall']=row['row_tp']/(row['row_tp']+row['row_fn'])
            rows.append(row)
    pd.DataFrame(rows).to_csv(R/'comparison.csv',index=False)
    if selected=='A_frozen':
        # Preserve exact model bytes AND frozen existing operating policies.
        for src,dst in [('selected_v2.json','selected_v4.json'),('selected_policies.json','selected_policies.json')]:
            (C/dst).write_bytes((ROOT/'config/fuzzy/task02b'/src).read_bytes())
    else:
        (C/'selected_v4.json').write_bytes((C/f'{selected}_fold0.json').read_bytes())
        e=MamdaniRiskEngine.load(C/'selected_v4.json')
        dump(C/'selected_policies.json',{'model_id':e.model_id,'policies':policy_records[f'{selected}_0'],
              'default_policy':'Balanced','independent_test':False})
    active=MamdaniRiskEngine.load(C/'selected_v4.json')
    dump(C/'selected_manifest.json',{'candidate':selected,'model_id':active.model_id,'configuration_version':'task04-v1',
        'model_version':'TASK 04 · korunan Mamdani v1' if selected=='A_frozen' else 'TASK 04 · '+selected,
        'rule_count':len(active.config['rules']),'feature_count':5,'independent_test':False,
        'evidence':'reused internal validation; not independent final evaluation',
        'model_sha256':digest(C/'selected_v4.json'),'policy_sha256':digest(C/'selected_policies.json')})
    print(json.dumps({'selected':selected,'summary':summary},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['freeze','compare']); args=parser.parse_args()
    {'freeze':freeze,'compare':compare}[args.phase]()
