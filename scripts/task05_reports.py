"""Post-selection diagnostic evidence, figures and five scientific reports."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import json
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fuzzy_network_risk.advanced import AdvancedRiskEngine,COLUMNS,NAMES
from fuzzy_network_risk.data import LABEL
from fuzzy_network_risk.membership import membership
from fuzzy_network_risk.refinement import group_weights,threshold_curve
from fuzzy_network_risk.policy import PolicyRiskModel
from task05_research import R,C,T,dump,digest

F=ROOT/'reports/figures/task05'


def load(name,fold=0): return AdvancedRiskEngine.load(C/f'{name}_fold{fold}.json')


def semantics(column):
    n=column.strip()
    if n=='Destination Port': return 'service context','port identifier','Remote service port; scenario/service shortcut risk, excluded from inference.'
    if 'IAT' in n: return 'temporal','microseconds','Within-flow inter-arrival gap statistic; no cross-flow periodicity evidence.'
    if 'Active' in n or 'Idle' in n: return 'temporal','microseconds','Activity/idle episode duration statistic; depends on exporter timeout convention.'
    if n=='Flow Duration': return 'temporal','microseconds','Elapsed observed flow lifetime; timeout/censoring and application behavior overlap.'
    if 'Flag' in n or 'Flags' in n: return 'connection','exported flag statistic','TCP flag export; actual 0/1 or constant range is audited, not interpreted as cross-flow attempt frequency.'
    if n=='Down/Up Ratio': return 'direction','integer-exported ratio','Backward/forward packet ratio with exporter integer division; zero does not establish no response.'
    if 'Packets/s' in n: return 'intensity','packets/second','Observed directional/all-flow packet count divided by observed duration.'
    if 'Bytes/s' in n or 'Bulk Rate' in n: return 'intensity','bytes/second or exporter bulk-rate unit','Rate statistic; denominator inflation and exporter bulk conventions require caution.'
    if 'Variance' in n: return 'structure','bytes squared','Packet-length variance; strongly related to squared standard deviation.'
    if 'Length' in n or 'Size' in n or 'Bytes' in n or 'Win_bytes' in n or 'seg_size' in n:
        return 'structure/direction','bytes','Packet/header/payload/window size statistic in the named direction; source-export details and sentinels matter.'
    return 'volume/direction','packets or exporter count','Named directional/subflow/bulk count; duplicate definitions and constant columns are screened.'


def diagnostics():
    F.mkdir(parents=True,exist_ok=True)
    frame=pd.read_parquet(T/'research.parquet'); design=frame.loc[frame.bucket=='design']
    policies=json.loads((C/'fold_policies.json').read_text())
    parameter_rows=[]; rule_rows=[]; membership_rows=[]; distributions=[]; conflicts=[]; examples=[]; robustness=[]
    feature_table=pd.read_csv(R/'feature_audit.csv'); sem=[]
    for column in feature_table.feature.unique():
        dimension,unit,meaning=semantics(column)
        g=feature_table.loc[(feature_table.feature==column)&(feature_table.panel=='design')].iloc[0]
        if column in COLUMNS: decision='Retained experimental input; not a validated discriminant.'
        elif g.unique_values<=1: decision='Reject: constant/uninformative in design.'
        elif column.strip()=='Destination Port': decision='Reject: service/scenario shortcut, not a behavioral input.'
        elif column.endswith('.1') or 'Subflow' in column: decision='Reject for compactness: duplicate/closely derived measurement.'
        elif g.max_baseline_abs_spearman>.95: decision='Not added: very high baseline rank redundancy; not proof of uselessness.'
        else: decision='Audited alternative: not in fixed eight-input hypothesis; stability/artifact/complexity need a separate study.'
        sem.append({'feature':column,'dimension':dimension,'unit':unit,'meaning_and_caveat':meaning,'decision':decision})
    pd.DataFrame(sem).to_csv(R/'feature_semantics.csv',index=False)
    # Exact-column repeats on design, bounded 78 x 14042 comparison.
    cols=list(feature_table.feature.unique()); duplicate_columns=[]
    for i,c in enumerate(cols):
        matches=[d for d in cols[:i] if design[c].equals(design[d])]
        if matches: duplicate_columns.append({'feature':c,'identical_to':matches[0]})
    dump(R/'duplicate_feature_columns.json',duplicate_columns)
    for name in NAMES[2:]:
        engine=load(name); wrapper=PolicyRiskModel(engine,{'model_id':engine.model_id,'policies':policies[f'{name}_0']},'Balanced')
        p=engine.predict_batch(design[COLUMNS]); y=(design[LABEL]!='BENIGN').to_numpy(); alert=p['risk_score']>=wrapper.threshold
        for layer,specs in engine.config['layers'].items():
            strengths=p['layers'][layer]['strengths']; low=[]; high=[]
            for j,r in enumerate(specs):
                active=strengths[:,j]>=.1
                if r['consequent']=='Low': low.append(j)
                if r['consequent'] in ['High','Critical']: high.append(j)
                rule_rows.append({'candidate':name,'layer':layer,'rule':r['id'],'consequent':r['consequent'],
                    'activation_fraction':float(active.mean()),'mean_strength':float(strengths[:,j].mean()),
                    'benign_activation':float(active[~y].mean()),'attack_activation':float(active[y].mean()),
                    'active_false_positives':int((active&~y&alert).sum()),'active_false_negatives':int((active&y&~alert).sum())})
            pd.DataFrame(strengths,columns=[r['id'] for r in specs]).corr(method='spearman').to_csv(R/f'{name}_{layer}_rule_correlations.csv')
            conflict=((strengths[:,low].max(axis=1)>=.1)&(strengths[:,high].max(axis=1)>=.1)) if low and high else np.zeros(len(design),bool)
            conflicts.append({'candidate':name,'layer':layer,'low_high_conflict_fraction':float(conflict.mean()),
                'coverage':float((strengths>0).any(axis=1).mean()),'score_median':float(np.median(p['layers'][layer]['score']))})
        for key,terms in p['memberships'].items():
            for term,v in terms.items():
                membership_rows.append({'candidate':name,'feature':key,'term':term,'positive_fraction':float((v>0).mean()),
                    'saturated_fraction':float((v==1).mean()),'benign_mean':float(v[~y].mean()),'attack_mean':float(v[y].mean())})
        for label,mask in [('BENIGN',~y),('Attack',y)]:
            distributions.append({'candidate':name,'traffic':label,'rows':int(mask.sum()),
                **dict(zip(['min','p05','p25','median','p75','p95','max'],map(float,np.quantile(p['risk_score'][mask],[0,.05,.25,.5,.75,.95,1])))),
                'near_category_cut_fraction':float((np.min(abs(p['risk_score'][mask,None]-[25,50,75]),axis=1)<=1).mean())})
        for fold in range(3):
            e=load(name,fold)
            for key,spec in e.config['features'].items():
                parameter_rows.append({'candidate':name,'fold':fold,'model_id':e.model_id,'feature':key,'column':spec['column'],
                    'unit':spec['unit'],'transform':spec['transform'],'basis':spec['anchor_basis'],
                    'training_min':spec['training_min'],'training_max':spec['training_max'],
                    'anchors':json.dumps(spec['raw_anchors']),'sets':json.dumps(spec['sets'])})
        for category in ['Low','Medium','High','Critical']:
            idx=np.flatnonzero(p['risk_level']==category)
            item={'candidate':name,'requested_category':category,'naturally_observed':bool(len(idx))}
            if len(idx):
                row=design.iloc[int(idx[0])]; item.update(source_row_id=int(row.source_row_id),prediction=wrapper.predict_one(row[COLUMNS].to_dict()))
            examples.append(item)
        # Deterministic design errors are post-selection illustrations only.
        for kind,mask in [('FP',~y&alert),('FN',y&~alert)]:
            idx=np.flatnonzero(mask)
            if len(idx):
                row=design.iloc[int(idx[0])]
                examples.append({'candidate':name,'error_kind':kind,'source_row_id':int(row.source_row_id),'label':row[LABEL],
                    'input':row[COLUMNS].to_dict(),'prediction':wrapper.predict_one(row[COLUMNS].to_dict()),'scope':'post-selection design illustration, not tuning'})
        # Bounded empirical perturbation excludes discrete exported SYN.
        pilot=design[COLUMNS].head(1000); changed=pilot.copy(); changed[COLUMNS[:-1]]*=1.001
        original=engine.predict_batch(pilot); changed_p=engine.predict_batch(changed)
        delta=abs(original['risk_score']-changed_p['risk_score'])
        near=[]; reference=pilot.median().to_dict()
        for key,spec in engine.config['features'].items():
            if key=='syn': continue
            for anchor in spec['raw_anchors']:
                a=dict(reference); b=dict(reference); a[spec['column']]=anchor*(1-1e-6); b[spec['column']]=anchor*(1+1e-6)
                near.append(abs(engine.predict_one(a)['risk_score']-engine.predict_one(b)['risk_score']))
        zero={c:0. for c in COLUMNS}; extreme={c:1e308 for c in COLUMNS}; extreme[COLUMNS[-1]]=1.
        assert 0<=engine.predict_one(zero)['risk_score']<=100 and 0<=engine.predict_one(extreme)['risk_score']<=100
        assert engine.predict_one({})['risk_score'] is None
        start=time.perf_counter(); measured=engine.predict_batch(design[COLUMNS]); elapsed=time.perf_counter()-start
        for _,row in pilot.head(20).iterrows():
            record=row.to_dict(); output=wrapper.predict_one(record)
            assert output['risk_score']==engine.predict_batch(record)['risk_score'][0]
            for policy in policies[f'{name}_0']:
                other=PolicyRiskModel(engine,{'model_id':engine.model_id,'policies':policies[f'{name}_0']},policy).predict_one(record)
                assert output['risk_score']==other['risk_score'] and output['layers']==other['layers']
        np.testing.assert_array_equal(measured['risk_score'],load(name).predict_batch(design[COLUMNS])['risk_score'])
        robustness.append({'candidate':name,'status':'PASS','design_rows':len(design),'seconds':elapsed,'rows_per_second':len(design)/elapsed,
            'max_change_plus_0_1_percent':float(delta.max()),'p99_change':float(np.quantile(delta,.99)),
            'near_anchors_2ppm_max_change':max(near),'near_anchor_checks':len(near),
            'centroid_workspace_bytes_per_layer':1024*201*8,'empirical_scope':'1000 eligible design rows, SYN unchanged, not a universal continuity bound'})
        if name=='C_hierarchy':
            idx=np.flatnonzero(p['risk_level']=='High'); row=design.iloc[int(idx[0])] if len(idx) else design.iloc[0]
            dump(R/'example_input.json',row[COLUMNS].to_dict())
            dump(R/'explanation_example.json',{'source_row_id':int(row.source_row_id),'label':row[LABEL],
                'scope':'eligible design example, no tuning or independent evaluation claim','prediction':wrapper.predict_one(row[COLUMNS].to_dict())})
    pd.DataFrame(parameter_rows).to_csv(R/'membership_parameters.csv',index=False)
    pd.DataFrame(rule_rows).to_csv(R/'rule_diagnostics.csv',index=False)
    pd.DataFrame(membership_rows).to_csv(R/'membership_diagnostics.csv',index=False)
    pd.DataFrame(distributions).to_csv(R/'score_distributions.csv',index=False)
    dump(R/'layer_conflicts.json',conflicts); dump(R/'explanation_examples.json',examples); dump(R/'robustness.json',robustness)
    perclass=[]
    for name in NAMES:
        p=pd.read_parquet(T/f'{name}_oof.parquet')
        for label,g in p.groupby('label'):
            perclass.append({'candidate':name,'label':label,'support':len(g),'alerts':int(g.alert.sum()),
                'unalerted':int((~g.alert).sum()),'attack_false_negatives':int((~g.alert).sum()) if label!='BENIGN' else 0,'alert_rate':float(g.alert.mean())})
    pd.DataFrame(perclass).to_csv(R/'per_class.csv',index=False)
    figures(design)
    reports(sem,conflicts,robustness)
    print('Generated feature, architecture, candidate, failure and final reports, figures and real explanations.',flush=True)


def figures(design):
    comparison=pd.read_csv(R/'comparison.csv'); balanced=comparison.loc[comparison.policy=='Balanced']
    fig,axes=plt.subplots(1,2,figsize=(12,4)); x=np.arange(len(balanced))
    axes[0].bar(x,balanced.recall,yerr=balanced.recall_fold_sd,capsize=4); axes[0].set_xticks(x,balanced.candidate,rotation=20)
    axes[0].set(ylabel='Recall ± fold SD',title='Reused group-aware internal validation')
    axes[1].bar(x,balanced.false_positive_rate,yerr=balanced.false_positive_rate_fold_sd,capsize=4)
    axes[1].set_xticks(x,balanced.candidate,rotation=20); axes[1].set(ylabel='FPR ± fold SD',title='Calibration cap is not an assessment guarantee')
    fig.tight_layout(); fig.savefig(F/'comparison.png',dpi=140); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for name in NAMES:
        p=pd.read_parquet(T/f'{name}_oof.parquet'); curve=threshold_curve(p.truth,p.score,group_weights(p))
        axes[0].plot(curve.recall,curve.precision,label=name); axes[1].plot(curve.fpr,curve.recall,label=name)
    axes[0].set(xlabel='Recall',ylabel='Precision',title='Pooled OOF rankings, not policy fitting'); axes[1].set(xlabel='FPR',ylabel='Recall',title='Descriptive operating tradeoff'); axes[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(F/'tradeoffs.png',dpi=140); plt.close(fig)
    e=load('C_hierarchy'); p=e.predict_batch(design[COLUMNS]); y=(design[LABEL]!='BENIGN').to_numpy()
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for label,mask in [('BENIGN',~y),('Attack',y)]: axes[0].hist(p['risk_score'][mask],bins=np.linspace(0,100,41),density=True,alpha=.5,label=label)
    axes[0].set(xlabel='Behavioral risk score',ylabel='Density',title='C_hierarchy design-score overlap'); axes[0].legend()
    for name,result in p['layers'].items():
        if name!='final': axes[1].hist(result['score'],bins=30,density=True,histtype='step',label=name)
    axes[1].set(xlabel='Intermediate fuzzy output',ylabel='Density',title='Real module centroid outputs'); axes[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(F/'scores_modules.png',dpi=140); plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(15,7))
    for ax,(key,spec) in zip(axes.flat,e.config['features'].items()):
        z=np.unique(np.r_[np.linspace(0,spec['upper'],400),[v for s in spec['sets'].values() for v in s['parameters']]])
        for term,s in spec['sets'].items(): ax.plot(z,membership(z,s),label=term)
        ax.set(title=spec['column'].strip(),xlabel=spec['transform']+' axis ('+spec['unit']+')',ylabel='Degree'); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(F/'memberships.png',dpi=140); plt.close(fig)
    rules=pd.read_csv(R/'rule_diagnostics.csv'); rules=rules.loc[rules.candidate=='C_hierarchy']
    fig,ax=plt.subplots(figsize=(13,4)); x=np.arange(len(rules)); labels=rules.layer+'.'+rules.rule
    ax.bar(x-.2,rules.benign_activation,.4,label='BENIGN'); ax.bar(x+.2,rules.attack_activation,.4,label='Attack')
    ax.set_xticks(x,labels,rotation=90,fontsize=7); ax.set(ylabel='Activation >=0.1 fraction',title='C_hierarchy design associations (not causal contribution)'); ax.legend()
    fig.tight_layout(); fig.savefig(F/'rules.png',dpi=140); plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,4))
    for ax,name in zip(axes,['A_frozen','C_hierarchy','D_behavior']):
        r=balanced.loc[balanced.candidate==name].iloc[0]; matrix=np.array([[r.row_tn,r.row_fp],[r.row_fn,r.row_tp]])
        ax.imshow(matrix,cmap='Blues'); ax.set_xticks([0,1],['No alert','Alert']); ax.set_yticks([0,1],['BENIGN','Attack']); ax.set_title(name+' (raw flow counts)')
        for i in range(2):
            for j in range(2): ax.text(j,i,str(int(matrix[i,j])),ha='center',va='center')
    fig.tight_layout(); fig.savefig(F/'confusion.png',dpi=140); plt.close(fig)


def reports(sem,conflicts,robustness):
    comparison=pd.read_csv(R/'comparison.csv'); audit=pd.read_csv(R/'feature_audit.csv')
    selected=json.loads((R/'selection.json').read_text())
    source='https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java'
    feature=['# TASK05 feature research','',
        'All 78 numerical source columns were audited on the 14,042 eligible design rows and three training roles. Exact names, cleaned-stage validity, ranges, p01/p25/median/p75/p95/p99, zeros, uniqueness, redundancy and mixed-day univariate AUC are in feature_audit.csv. Every feature has a physical dimension, unit/meaning caveat and decision in feature_semantics.csv. No assessment or exposed-test labels were screened to choose the feature representation.','',
        'Set A is the original five inputs. Sets B/C/D contain those five plus Flow Duration, Flow IAT Std and SYN Flag Count, preserving leading spaces. They represent intensity/volume, structure, coarse asymmetry, persistence, spacing variability and handshake information. The hierarchical set divides them into small overlapping groups; it is not a larger input list.','',
        'Duration and IAT are correlated with rate/volume, but the research hypothesis is conditional persistence/spacing behavior, not independent univariate information. Positive-subset IAT anchors distinguish spacing spread from a point mass at zero. SYN is supplementary and zero-heavy; its cross-day class association is unstable. In this export it is observed only as 0/1, so it is modeled as absent/present rather than a count of repeated attempts. No single TCP flag establishes maliciousness.','',
        'Alternative flags, forward/backward IAT and active/idle statistics were measured, not added in an uncontrolled search. Bulk counters that are constant cannot help. Forward Header Length.1 and several subflow/segment statistics duplicate or closely derive other measurements (see duplicate_feature_columns.json). Packet variance and std are algebraically related; bytes/s shares volume/size/duration. Port is excluded as a service/scenario shortcut. Window, minimum-segment and header statistics can encode exporter/stack artifacts. These are reasons for compactness and caution, not a proof that rejected measurements contain no conditional information.','',
        'The current five features are not proven sufficient: expanded hierarchical hypotheses improve within-development recall. But expanded flat rules fail and day stress collapses, so this does not isolate an architecture-only or feature-only causal benefit. A separate preregistered ablation would be needed; no additional candidate was added after these outcomes.','',
        'The current upstream exporter source calculates duration-based rates using microseconds, exports IAT statistics and implements integer packet-ratio division. This supports semantic interpretation, but its current revision is not proof of the exact historical exporter binary used for the HF dataset. See [CICFlowMeter BasicFlow.java]('+source+').','',
        '| Input | Dimension | Design median | Design p95 | Missing |','|---|---|---:|---:|---:|']
    for column in COLUMNS:
        a=audit.loc[(audit.panel=='design')&(audit.feature==column)].iloc[0]
        feature.append(f'| `{column}` | {semantics(column)[0]} | {a["median"]:.6g} | {a.p95:.6g} | {a.missing_fraction:.2%} |')
    feature+=['','These validity rates describe the unchanged TASK01 cleaned subset. Raw invalids were already nulled by documented cleaning; they cannot be retrospectively classified as new raw-source defects here. There were no extra complete-case exclusions for the eight selected inputs. Distribution/association is not causal security evidence.']
    (R/'feature_research.md').write_text('\n'.join(feature)+'\n',encoding='utf-8')
    architecture=['# TASK05 implemented fuzzy architecture','',
        'Production A_frozen remains the unchanged five-input/22-rule Mamdani model. A_refit uses the same architecture with fold-training memberships. B_flat8 is a 15-rule eight-input Mamdani model. C_hierarchy has four computationally separate modules (9 load, 6 timing, 6 connection, 6 structure rules), each with its own clipped/aggregated output and centroid, followed by 7 final Mamdani rules: 34 rules total. D_behavior has 6 flooding-like load, 7 persistent-intermittent behavior and 6 connection rules, followed by 6 final Mamdani rules: 25 total.','',
        'Hierarchical inference is physical inputs -> input memberships -> per-module min/max rules -> per-module clipped output union -> module centroids -> module-score memberships -> final min/max rules -> output union -> final centroid. There is no averaging, voting, learned classifier, label lookup or Cartesian enumeration. Modules are computationally independent first-layer mappings, not statistically independent evidence. Timing/structure can encode related behavior.','',
        'All membership anchors are training-only p25/p60/p90, with positive subsets for backward-length variation and IAT spread. Rate/count/variation/duration/IAT use log1p. Size is linear. Exported ratio has domain anchors 0/1/2; SYN has a fixed 0/1 domain. Low/high shoulder sets saturate finite extremes; middle sets are triangular. Duplicated quantiles expand deterministically by one physical unit or 1% of the first anchor. Each three-term partition covers its domain. Intermediate memberships use explicit 25/50/75 score anchors on the 0–100 behavioral scale. These semantic index anchors are not label-tuned.','',
        'All layers use AND=min, OR=max, implication=min clipping, aggregation=max, 201-point centroid quadrature. Same Low/Medium/High/Critical output sets and 25/50/75 category cuts as the original. Final alert threshold is calibrated separately per model/fold. membership_parameters.csv and all nine experimental fold JSON configs record exact numerical parameters and model IDs.','',
        'C requires cross-dimension agreement for strong elevation; D permits one multi-input behavior module to elevate concern, and two to activate Critical. A SYN flag or high packet rate alone cannot establish a definitive attack. Connection modules use the coarse exported ratio; zero does not mean no backward packets. Repeated connection attempts/scanning cannot be reconstructed from these per-flow summaries, so no such definitive module is claimed.','',
        'Missing/non-numeric/Boolean/NaN/infinite/negative inputs abstain globally. Missing subsystem output also forces final abstention, even if other modules fire. SYN values outside [0,1] reject rather than saturate a malformed indicator; other extreme finite inputs saturate with range flags. Fractional values inside the SYN domain interpolate its two terms, although actual source observations are binary. Zero is a valid measurement, never a missing-value replacement. Explanation paths preserve layer name, stable rule ID, antecedent, strength, consequent, raw memberships, module score and final score.','',
        'Example executable API: AdvancedRiskEngine.load(config).predict_one(eight_input_dict); predict_batch(frame,batch_size=1024) is vectorized. Existing PolicyRiskModel can wrap this engine without changing inference evidence. The experimental CLI is scripts/task05_predict.py. Production API/UI are not imported or replaced by these research engines.','']
    for name in NAMES[2:]:
        e=load(name); architecture.extend(['## '+name,'','| Layer | Rule | IF | THEN | Rationale |','|---|---|---|---|---|'])
        for layer,rules in e.config['layers'].items():
            for rule in rules:
                expression=rule['antecedent']; op=' AND ' if 'all' in expression else ' OR '
                text=op.join(f'{a["feature"]} IS {a["term"]}' for a in next(iter(expression.values())))
                architecture.append(f'| {layer} | {rule["id"]} | {text} | {rule["consequent"]} | {rule["rationale"]} |')
    (R/'architecture_design.md').write_text('\n'.join(architecture)+'\n',encoding='utf-8')
    evaluation=['# TASK05 candidate evaluation','',
        '**Reused internal development validation only. No untouched independent holdout exists.**','',
        'The unchanged eligible population is 297,916 flows after excluding 2,529,845 exposed or linked quality-eligible rows, including all Friday and old grouped-test source/group/coarse-signature links. The saved 60,000-row sample preserves IDs, source files and capture days. Design: 14,042 rows. Assessment panel: 45,958 rows (39,159 benign, 6,799 attacks) across three original signature buckets. For fold k, training is (k+2)%3 and policy calibration (k+1)%3. Each comparison record is assessed once. No original group, coarse signature or exact expanded eight-input vector crosses roles. Metadata-only exposed IDs/groups/signatures are checked before fitting.','',
        'TASK02B/TASK04 already assessed this development panel. Expanded feature profiling is new measurement on previously used records; the new architecture outcomes are adaptively reused internal validation. The day-stress hash split is new, but its observations were already development evidence. It is not an untouched temporal test. A_frozen is warm because its historical membership fitting overlaps eligible data; A_refit is the clean within-fold fit comparator.','',
        'The full selection objective was frozen before candidate outcomes in config/fuzzy/task05/protocol.json with source/cache SHA256 hashes. Promotion requires >=5pp mean Balanced group-recall gain over both baselines; positive 500-resample paired signature-bootstrap lower95 against both; mean FPR<=7.5%, every fold<=10%; fold recall no worse than frozen minus2pp; zero abstentions. Additionally each Tuesday/Wednesday/Thursday holdout requires FPR<=10% and recall no worse than its day-clean refit minus2pp. Simpler systems within2pp recall are preferred. No criterion or rule was changed after outcomes.','',
        'Sensitive/Balanced/Conservative calibrate thresholds exclusively on calibration rows to maximize signature-weighted recall at estimated FPR caps10%/5%/1%. Ties and no-alert candidate follow the existing policy procedure. These are not guaranteed rates or attack probabilities. All 45 fold/policy rows and exact thresholds are in metrics.json/fold_policies.json. Thresholds vary by architecture, never fixed arbitrarily across incompatible scores.','',
        '| Candidate | Rules | Precision | Recall ± fold SD | F1 | FPR | FNR | BA | ROC-AUC | AP | Raw TN/FP/FN/TP |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for _,a in comparison.loc[comparison.policy=='Balanced'].iterrows():
        evaluation.append(f'| {a.candidate} | {a.rules} | {a.precision:.4f} | {a.recall:.4f} ± {a.recall_fold_sd:.4f} | {a.f1:.4f} | {a.false_positive_rate:.4f} | {a.false_negative_rate:.4f} | {a.balanced_accuracy:.4f} | {a.roc_auc:.4f} | {a.pr_auc_average_precision:.4f} | {a.row_tn}/{a.row_fp}/{a.row_fn}/{a.row_tp} |')
    evaluation+=['','Rates are means of signature-group-weighted fold metrics; confusion counts are separately pooled RAW flows. One signature receives total weight one, including conflicting-label rows proportionally. Raw confusion cannot reconstruct weighted rates. Full row metrics, support, coverage, abstention and throughput are retained in comparison.csv/metrics.json. All candidates have 100% final rule coverage and zero abstention on this common valid cohort.','',
        '## Multiple operating points','', '| Candidate | Policy | Group recall | Group FPR | Raw recall | Raw FPR |','|---|---|---:|---:|---:|---:|']
    for _,a in comparison.iterrows(): evaluation.append(f'| {a.candidate} | {a.policy} | {a.recall:.4f} | {a.false_positive_rate:.4f} | {a.pooled_row_recall:.4f} | {a.pooled_row_fpr:.4f} |')
    evaluation+=['','C_hierarchy improves mean group recall from21.08% to31.66%, with4.53% FPR compared to4.91%. Conditional paired bootstrap recall-gain95 is approximately[6.79,14.23]pp versus frozen. D_behavior reaches30.18% recall with3.57% FPR and gain interval[5.24,12.67]pp. These indicate a promising internal architectural hypothesis, not independent generalization. Bootstrap resamples signatures, not rows; it is conditional on fitted folds and excludes selection/adaptive reuse and day/host uncertainty.','',
        '## Registered capture-day stability gate','', '| Day | Candidate | Recall | FPR | Unseen labels |','|---|---|---:|---:|---|']
    for a in json.loads((R/'day_stress.json').read_text()):
        evaluation.append(f'| {a["day"]} | {a["candidate"]} | {a["group_metrics"]["recall"]:.4f} | {a["group_metrics"]["false_positive_rate"]:.4f} | {", ".join(a["unseen_labels"]) or "None"} |')
    evaluation+=['','Entire assessment-day signatures are removed from other-day training/calibration; remaining groups split deterministically by task05-day SHA256 suffix. Monday contains only benign traffic and is not used for two-class day stress. A_frozen remains historically warm; only refitted candidates are day-clean for this diagnostic. Tuesday and Wednesday C/D recall are zero, violating the frozen gate. Wednesday C calibration chose the no-alert threshold 100 because no nontrivial calibration recall met the 5% FPR cap; zero assessment recall is then an explicit operating-policy consequence, not proof that score ranking contains no information. The full pipeline still fails the registered practical gate. Thus no new architecture is promoted, despite improved mixed-day internal results. Very small Thursday and rare-class supports prohibit stable attack-category conclusions. See per_class.csv; one Heartbleed assessment example cannot establish reliability.','',
        'Historical TASK02 exposed-test metrics remain unchanged and were not recomputed or used to tune architectures. No Friday labels/scores/errors or old grouped-test individual records entered selection. Near-duplicate bin-boundary dependence remains: TASK04 identified3169 adjacent-bin cross-role representative pairs. Original 698 conflicting-label full numerical groups and308381 extra exact rows remain documented. Severe exclusions change the evaluation population; these rates cannot estimate general traffic prevalence.','',
        'Figures: reports/figures/task05/{comparison,tradeoffs,scores_modules,memberships,rules,confusion}.png. They are regenerated local artifacts, ignored by Git. All unfavorable outcomes are preserved.']
    (R/'candidate_evaluation.md').write_text('\n'.join(evaluation)+'\n',encoding='utf-8')
    failure=['# TASK05 failure analysis','',
        'No single cause explains all errors. Expanded flat B loses nearly all attack recall at calibrated low FPR: mixed rule-output areas still overlap benign scores, and added evidence is insufficient under this particular rule design. This rejects this 15-rule flat hypothesis, not every possible flat eight-input system.','',
        'C/D improve mixed-day low-FPR recall, suggesting that separating timing/structure/load before final aggregation can reduce conflicts for some development behavior. However, their own per-day tests collapse on withheld Tuesday/Wednesday. Wednesday C calibration explicitly chooses a no-alert threshold 100 at the 5% cap: threshold transfer and a feasible operating policy are part of the failure, not only membership/rule discrimination. Packet and timing distributions, attack scenarios and benign applications change across days; previously absent classes cannot be inferred from labels the model never saw. No timing boundary was refitted on the held-out day. Thursday gains are supported by very few rare attack observations and do not rescue the promotion gate.','',
        'SYN export has very low nonzero prevalence, so the connection module is often Low. It cannot count attempts across flows and the integer ratio hides fractional response asymmetry. Timing and structure modules can respond to related long-transfer phenomena, so their corroboration may double-count ordinary downloads. High duration/IAT can reflect exporter timeout/application idle behavior rather than attacks. Membership saturation maps extreme-but-different observations to similar degrees; source-range notices do not repair lost context.','',
        'Intermediate centroids are deliberately compressed behavioral summaries; re-fuzzification can erase within-module distinctions. The final max/min union may concentrate scores around a few bands. Critical was not naturally produced by any new architecture on the design panel; no Critical example was invented. Its absence is a score-range/capacity limitation of these particular memberships and rules, not proof that no critical traffic exists. A high ROC-AUC does not guarantee useful recall at a strict FPR threshold; conversely D has lower global AUC but a better low-FPR internal operating point. Tables/curves retain both facts. More features or deeper layers are not automatically better.','',
        'rule_diagnostics.csv reports each module/final rule activation, mean strength and benign/attack/FP/FN associations; layer_conflicts.json records Low versus High/Critical overlap and coverage. Such associations are not causal contributions under max aggregation. membership_diagnostics.csv records term coverage/saturation. rule correlations are retained by layer. score_distributions.csv shows overlap and category-boundary concentration. explanation_examples.json includes deterministic real design FP/FN evidence generated only after selection; no rules were changed from these examples.','',
        '## Measured layer conflicts on eligible design data','', '| Candidate | Layer | Low/high conflict | Coverage | Median output |','|---|---|---:|---:|---:|']
    for a in conflicts: failure.append(f'| {a["candidate"]} | {a["layer"]} | {a["low_high_conflict_fraction"]:.2%} | {a["coverage"]:.2%} | {a["score_median"]:.4f} |')
    failure+=['','## Per-class coverage — post-selection raw internal counts','',
        'C gains are concentrated in the dominant DoS Hulk class and trade away FTP-Patator coverage. This is development error analysis after selection, not an attack-label-based module or a new tuning round. Rare supports (especially Heartbleed1) do not establish class reliability. The table gives alerts, not calibrated severity.','',
        '| Label | Support | A_frozen alerts | C_hierarchy alerts | D_behavior alerts |','|---|---:|---:|---:|---:|']
    classes=pd.read_csv(R/'per_class.csv')
    for _,a in classes.loc[classes.candidate=='A_frozen'].iterrows():
        others=[int(classes.loc[(classes.candidate==n)&(classes.label==a.label),'alerts'].iloc[0]) for n in ['C_hierarchy','D_behavior']]
        failure.append(f'| {a.label} | {a.support} | {a.alerts} | {others[0]} | {others[1]} |')
    failure+=['','No confident attribution to feature insufficiency versus rule choice is possible from this limited comparison alone. Within-day dependence, known benchmark reuse, conflicting labels, selected-cohort exclusions, rare supports and unobserved host/session metadata remain. A new independent capture and predeclared factorial feature/architecture ablation are needed before claiming unseen-day detection improvement.']
    (R/'failure_analysis.md').write_text('\n'.join(failure)+'\n',encoding='utf-8')
    final=['# TASK05 final engineering decision','',
        '**Keep production unchanged. C_hierarchy is a promising research candidate, not a promoted model.**','',
        'Implemented and executed a systematic78-column audit, expanded eight-input flat Mamdani, four-module hierarchy and three behavior-module hierarchy. Original/refitted baselines are preserved. Exact features, membership parameters, rule rationales, intermediate outputs, configs, policy thresholds and actual metrics are versioned. No classifier, probability model or arbitrary score averaging was introduced.','',
        'C_hierarchy has the highest internal Balanced recall31.66% versus frozen21.08%, with FPR4.53% versus4.91%. D_behavior reaches30.18% recall/FPR3.57% with fewer rules. Both show positive conditional group-bootstrap recall gains; neither passes the registered day stability gate. Their Tuesday/Wednesday holdout recall is zero. Highest internal recall therefore does not justify production promotion. No post-outcome tuning was performed.','',
        '## Frozen artifacts and production','',
        'config/fuzzy/task05/protocol.json records the pre-result architecture and selection freeze. All15 fold configurations and fold_policies.json are saved. recommendation.json points back to config/fuzzy/task04/selected_v4.json. Production scoring ID remains ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b with its existing policies49.632522849397134/51.809236850031304/59.465890915130174. The FastAPI backend, React source, styles, all pages, metadata, catalog, API schema and previous reports are unmodified. Research files do not change active model loading.','',
        '## Explainability and execution','',
        'explanation_example.json contains a real eligible design row, label outside inference, full eight-feature memberships, per-module rules/strengths/centroids, final-layer rules/strengths and risk result. example_input.json has inputs only. Example command:','',
        '```powershell',
        '.\\.venv\\Scripts\\python.exe scripts/task05_predict.py --model config/fuzzy/task05/C_hierarchy_fold0.json --input reports/fuzzy/task05/example_input.json --policy-key C_hierarchy_0 --policy Balanced',
        '```','',
        'Changing policy uses the existing transparent PolicyRiskModel wrapper and changes only the alert decision. Model-specific frozen fold thresholds are research artifacts, not new production policies. Invalid/unknown inputs abstain; intermediate output failure forces final abstention. Missing categories are reported as unavailable rather than fabricated.','',
        '## Performance and robustness','', '| Candidate | Design rows | Seconds | Rows/s | Max +0.1% score change | Near-anchor2ppm max |','|---|---:|---:|---:|---:|---:|']
    for a in robustness: final.append(f'| {a["candidate"]} | {a["design_rows"]} | {a["seconds"]:.6f} | {a["rows_per_second"]:.0f} | {a["max_change_plus_0_1_percent"]:.6f} | {a["near_anchors_2ppm_max_change"]:.8f} |')
    final+=['','CPU only, excluding disk IO. Per-layer centroid workspace is1,646,592 bytes for1024x201 float64; additional temporaries and retained explanation arrays increase total memory. The60k x78 research cache is bounded to tens of MB of numeric data; joins use DuckDB1GB memory cap/two threads. Full2.8M table is not materialized. No new dataset download. Hierarchies are several times slower than flat inference because they perform four/five Mamdani layers; measured desktop throughput remains suitable for experiments but is not a production SLA. Perturbation results cover1000 design rows with discrete SYN held unchanged, not a universal robustness bound.','',
        '## Reproducibility and validation','',
        'Run scripts/task05_research.py once to regenerate the eligible feature cache; scripts/task05_experiment.py freeze is one-time and refuses overwrite. The registered evaluate phase reproduces all candidate fitting/calibration/assessment/day-stress results and selection without source changes. scripts/task05_validate.py separately reproduces15 models,15 calibration policy sets,45 fold/policy metrics and15 day-stress metric sets, verifies exposed exclusions and historical hashes. scripts/task05_reports.py regenerates post-selection diagnostics, figures and these reports. All full prediction/curve/research caches are ignored under .tmp/task05. New small source/configs/numerical summaries are versioned. validation.json records final tests/build/API results.','',
        'Independent generalization remains unproven. Prior development assessments were adaptively reused, signature boundaries do not remove all near-duplicate/host dependencies, and capture-day scenario shift dominates stress. The educational web app remains intact; no improved-model integration is authorized by the failed promotion gate. Future work should predeclare a compact feature ablation and evaluate newly reserved independent network captures, retaining visible false-negative/false-alarm limitations. No remote Git operation is part of this workflow.']
    (R/'final_report.md').write_text('\n'.join(final)+'\n',encoding='utf-8')


if __name__=='__main__': diagnostics()
