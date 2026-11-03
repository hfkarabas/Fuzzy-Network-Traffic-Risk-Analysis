"""Measured diagnostics, post-selection stress, preservation and scientific report."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import hashlib
import json
import time
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.evaluation import binary_metrics
from fuzzy_network_risk.refinement import group_weights,select_policies,threshold_curve
from fuzzy_network_risk.optimization import candidate_config
from fuzzy_network_risk.policy import PolicyRiskModel
from task04_experiment import R,C,T,dump,digest

F=ROOT/'reports/figures/task04'


def main():
    F.mkdir(parents=True,exist_ok=True)
    frame=pd.read_parquet(ROOT/'data/fuzzy_v2/internal_development.parquet')
    design=frame.loc[frame.bucket=='design']
    panel=frame.loc[frame.bucket!='design']
    engine=MamdaniRiskEngine.load(C/'selected_v4.json')
    settings=json.loads((C/'selected_policies.json').read_text(encoding='utf-8'))
    threshold=settings['policies']['Balanced']['threshold']
    pred=engine.predict_batch(design[INPUTS]); strengths=pred['rule_strengths']
    y=(design[LABEL]!='BENIGN').to_numpy(); scores=pred['risk_score']; alert=scores>=threshold
    rules=[]
    for j,rule in enumerate(engine.config['rules']):
        active=strengths[:,j]>=.1
        rules.append({'rule':rule['id'],'consequent':rule['consequent'],'mean_strength':float(strengths[:,j].mean()),
            'activation_fraction':float(active.mean()),'benign_activation':float(active[~y].mean()),
            'attack_activation':float(active[y].mean()),'active_fp':int((active&~y&alert).sum()),
            'active_fn':int((active&y&~alert).sum()),'fp_association':float(active[~y&alert].mean()),
            'fn_association':float(active[y&~alert].mean())})
    pd.DataFrame(rules).to_csv(R/'rule_diagnostics.csv',index=False)
    correlations=pd.DataFrame(strengths,columns=[r['id'] for r in engine.config['rules']]).corr(method='spearman')
    correlations.to_csv(R/'rule_redundancy.csv')
    memberships=[]
    for key,terms in pred['memberships'].items():
        for term,values in terms.items():
            memberships.append({'feature':key,'term':term,'positive_fraction':float((values>0).mean()),
                'full_fraction':float((values==1).mean()),'mean':float(values.mean()),
                'benign_mean':float(values[~y].mean()),'attack_mean':float(values[y].mean())})
    pd.DataFrame(memberships).to_csv(R/'membership_diagnostics.csv',index=False)
    dist=[]
    for label,mask in [('BENIGN',~y),('Attack',y)]:
        dist.append({'traffic':label,'rows':int(mask.sum()),
            **dict(zip(['min','p05','p25','median','p75','p95','max'],map(float,np.quantile(scores[mask],[0,.05,.25,.5,.75,.95,1])))),
            'near_category_cut_fraction':float((np.min(abs(scores[mask,None]-[25,50,75]),axis=1)<=1).mean()),
            'categories':dict(Counter(pred['risk_level'][mask]))})
    low=[i for i,r in enumerate(engine.config['rules']) if r['consequent']=='Low']
    high=[i for i,r in enumerate(engine.config['rules']) if r['consequent'] in ['High','Critical']]
    # Quantify near-bin residual dependence without pairwise flow comparisons.
    # This checks adjacent coarse bins and representative log distances only;
    # absence would NOT establish absence of host/session or cross-bin leakage.
    grouped=panel.groupby('signature',sort=True)
    representatives=grouped[INPUTS].median()
    buckets=grouped.bucket.first().to_dict()
    rep={s:np.log1p(row.to_numpy()[:4]) for s,row in representatives.iterrows()}
    pairs=0; touched=set()
    for signature in representatives.index:
        parts=list(map(int,signature.split(':')))
        for axis in range(4):
            other=parts.copy(); other[axis]+=1; neighbor=':'.join(map(str,other))
            if neighbor in rep and buckets[signature]!=buckets[neighbor] and np.max(abs(rep[signature]-rep[neighbor]))<=.10:
                pairs+=1; touched.update([signature,neighbor])
    contradictory=design.groupby(INPUTS)[LABEL].nunique()
    diagnostic={'scope':'eligible design only; descriptive reuse of previously diagnosed development',
        'score_distributions':dist,'low_high_conflict_fraction':float(((strengths[:,low].max(axis=1)>=.1)&(strengths[:,high].max(axis=1)>=.1)).mean()),
        'identical_five_input_vectors_with_multiple_labels':int((contradictory>1).sum()),
        'adjacent_signature_cross_role_representative_pairs':pairs,'signatures_in_adjacent_pairs':len(touched),
        'near_duplicate_scope':'One-axis adjacent bins, same ratio, representative L-infinity log1p distance <=0.10. Non-exhaustive evidence of remaining dependence, not a claim of full leakage removal.',
        'source_sha256':digest(ROOT/'data/fuzzy_v2/internal_development.parquet')}
    dump(R/'diagnostics.json',diagnostic)
    # Independent of assessment labels: extra-feature audit on each TRAIN role.
    extra=[c for c in frame.columns if c in [' Flow Duration',' Flow IAT Mean',' Flow IAT Std','Flow Bytes/s',
        ' Total Backward Packets',' SYN Flag Count',' ACK Flag Count',' PSH Flag Count',' Fwd Header Length',' min_seg_size_forward']]
    profile=[]
    for fold in range(3):
        train=panel.loc[panel.bucket==str((fold+2)%3)]
        corr=train[INPUTS+extra].corr(method='spearman')
        for column in INPUTS+extra:
            v=train[column].to_numpy(dtype=float); valid=np.isfinite(v)&(v>=0)
            day_auc={}
            for day,g in train.loc[valid].groupby('capture_day'):
                truth=(g[LABEL]!='BENIGN').to_numpy()
                if truth.any() and not truth.all(): day_auc[day]=binary_metrics(truth,g[column].to_numpy(),float(g[column].median()))['roc_auc']
            other=[c for c in INPUTS if c!=column]
            profile.append({'fold':fold,'feature':column,'invalid_fraction':float((~valid).mean()),'zero_fraction':float((v==0).mean()),
                'p05':float(np.quantile(v[valid],.05)),'median':float(np.median(v[valid])),'p95':float(np.quantile(v[valid],.95)),
                'max_abs_existing_spearman':float(corr.loc[column,other].abs().max()),'auc_by_day':json.dumps(day_auc)})
    pd.DataFrame(profile).to_csv(R/'training_feature_audit.csv',index=False)
    # Frozen selection already exists. This stress must not change it.
    selected=json.loads((R/'selection.json').read_text())['candidate']
    stress=[]
    for day in ['Tuesday','Wednesday','Thursday']:
        assess=panel.loc[panel.capture_day==day]
        rest=panel.loc[(panel.capture_day!=day)&~panel.signature.isin(assess.signature)]
        split=rest.signature.map(lambda s:int(hashlib.sha256((s+'|task04-day').encode()).hexdigest()[:8],16)%2)
        train=rest.loc[split==0]; cal=rest.loc[split==1]
        for name in dict.fromkeys(['A_refit',selected]):
            e=MamdaniRiskEngine(candidate_config(train,name,engine.config))
            cp=e.predict_batch(cal[INPUTS]); policies,_=select_policies((cal[LABEL]!='BENIGN').to_numpy(),cp['risk_score'],group_weights(cal))
            ap=e.predict_batch(assess[INPUTS]); truth=(assess[LABEL]!='BENIGN').to_numpy(); t=policies['Balanced']['threshold']
            stress.append({'day':day,'candidate':name,'threshold':t,'train_rows':len(train),'calibration_rows':len(cal),
                'assessment_rows':len(assess),'unseen_labels':sorted(set(assess[LABEL])-set(train[LABEL])),
                'group_metrics':binary_metrics(truth,ap['risk_score'],t,group_weights(assess)),
                'row_metrics':binary_metrics(truth,ap['risk_score'],t),
                'caveat':'Post-selection internal scenario shift; A_frozen warm historical fit, not day-clean training.'})
    dump(R/'day_stress.json',stress)
    # Per-class and deterministic representative errors on internal OOF only.
    oof=pd.read_parquet(T/f'{selected}_oof.parquet')
    classes=[]
    for label,g in oof.groupby('label'):
        classes.append({'label':label,'support':len(g),'alerts':int(g.alert.sum()),'missed':int((~g.alert).sum()),
                        'alert_rate':float(g.alert.mean()),'scope':'internal OOF using fold-calibrated thresholds; not deployed-policy test'})
    pd.DataFrame(classes).to_csv(R/'per_class.csv',index=False)
    error=[]
    for kind,mask in [('false_positive',~oof.truth&oof.alert),('false_negative',oof.truth&~oof.alert)]:
        for _,row in oof.loc[mask].sort_values('source_row_id').head(3).iterrows():
            source=panel.loc[panel.source_row_id==row.source_row_id].iloc[0]
            e=MamdaniRiskEngine.load(C/f'{selected}_fold{row.fold}.json')
            fold_settings=json.loads((C/'fold_policies.json').read_text())[f'{selected}_{row.fold}']
            prediction=PolicyRiskModel(e,{'model_id':e.model_id,'policies':fold_settings},'Balanced').predict_one(source[INPUTS].to_dict())
            error.append({'kind':kind,'source_row_id':int(row.source_row_id),'label':row.label,
                'inputs':source[INPUTS].to_dict(),'prediction':prediction,
                'fold_alert':bool(row.alert),'alert_threshold':json.loads((C/'fold_policies.json').read_text())[f'{selected}_{row.fold}']['Balanced']['threshold'],
                'interpretation':'Overlapping behavioral features and fuzzy output conflict; illustrative internal error, not rule-tuning evidence.'})
    dump(R/'error_examples.json',error)
    # Empirical bounded stability, invalid abstention, policy invariance and reload.
    start=time.perf_counter(); actual=engine.predict_batch(design[INPUTS]); seconds=time.perf_counter()-start
    perturbed=engine.predict_batch(design[INPUTS]*1.001)
    delta=abs(actual['risk_score']-perturbed['risk_score'])
    examples=[]
    wrappers={n:PolicyRiskModel(engine,settings,n) for n in settings['policies']}
    for level in ['Low','Medium','High','Critical']:
        idx=np.flatnonzero(actual['risk_level']==level)
        item={'category':level,'naturally_observed':bool(len(idx))}
        if len(idx):
            row=design.iloc[int(idx[0])]; item.update(source_row_id=int(row.source_row_id),prediction=wrappers['Balanced'].predict_one(row[INPUTS].to_dict()))
        examples.append(item)
    dump(R/'explanation_examples.json',examples)
    cases=[]
    for name,values in {'zero':[0]*5,'extreme':[1e308]*5,'sparse':[.01,2,40,0,0],
        'bulk':[5000,10000,1400,500,1],'asymmetric':[1000,100,100,50,10],'burst':[1e6,2,40,0,0],
        'missing':[None,2,40,0,0],'nan':[np.nan,2,40,0,0],'infinity':[np.inf,2,40,0,0],'negative':[-1,2,40,0,0]}.items():
        output=wrappers['Balanced'].predict_one(dict(zip(INPUTS,values)))
        assert output['status']==('invalid_input' if name in ['missing','nan','infinity','negative'] else 'ok')
        cases.append({'case':name,'synthetic':True,'result':output})
    near=[]; reference=design[INPUTS].median().to_dict()
    for feature in engine.config['features'].values():
        for anchor in feature['raw_anchors']:
            a=dict(reference); b=dict(reference); a[feature['column']]=anchor*(1-1e-6); b[feature['column']]=anchor*(1+1e-6)
            near.append(abs(engine.predict_one(a)['risk_score']-engine.predict_one(b)['risk_score']))
    for _,row in design.head(40).iterrows():
        record=row[INPUTS].to_dict(); one=engine.predict_one(record)
        batch=engine.predict_batch(record)
        assert one['risk_score']==batch['risk_score'][0]
        values=[w.predict_one(record) for w in wrappers.values()]
        assert len({v['risk_score'] for v in values})==1
        assert all(v['activated_rules']==one['activated_rules'] for v in values)
    reloaded=MamdaniRiskEngine.load(C/'selected_v4.json')
    np.testing.assert_array_equal(actual['risk_score'],reloaded.predict_batch(design[INPUTS])['risk_score'])
    robust={'status':'PASS','rows':len(design),'seconds':seconds,'rows_per_second':len(design)/seconds,
        'scope':'CPU inference incl output arrays, excludes IO; one bounded run, not latency SLA',
        'max_score_change_plus_0_1_percent':float(delta.max()),'p99_score_change':float(np.quantile(delta,.99)),
        'near_anchor_max_change_2ppm':max(near),'near_anchor_checks':len(near),
        'single_batch_policy_and_reload_consistency':True,'centroid_workspace_bytes':2048*201*8,
        'input_dataframe_bytes':int(design[INPUTS].memory_usage(deep=True).sum()),'invalid_cases_abstain':True}
    dump(R/'robustness.json',robust); dump(R/'robustness_cases.json',cases)
    # Reproduce every saved metric from OOF and fold policies, no new tuning.
    metrics=json.loads((R/'metrics.json').read_text()); verified=0
    for name in sorted(set(m['candidate'] for m in metrics)):
        p=pd.read_parquet(T/f'{name}_oof.parquet')
        for m in [m for m in metrics if m['candidate']==name]:
            g=p.loc[p.fold==m['fold']]
            for key,w in [('row_metrics',None),('group_metrics',group_weights(g))]:
                reproduced=binary_metrics(g.truth,g.score,m['threshold'],w)
                for metric,value in reproduced.items():
                    if isinstance(value,(float,int)) and value is not None:
                        assert np.isclose(value,m[key][metric],atol=1e-12)
                for k,value in reproduced['confusion_matrix'].items(): assert np.isclose(value,m[key]['confusion_matrix'][k])
            verified+=1
    dump(R/'metric_reproduction.json',{'status':'PASS','policy_metric_rows':verified,'source':'saved internal OOF, thresholds frozen before assessment'})
    figures(engine,design,pred,rules)
    report(diagnostic,robust,stress)
    print(json.dumps({'diagnostic_rows':len(design),'near_bin_cross_role_pairs':pairs,'robustness':robust,'metric_rows_verified':verified},indent=2))


def figures(engine,design,pred,rules):
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for ax,(key,spec) in zip(axes.flat,engine.config['features'].items()):
        from fuzzy_network_risk.membership import membership
        x=np.linspace(0,spec['upper'],600)
        for term,mf in spec['sets'].items(): ax.plot(x,membership(x,mf),label=term)
        ax.set(title=spec['column'].strip(),xlabel='log1p physical units' if spec['transform']=='log1p' else spec['unit'],ylabel='Membership'); ax.legend(fontsize=7)
    axes.flat[-1].axis('off'); fig.tight_layout(); fig.savefig(F/'memberships.png',dpi=140); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4)); y=(design[LABEL]!='BENIGN').to_numpy()
    for label,mask in [('BENIGN',~y),('Attack',y)]:
        axes[0].hist(pred['risk_score'][mask],bins=np.linspace(0,100,41),density=True,alpha=.5,label=label)
    axes[0].set(xlabel='Fuzzy score (not probability)',ylabel='Density',title='Design-only score overlap'); axes[0].legend()
    x=np.arange(len(rules)); axes[1].bar(x-.2,[r['benign_activation'] for r in rules],.4,label='BENIGN'); axes[1].bar(x+.2,[r['attack_activation'] for r in rules],.4,label='Attack')
    axes[1].set_xticks(x,[r['rule'] for r in rules],rotation=90); axes[1].set(ylabel='Activation >=0.1 fraction',title='Associations, not causal contributions'); axes[1].legend()
    fig.tight_layout(); fig.savefig(F/'score_rule_diagnostics.png',dpi=140); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for name in ['A_frozen','A_refit','B_group_membership','C_context_rules','D_combined']:
        p=pd.read_parquet(T/f'{name}_oof.parquet'); curve=threshold_curve(p.truth,p.score,group_weights(p))
        axes[0].plot(curve.recall,curve.precision,label=name); axes[1].plot(curve.fpr,curve.recall,label=name)
    axes[0].set(xlabel='Recall',ylabel='Precision',title='Pooled internal OOF ranking; descriptive only')
    axes[1].set(xlabel='False-positive rate',ylabel='Recall',title='No threshold selection on this plot'); axes[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(F/'tradeoffs.png',dpi=140); plt.close(fig)
    comparison=pd.read_csv(R/'comparison.csv'); rows=comparison.loc[comparison.policy=='Balanced']
    fig,axes=plt.subplots(1,2,figsize=(12,4)); x=np.arange(len(rows))
    axes[0].bar(x,rows.balanced_accuracy,yerr=rows.balanced_accuracy_fold_sd,capsize=4); axes[0].axhline(.5,color='gray',linestyle='--')
    axes[0].set_xticks(x,rows.candidate,rotation=20); axes[0].set(ylabel='Group balanced accuracy ± fold SD',title='Reused internal validation')
    a=rows.iloc[0]; matrix=np.array([[a.row_tn,a.row_fp],[a.row_fn,a.row_tp]])
    axes[1].imshow(matrix,cmap='Blues'); axes[1].set_xticks([0,1],['No alert','Alert']); axes[1].set_yticks([0,1],['BENIGN','Attack']); axes[1].set_title('Frozen baseline pooled RAW flow counts')
    for i in range(2):
        for j in range(2): axes[1].text(j,i,str(int(matrix[i,j])),ha='center',va='center')
    fig.tight_layout(); fig.savefig(F/'comparison_confusion.png',dpi=140); plt.close(fig)


def report(diagnostic,robust,stress):
    comparison=pd.read_csv(R/'comparison.csv'); selected=json.loads((R/'selection.json').read_text())['candidate']
    lines=['# TASK04 scientific evaluation and integration report','',
        '**No defensible scoring improvement was demonstrated. Retain the existing fuzzy model and operating policies.**','',
        '## Audit and dataset foundation','',
        'TASK01 verified 2,830,743 records / 79 columns / 15 labels, 2,827,761 fuzzy-ready flows. TASK02 built grouped_v1 and day_v1 Mamdani models. TASK02B actually implemented frozen/refit, benign-reference membership, and 18-rule candidates; none passed its gate. TASK03 loaded selected_v2 (a verbatim copy of grouped_v1) with separate TASK02B policies. The dashboard displayed historical TASK02 tests separately from TASK02B internal validation. The historical model has 22 rules and five exact leading-space input names. Its score is a behavioral index, never an attack probability or class-derived severity.','',
        '## Integrity and lineage','',
        'Eligible population is 297,916 Monday–Thursday flows after excluding 2,529,845 exposed or leakage-linked flows from 2,827,761 quality-eligible flows. 703,945 were directly exposed; 1,825,900 more linked rows were excluded. TASK04 reads the saved eligible 60,000-row sample only, checks source IDs, original groups and coarse signatures against metadata-only exposure manifest, excludes all Friday, and does not read exposed labels/scores/errors. 14,042 design rows inform descriptive diagnostics; 45,958 comparison rows rotate through three disjoint train/calibration/assessment signature buckets. Each fold contains exactly one bucket per role. Exact selected-input duplicates cannot cross these roles. Capture days are recorded, but observations from a day can occur in multiple roles.','',
        'These development folds were already assessed in TASK02B and are adaptively reused here. Historical frozen membership fitting overlaps some eligible development data. A_frozen is contextual/warm; A_refit is the fair training-only comparator. No untouched independent test exists. No new shuffled subset is called a test. Conditional bootstrap intervals and fold SD omit adaptive selection, host/session dependence and population-exclusion bias.','',
        f"Residual near-duplicate audit found {diagnostic['adjacent_signature_cross_role_representative_pairs']} cross-role neighboring-bin representative pairs involving {diagnostic['signatures_in_adjacent_pairs']} signatures. This is a bounded one-axis adjacency check, not exhaustive matching. It demonstrates why signature disjointness does not prove independence. Design contains {diagnostic['identical_five_input_vectors_with_multiple_labels']} identical five-input vectors with multiple labels (not necessarily identical full flows). Earlier full-data audit found 698 conflicting-label numerical observation groups and 308,381 duplicate rows beyond first. No source labels were repaired or deleted.",'',
        '## Predeclared hypotheses and selection','',
        'config/fuzzy/task04/protocol.json freezes source/data hashes, candidates and selection before TASK04 results. A_frozen retains original scoring; A_refit refits original p25/p60/p90 anchors on training rows. B uses equal-signature training medians to reduce repeated-flow influence. C uses training-row memberships and exactly four rule changes: R07/R19 become Low; R10/R11 additionally require volume many. D combines B and C. All retain five features, 22 explicit rules and stable rule IDs. There is no Cartesian rule generation, classifier or black-box fitting. No post-result candidate search was performed.','',
        'Primary gate: mean Balanced group-weighted balanced accuracy; mean FPR <=7.5%; >=2 percentage-point improvement over BOTH refit and frozen baselines with positive paired signature-bootstrap lower95 against both. Otherwise retain original scoring and policies. This stricter gate prevents promoting a clean refit that is worse than the already active educational model.','',
        '## Feature and membership evidence','',
        'training_feature_audit.csv profiles all five inputs and ten extra candidates separately on each training fold, with missing/invalid rates, zeros, quantiles, rank redundancy and day-specific univariate AUC. Duration/IAT/header measurements strongly overlap existing volume/rate, bytes/s couples packet size and rate, flags are zero-heavy and day-unstable, and minimum segment size has collection-artifact concerns. No extra feature passed the pre-registration design justification; feature-enhanced E was not implemented. This does not prove five inputs sufficient. Timing/application context may ultimately be necessary, but requires a separately justified study. No API schema expansion is warranted here.','',
        'Rate and volume overlap is a rate-duration identity issue: high rate from a tiny denominator does not imply sustained load. Packet-length variation has a large zero mass; zero can mean a one-response flow, not malicious repetition. Forward/backward ratio is exported as an integer and loses fractional asymmetry. Class distributions and attack scenarios shift by capture day. All current inputs have overlapping benign/attack patterns.','',
        'Training-only triangular/trapezoidal sets use log1p for rate, count and response variation, identity for packet mean and exported ratio; shoulders saturate finite extremes. Direction anchors remain 0/1/2 by domain convention. B changes the reference population, not the transparent quantile rule. Final membership curves and all raw/transformed parameters are frozen in selected_v4.json and membership_diagnostics.csv/figures. Too much saturation and overlap remain; no hard set assignments were introduced.','',
        '## Root-cause diagnostics','',
        'rule_diagnostics.csv records all 22 rules: frequency >=0.1, average strength, benign/attack activation and association with FP/FN at the deployed Balanced threshold. rule_redundancy.csv retains activation rank correlations. R07/R10/R11/R19 co-activate often on benign design traffic; R02/R03 also cover many attacks, including slow flows. Removing broad rules can suppress benign alerts but also removes attack signal: the candidates demonstrate this tradeoff rather than solve it. Activation association is not causal contribution under max aggregation.','',
        f"Low and High/Critical rules simultaneously activate >=0.1 on {diagnostic['low_high_conflict_fraction']:.2%} of design flows. Min clipping, max aggregation and centroid combine their output areas, not a count or sum of rules; duplicate high rules do not add evidence. Centroids concentrate in moderate bands when several outputs conflict. All score/category cuts remain [25,50,75], distinct from binary alert thresholds. Large unusual transfers can be legitimate; low-rate attacks can resemble ordinary exchanges.",'',
        '## Candidate comparison — internal validation only','',
        'Metrics below are means of three signature-group-weighted fold rates. CM is separately pooled raw flow TN/FP/FN/TP; it must not be used to reconstruct group-weighted rates. Every candidate has 39,159 benign and 6,799 attack assessment rows. All 45 policy/fold rows, per-fold supports, exact thresholds, uncertainty and raw metrics are saved in machine-readable files.','',
        '| Candidate | Precision | Recall | F1 | FPR | FNR | BA ± fold SD | ROC-AUC | AP | Raw CM |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for _,r in comparison.loc[comparison.policy=='Balanced'].iterrows():
        lines.append(f"| {r.candidate} | {r.precision:.4f} | {r.recall:.4f} | {r.f1:.4f} | {r.false_positive_rate:.4f} | {r.false_negative_rate:.4f} | {r.balanced_accuracy:.4f} ± {r.balanced_accuracy_fold_sd:.4f} | {r.roc_auc:.4f} | {r.pr_auc_average_precision:.4f} | {int(r.row_tn)}/{int(r.row_fp)}/{int(r.row_fn)}/{int(r.row_tp)} |")
    lines+=['','A higher ranking AUC does not establish useful detection at a low-FPR threshold. The refined candidates failed the predeclared operating-point gate; all unfavorable results remain saved. uncertainty.json reports 500 paired signature-group bootstrap intervals against both baselines. Assessment labels select candidates, so this table is selection evidence, not independent performance.','',
        '## Policies and selected artifact','',
        f'Selected: {selected}. config/fuzzy/task04/selected_v4.json is a versioned exact copy of the retained model; selected_policies.json preserves existing bytes. selected_manifest.json records model ID and hashes. No new deployed threshold was fitted after results. Fold-specific policy calibration is separate from this deployed artifact.','',
        'Sensitive/Balanced/Conservative optimize calibration group recall at respective 10%/5%/1% estimated group FPR caps. Targets are not guarantees or raw flow FPR. Frozen deployed thresholds are 49.632522849397134 / 51.809236850031304 / 59.465890915130174. A policy changes only alert decisions, not score, memberships, category or rule activation.','',
        '| Policy | Group recall | Group FPR | Raw recall | Raw FPR |','|---|---:|---:|---:|---:|']
    for _,r in comparison.loc[comparison.candidate==selected].iterrows():
        lines.append(f'| {r.policy} | {r.recall:.4f} | {r.false_positive_rate:.4f} | {r.pooled_row_recall:.4f} | {r.pooled_row_fpr:.4f} |')
    lines+=['','## Post-selection day-shift stress','',
        'Each Tuesday/Wednesday/Thursday is excluded from refit training/calibration; all its coarse signatures are also removed from other days. Remaining signatures split deterministically for train/calibration. The frozen model remains warm historically and is explicitly not a day-clean fit. These results did not influence candidate selection or thresholds. Monday has no attacks and is omitted from two-class stress metrics.','',
        '| Day | Candidate | Rows | Recall | FPR | Unseen classes |','|---|---|---:|---:|---:|---|']
    for s in stress:
        lines.append(f"| {s['day']} | {s['candidate']} | {s['assessment_rows']} | {s['group_metrics']['recall']:.4f} | {s['group_metrics']['false_positive_rate']:.4f} | {', '.join(s['unseen_labels']) or 'None'} |")
    lines+=['','per_class.csv provides internal support, alert counts and missed attacks; rare supports cannot establish class reliability. error_examples.json contains three deterministic FP and FN examples with exact inputs, source IDs, labels, fold threshold and full rule evidence. They were generated after selection and not used to tune it. explanation_examples.json identifies naturally observed Low/Medium/High/Critical design examples; no category example is invented.','',
        '## Robustness, performance and integration','',
        f"Measured {robust['rows_per_second']:,.0f} rows/s on {robust['rows']:,} design flows in {robust['seconds']:.6f}s, CPU only excluding disk IO. Centroid batch workspace is {robust['centroid_workspace_bytes']:,} bytes before other NumPy temporaries. Batch size remains 2,048. +0.1% feature perturbations have maximum observed score change {robust['max_score_change_plus_0_1_percent']:.6f}; 15 near-anchor checks at two ppm yield maximum {robust['near_anchor_max_change_2ppm']:.8f}. These are measured workloads, not universal bounds or production SLAs.",'',
        'Missing/NaN/infinite/negative inputs abstain; no silent zero imputation. Extreme finite values saturate shoulders with out-of-range notices; valid zeros infer normally. Single/batch, reload, rule evidence and all-policy score invariance were checked. A separate metric-reproduction pass verified all 45 saved policy rows.','',
        'The FastAPI service loads the TASK04 manifest/configuration while preserving the same scoring/policy IDs. API schema and five inputs remain backward compatible. Historical example source rows and predictions remain valid. The existing React layout/pages/navigation/CSS are retained; the evaluation page adds a compact scientific comparison and explicit model/protocol identification. Historical TASK02 tests and TASK02B evidence remain separately labeled. Newly reused validation metrics are never presented as new independent tests.','',
        '## Reproduction and limitations','',
        'Run .venv/Scripts/python.exe scripts/task04_experiment.py compare after checking the registered source hashes; it regenerates candidate configs and comparison from unchanged eligible cache. Run scripts/task04_diagnostics.py for diagnostics/figures/stress/robustness. Freeze is one-time and refuses overwrite. Transient OOF/curves are under ignored .tmp/task04; figures under ignored reports/figures/task04. No dataset download, classifier training, GPU or remote Git operation is needed.','',
        'The user-approved educational web application is usable, but detection reliability has not improved. The project is ready for presentation review, not operational deployment. Present the negative experiment honestly, distinguish scores/categories/alerts, show a real false negative, and retain the scenario-shift and group-vs-flow caveats. Further scientific progress needs new training hypotheses and genuinely independent captures, not more adaptive tuning on this benchmark. See validation.json for executed test/build/integration evidence and preservation.json for historical hashes.']
    (R/'scientific_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__': main()
