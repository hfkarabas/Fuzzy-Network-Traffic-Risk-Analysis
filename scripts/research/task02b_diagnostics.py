"""Design-only diagnostics. Never reads comparison-fold or exposed labels."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import numpy as np
import pandas as pd
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.evaluation import binary_metrics
from fuzzy_network_risk.refinement import group_weights,select_policies

R=ROOT/'reports/fuzzy/task02b'

def main():
    # Push down bucket filter: only the design panel enters diagnostics.
    data=pd.read_parquet(ROOT/'data/fuzzy_v2/internal_development.parquet',filters=[('bucket','==','design')])
    engine=MamdaniRiskEngine.load(ROOT/'config/fuzzy/grouped_v1.json')
    p=engine.predict_batch(data[INPUTS]); scores=p['risk_score']; a=p['rule_strengths']; y=(data[LABEL]!='BENIGN').to_numpy()
    alert=scores>=engine.config['alert_threshold']; w=group_weights(data)
    pd.DataFrame({'source_row_id':data.source_row_id,'signature':data.signature,'truth':y,'score':scores}).to_parquet(ROOT/'data/fuzzy_v2/design_baseline_scores.parquet',index=False)
    rules=[]
    for j,rule in enumerate(engine.config['rules']):
        active=a[:,j]>=.1
        rules.append({'id':rule['id'],'consequent':rule['consequent'],'activation_fraction':float(active.mean()),
                      'mean_strength':float(a[:,j].mean()),'benign_fraction':float(active[~y].mean()),'attack_fraction':float(active[y].mean()),
                      'active_false_positives':int((active&~y&alert).sum()),'active_false_negatives':int((active&y&~alert).sum()),
                      'associated_fp_fraction':float(active[~y&alert].mean()) if (~y&alert).any() else None,
                      'associated_fn_fraction':float(active[y&~alert].mean()) if (y&~alert).any() else None})
    pd.DataFrame(rules).to_csv(R/'design_rule_diagnostics.csv',index=False)
    redundancy=pd.DataFrame(a,columns=[r['id'] for r in engine.config['rules']]).corr(method='spearman')
    redundancy.to_csv(R/'design_rule_correlations.csv')
    memberships=[]
    for key,terms in p['memberships'].items():
        for term,values in terms.items():
            memberships.append({'feature':key,'term':term,'mean_degree':float(values.mean()),'positive_fraction':float((values>0).mean()),
                                'full_membership_fraction':float((values==1).mean()),'benign_mean_degree':float(values[~y].mean()),'attack_mean_degree':float(values[y].mean())})
    pd.DataFrame(memberships).to_csv(R/'design_memberships.csv',index=False)
    distributions=[]
    for name,mask in [('Benign',~y),('Attack',y)]:
        distributions.append({'traffic':name,'rows':int(mask.sum()),**dict(zip(['min','p05','p25','median','p75','p95','max'],map(float,np.quantile(scores[mask],[0,.05,.25,.5,.75,.95,1])))),
                              'within_one_point_of_category_cut':float(np.min(np.abs(scores[mask,None]-np.array([25,50,75])),axis=1).min()) if False else float((np.min(np.abs(scores[mask,None]-[25,50,75]),axis=1)<=1).mean())})
    pd.DataFrame(distributions).to_csv(R/'design_score_distributions.csv',index=False)
    policies,curve=select_policies(y,scores,w); curve.to_csv(R/'design_threshold_tradeoff.csv',index=False)
    # Additional feature screening: descriptive training/design associations only,
    # not a trained predictor, not grounds alone for adding another fuzzy input.
    columns=INPUTS+[' Flow Duration',' Flow IAT Mean',' Flow IAT Std','Flow Bytes/s',' Total Backward Packets',
                    ' SYN Flag Count',' ACK Flag Count',' PSH Flag Count',' Fwd Header Length',' min_seg_size_forward']
    profile=[]; correlations=data[columns].corr(method='spearman')
    correlations.to_csv(R/'design_feature_correlations.csv')
    for c in columns:
        values=data[c].to_numpy(dtype=float); valid=np.isfinite(values)&(values>=0)
        aucs={}
        for day,g in data.loc[valid].groupby('capture_day'):
            truth=(g[LABEL]!='BENIGN').to_numpy()
            if truth.any() and not truth.all():
                aucs[day]=binary_metrics(truth,g[c].to_numpy(),float(g[c].median()))['roc_auc']
        other=[v for v in INPUTS if v!=c]
        corrs=correlations.loc[c,other].abs().dropna()
        profile.append({'feature':c,'invalid_percent':100*float((~valid).mean()),'zero_percent':100*float((values==0).mean()),
                        'minimum':float(values[valid].min()) if valid.any() else None,'median':float(np.median(values[valid])) if valid.any() else None,
                        'p95':float(np.quantile(values[valid],.95)) if valid.any() else None,'maximum':float(values[valid].max()) if valid.any() else None,
                        'max_abs_existing_spearman':float(corrs.max()) if len(corrs) else None,
                        'univariate_direction_stable_across_days':bool(len(aucs)>=3 and (all(v>.55 for v in aucs.values()) or all(v<.45 for v in aucs.values()))),
                        'auc_by_day':json.dumps(aucs)})
    pd.DataFrame(profile).to_csv(R/'feature_audit.csv',index=False)
    input_labels=data.groupby(INPUTS,dropna=False)[LABEL].nunique()
    summary={'design_rows':len(data),'benign':int((~y).sum()),'attack':int(y.sum()),'signature_groups':data.signature.nunique(),
             'baseline_threshold':engine.config['alert_threshold'],'baseline_metrics':binary_metrics(y,scores,engine.config['alert_threshold'],w),
             'policy_tradeoffs':policies,'five_input_vectors_with_contradictory_labels':int((input_labels>1).sum()),
             'low_high_conflict_fraction':float(((a[:,[j for j,r in enumerate(engine.config['rules']) if r['consequent']=='Low']].max(axis=1)>=.1)&
                                               (a[:,[j for j,r in enumerate(engine.config['rules']) if r['consequent'] in ['High','Critical']]].max(axis=1)>=.1)).mean()),
             'diagnostic_scope':'design bucket only; no exposed/comparison assessment scores read',
             'feature_decision':'D not automatic; inspect domain meaning, missingness, redundancy and day stability before freezing candidate list'}
    (R/'design_diagnostics.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__': main()
