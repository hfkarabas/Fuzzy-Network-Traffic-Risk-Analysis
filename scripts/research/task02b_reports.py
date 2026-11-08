"""Read-only analysis of saved internal results; never refit or read old test data."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.refinement import SEED
from task02b_experiment import R,C,D,dump

FIG=ROOT/'reports/figures/task02b'

def md(frame):
    rows=['| '+' | '.join(map(str,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    rows+=['| '+' | '.join(str(v).replace('|','\\|') for v in row)+' |' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(rows)

def intervals(predictions,policies):
    results={}
    f=predictions.copy(); weights=1/f.groupby('signature').source_row_id.transform('size').to_numpy()
    for name in ['Sensitive','Balanced','Conservative']:
        thresholds=f.fold.map(lambda fold:policies[f'A_frozen_fold{fold}'][name]['threshold']).to_numpy()
        y=f.truth.to_numpy(dtype=bool); alert=f.score.to_numpy()>=thresholds
        sums=pd.DataFrame({'signature':f.signature,'tp':weights*(y&alert),'fn':weights*(y&~alert),
                           'fp':weights*(~y&alert),'tn':weights*(~y&~alert)}).groupby('signature',sort=True).sum().to_numpy()
        rng=np.random.default_rng(SEED); values=[]
        for _ in range(500):
            tp,fn,fp,tn=sums[rng.integers(0,len(sums),len(sums))].sum(axis=0)
            values.append([tp/(tp+fn),fp/(fp+tn),(tp/(tp+fn)+tn/(tn+fp))/2])
        interval=np.quantile(values,[.025,.975],axis=0)
        results[name]={key:list(map(float,interval[:,j])) for j,key in enumerate(['recall_95','fpr_95','balanced_accuracy_95'])}
    return results

def render():
    FIG.mkdir(parents=True,exist_ok=True)
    lineage=json.loads((R/'lineage.json').read_text()); design=json.loads((R/'design_diagnostics.json').read_text())
    cv=json.loads((R/'cv_metrics.json').read_text()); selection=json.loads((R/'selection.json').read_text())
    robust=json.loads((R/'robustness.json').read_text()); valid=json.loads((R/'validation.json').read_text())
    policies=json.loads((C/'selected_policies.json').read_text()); fold_policies=json.loads((C/'fold_policies.json').read_text())
    uncertainty=json.loads((R/'uncertainty.json').read_text()); plan=json.loads((C/'candidate_plan.json').read_text())
    populations=pd.read_csv(R/'eligible_population_classes.csv')
    test_output=(R/'test_results.txt').read_text(encoding='utf-8') if (R/'test_results.txt').exists() else 'not yet executed'
    # Summaries explicitly distinguish group-weighted fold means from integer row totals.
    summaries=[]
    for candidate in plan['candidates']:
        for policy in ['Sensitive','Balanced','Conservative']:
            rows=[x for x in cv if x['candidate']==candidate and x['policy']==policy]
            record={'candidate':candidate,'policy':policy,'benign_rows':sum(x['benign_support'] for x in rows),
                    'attack_rows':sum(x['attack_support'] for x in rows),'groups':sum(x['signature_groups'] for x in rows)}
            for key in ['precision','recall','f1','false_positive_rate','false_negative_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']:
                record[key]=float(np.mean([x['group_metrics'][key] for x in rows]))
            for key in ['tn','fp','fn','tp']: record['row_'+key]=int(sum(x['row_metrics']['confusion_matrix'][key] for x in rows))
            record['pooled_row_fpr']=record['row_fp']/(record['row_fp']+record['row_tn'])
            record['pooled_row_recall']=record['row_tp']/(record['row_tp']+record['row_fn'])
            record['minimum_fold_recall']=min(x['group_metrics']['recall'] for x in rows); record['maximum_fold_recall']=max(x['group_metrics']['recall'] for x in rows)
            record['minimum_fold_fpr']=min(x['group_metrics']['false_positive_rate'] for x in rows); record['maximum_fold_fpr']=max(x['group_metrics']['false_positive_rate'] for x in rows)
            summaries.append(record)
    summaries=pd.DataFrame(summaries); summaries.to_csv(R/'comparison_summary.csv',index=False)
    selected_oof=pd.read_parquet(D/'A_frozen_oof.parquet')
    ci=intervals(selected_oof,fold_policies); dump(R/'selected_policy_uncertainty.json',ci)
    balanced=summaries.loc[summaries.policy=='Balanced'].copy()
    feasibility=[]
    for candidate in plan['candidates']:
        for policy in ['Sensitive','Balanced','Conservative']:
            values=[x for x in cv if x['candidate']==candidate and x['policy']==policy]
            feasibility.append({'candidate':candidate,'policy':policy,
                                'nontrivial_calibration_folds':sum(bool(x['calibration_policy'].get('nontrivial_recall_feasible')) for x in values),
                                'assessment_fpr_cap_exceeded_folds':sum(x['group_metrics']['false_positive_rate']>x['calibration_policy']['fpr_cap']+1e-12 for x in values)})
    feasibility=pd.DataFrame(feasibility); feasibility.to_csv(R/'policy_feasibility.csv',index=False)
    compact=balanced[['candidate','precision','recall','f1','false_positive_rate','false_negative_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']].round(6)
    # Nominal old grouped FPR precision uses user-supplied aggregate counts ONLY.
    p=114/150; z=1.959963984540054; n=150
    center=(p+z*z/(2*n))/(1+z*z/n); half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    old_ci=[center-half,center+half]
    audit=f'''# Evaluation integrity and partition lineage

## Historical exposure audit

TASK02 grouped memberships used 8,217 development-train records; its threshold used
1,753 validation labels; its 1,750 test records were inspected. Day memberships used
1,607,145 Monday–Wednesday records, threshold selection used 422,299 Thursday labels,
and 666,572 eligible Friday test records were inspected. Fixed rule hypotheses were
hand-authored before tests; training diagnostic panels used 8,217 grouped and 7,011
class-capped day-training rows. Both historical scores and error examples are
exposed evidence. Their individual labels, scores, errors and per-class behavior
were NOT loaded for TASK02B refinement or selection. The old grouped configuration
is read as the prescribed unchanged baseline, not reverse-engineered from its tests.
Metadata/features of exposed rows are used exclusively inside an exclusion query.

Original development sampling capped classes rather than preserving prevalence;
the old test had only 150 benign versus 1,600 attacks. A nominal Wilson interval for
the supplied aggregate 114/150 FPR is {old_ci[0]:.4f}–{old_ci[1]:.4f}, before accounting
for dependence or sampling bias. It is too small and unrepresentative for a precise
operational low-FPR claim. Original temporal classes vary sharply by capture day.

## Exact eligible population and exclusions

Begin with 2,827,761 quality-eligible original fuzzy-ready flows. The 2,982 unavailable
input rows are outside this quality-eligible universe. Conservatively mark every
Friday record, including previously quarantined Friday flows, plus every original
TASK02 grouped-test row. Direct exposure marks {lineage['direct_exposed_records']:,}
eligible records. Exclude all original observation groups and coarse five-input
signatures linked to those marks: {lineage['excluded_rows']:,} rows excluded in total,
including {lineage['additional_linked_rows_excluded']:,} additional linked rows.
Remaining eligible population: **{lineage['eligible']:,}** flows across Monday–Thursday.

{md(pd.DataFrame(lineage['eligible_day_counts']))}

Original source IDs, observation-group IDs, source filenames, capture days and old
partition lineage remain available in ignored Parquet manifests. There are
{lineage['blocked_groups']:,} directly exposed original groups and
{lineage['blocked_signatures']:,} blocked coarse signatures. Coarse signatures round
log1p of rate, volume, mean size and response std to a 0.10 grid, keeping the integer
direction ratio exact. Exact selected-feature repeats necessarily share a signature;
near clones within a bin also share it. All original groups were checked to map to
one signature. This is not exhaustive near-duplicate detection: close points across
bin boundaries and host/session dependencies can remain.

Excluding roughly 90% of the quality-eligible source creates a major selection
shift. The retained population has {int(populations.loc[populations.label=='BENIGN','rows'].sum()):,}
benign and {int(populations.loc[populations.label!='BENIGN','rows'].sum()):,} attack flows.
Nearly all web-attack observations disappear through conservative linkage; tiny
remaining category supports cannot justify generalization claims. See
eligible_population_classes.csv for exact remaining category/day counts.

## New internal roles

Sample {lineage['sample_rows']:,} rows uniformly by deterministic source-row hash,
without label stratification, AFTER exclusions. The sample has
{lineage['sample_groups']:,} signatures. Reserve {lineage['role_counts']['design']:,} design
rows in separate signature groups; only that panel informs rule/feature diagnostics.
The other {sum(int(v) for k,v in lineage['role_counts'].items() if k!='design'):,} rows rotate
through three fixed signature buckets: for assessment k, calibration is (k+1)%3
and training (k+2)%3. Every comparison row is assessed once. Design groups never
enter fold assessment or calibration. No original group/signature crosses roles.
Memberships use training only; alert thresholds use calibration only; assessment
labels compare the predeclared candidates. Signature-weighted metrics assign one
total unit per signature, with its rows sharing that unit; raw row metrics are also
retained. Capture days are recorded and analyzed, not silently assumed independent.

## No untouched holdout claim

TASK01 full-data EDA and previous training/validation summaries already viewed this
benchmark. The historical frozen model even fitted memberships on some newly
eligible assessment rows and inherits quantiles informed by its original training
population. Thus A_frozen is a warm, contextual comparator, NOT an unbiased refit.
A_refit uses the same training-only roles as B/C and is the fair scoring baseline.
No new shuffled subset is called an independent test. All comparison results and
post-selection leave-Wednesday-out stress results are **internal validation**.
The latter is selected-architecture stability only, with no model reselection.

## Fixed selection rule and execution checks

Before diagnostics, task02b_protocol.json fixed a maximum four-candidate search
(plus D only if defensible), three policies, group roles and selection rule.
Before comparison, candidate_plan.json froze exact candidate changes and code hashes.
Primary criterion: mean Balanced-policy group-weighted balanced accuracy, mean
assessment FPR <=0.075; replacing the baseline also needs >=0.02 improvement over
A_refit and a positive paired group-bootstrap lower bound. Otherwise retain the
original model. Assessment itself participates in model selection; its metrics
are not an independent estimate of the selected candidate's future performance.
Protocol/code/model hashes, per-fold support and every unfavorable result are saved.
Validation checked all 60,000 sample rows for blocked IDs/groups/signatures, all
candidate hashes and all 36 policy metric rows. No exposed record entered refinement.
Historical baseline preservation is separately SHA256 verified; dataset files and
all TASK01/TASK02 models, reports and tests remain unchanged.
'''
    (ROOT/'reports/fuzzy/evaluation_integrity.md').write_text(audit,encoding='utf-8')
    (R/'evaluation_integrity.md').write_text(audit,encoding='utf-8')
    feature=pd.read_csv(R/'feature_audit.csv')
    (ROOT/'reports/fuzzy/feature_sufficiency.md').write_text(f'''# Feature sufficiency audit — TASK02B

Only the {design['design_rows']:,}-row eligible design panel was used for feature
screening. No exposed or comparison-assessment feature/label associations informed
feature changes. All exact names, missingness, zero frequency, ranges, medians,
p95, correlations and descriptive per-day univariate AUCs are in
task02b/feature_audit.csv and design_feature_correlations.csv. These are descriptive
associations, not trained classifiers or feature-importance explanations.

{md(feature[['feature','invalid_percent','zero_percent','max_abs_existing_spearman','univariate_direction_stable_across_days']].round(6))}

Rate and integer directional ratio alone do not capture applications, destination
semantics, host behavior, cross-flow scan frequency or complete TCP handshakes.
Mean size and backward size variation correlate about 0.893 on this design panel.
One identical five-input vector has contradictory traffic labels in this panel.
The five inputs are NOT established as sufficient for attack identification.

Duration and IAT statistics have maximum rank correlations 0.965–0.999 with the
existing inputs and can reintroduce redundant timing. Flow Bytes/s is related to
packet rate and packet size; its per-day direction alone is not evidence of
incremental value. Backward count has correlation about 0.897 with existing features,
while integer ratio already provides approximate direction. SYN/ACK/PSH exports
are binary context, not rates or proof of handshake failure. Their label association
changes across days and scenario mix. Header length strongly tracks volume
(correlation about 0.977), with some unavailable measurements; minimum segment size
has extraction/stack/artifact concerns and inconsistent cross-day behavior.
No identifiers or ports are candidates. Zero measurements are not treated as invalid.

Feature screening is uncertain: Monday has only benign traffic and retained
Thursday attack support is tiny. Direction-consistent AUC flags therefore do NOT
establish stability or causation. Per-day attack counts are in partition_classes.csv.
Given redundancy, unstable associations and no convincing conditional benefit,
Candidate D was explicitly NOT implemented. This decision was frozen before any
candidate comparison. A six/seven-input system is deferred, not rejected forever.
The current task evaluates two compact five-input refinements, preserving physical
interpretability and avoiding complexity unsupported by eligible development evidence.
''',encoding='utf-8')
    rule=pd.read_csv(R/'design_rule_diagnostics.csv'); dist=pd.read_csv(R/'design_score_distributions.csv')
    sensitivity=pd.read_csv(R/'design_rule_removal_sensitivity.csv')
    (ROOT/'reports/fuzzy/improvement_diagnostics.md').write_text(f'''# Development-only diagnostics — TASK02B

Diagnostic scope: the {design['design_rows']:,}-row reserved design panel
({design['benign']:,} benign, {design['attack']:,} attacks; {design['signature_groups']:,}
signature groups). This panel is separate from model-comparison roles. The original
grouped TASK02 model and embedded threshold 25 are diagnostic reference only.
Its design signature-weighted FPR is {design['baseline_metrics']['false_positive_rate']:.6f},
recall {design['baseline_metrics']['recall']:.6f}, ROC-AUC
{design['baseline_metrics']['roc_auc']:.6f}. These are not old test measurements.

## Score overlap and threshold confusion

{md(dist.round(6))}

Benign median score exceeds attack median. Medium-only R03 has centroid around
43.333, which exceeds the embedded binary threshold 25. Therefore benign-looking
ambiguous volume patterns become alerts even when the category is only Medium.
This is a scoring-versus-operating-policy distinction, not numerical failure.
The full design PR/FPR-recall tradeoff is saved, rather than checking six coarse
thresholds. Sensitive/Balanced/Conservative policies target estimated FPR caps of
10%/5%/1%; calibration targets are not future guarantees.

## Rule diagnostics

{md(rule[['id','consequent','activation_fraction','mean_strength','benign_fraction','attack_fraction','active_false_positives','active_false_negatives']].round(6))}

R06/R07 provide broad Medium evidence on benign flows. R10/R11's small, intensive
patterns and R19's few/small/forward concern are more frequent among benign design
rows than attacks. R14/R15 response-pattern concerns are comparatively specific
on this panel, but this can reflect Wednesday scenario composition. Low baseline
rules activate on attacks as well. Removing all Low patterns would suppress honest
counter-evidence and would not solve feature overlap. Low versus High/Critical
activation conflicts occur in {design['low_high_conflict_fraction']:.4%} of design rows.
Max aggregation means correlated same-consequent rules can be redundant and frequent
activation is not an additive score contribution. design_rule_correlations.csv
quantifies redundancy; design_rule_removal_sensitivity.csv measures algorithmic
leave-one-rule-out score changes on the first 2,048 design rows. This is not causal
evidence about malicious behavior. A few sample sensitivities:

{md(sensitivity[['rule','mean_score_contribution_on_retained_coverage','max_abs_score_change','no_coverage_after_removal']].round(6))}

## Membership coverage and sensitivity

design_memberships.csv records all term frequencies, mean degrees, zero/full
activation and benign/attack contrasts. Old training quantiles are class-stratified
and therefore shift the meaning of ordinary versus unusual traffic relative to
this eligible population. Positive-only variation anchors avoid the zero mass
but do not establish attack relevance. Integer directional ratio loses fractional
information: zero is forward domination, not proof of no response. Saturating
shoulders safely handle large measurements, but many samples at full membership
can compress scores. Log1p improves numeric scale without creating discriminative
information absent from the aggregates. Membership diagrams are inspected as
training parameters only; previous exposed test plots are not reused.

Candidate B tests a benign-training reference and broader central quantiles while
keeping every rule. Candidate C additionally narrows concern patterns and weakens
broad Medium rules. Both are hypotheses frozen before comparison; their negative
results are retained. On the selected baseline, +/-0.1% input perturbations change
mean score by about 0.012 and worst checked score by under 0.15. Moving all input
membership coordinates by +/-1% can move some scores by several points; membership
design uncertainty matters even when numerical inference is stable. These
post-selection diagnostic perturbations were not used to search another candidate.
''',encoding='utf-8')
    uncertainty_table=pd.DataFrame([{'candidate':name,'paired_difference_CI_low':v['paired_balanced_accuracy_difference_95'][0],
                                      'paired_difference_CI_high':v['paired_balanced_accuracy_difference_95'][1]} for name,v in uncertainty.items()])
    policy_table=summaries.loc[summaries.candidate=='A_frozen',['policy','precision','recall','false_positive_rate','pooled_row_fpr','pooled_row_recall','false_negative_rate','balanced_accuracy','minimum_fold_recall','maximum_fold_recall','minimum_fold_fpr','maximum_fold_fpr']].round(6)
    (ROOT/'reports/fuzzy/candidate_comparison.md').write_text(f'''# Candidate comparison — internal validation only

## Predeclared candidates and unchanged baseline

A_frozen: exact TASK02 grouped scoring model, 22 rules, no parameter changes.
This is a contextual warm baseline, not a leakage-clean fit. A_refit: the original
22-rule procedure fitted separately on each training role, used as the fair baseline.
B_membership: same 22 rules, benign-training p25/p75/p95 references and fixed packet
size/volume domain floors. C_rules: B memberships plus 18 explicit IF–THEN rules;
demote sparse-many and intensive-few baselines, require volume corroboration for
critical/small-packet and varied-large concerns, remove broad few-small/forward
and intensive-small/uniform concerns. D: not implemented for the documented audit
reasons. Output sets, min/max Mamdani inference, centroid and risk cuts 25/50/75
are unchanged for every candidate. Exact configurations for each fold are saved.

## Fair rotating group-role comparison

Assessment support: {int(balanced.iloc[0].benign_rows):,} benign and
{int(balanced.iloc[0].attack_rows):,} attack rows, {int(balanced.iloc[0].groups):,}
signature groups, across three assessments. Each group is trained on in one rotation,
calibrated on in another and assessed only when excluded from both those roles.
No future final test is claimed. Main table entries are means of group-weighted
fold metrics using Balanced policy; A_frozen's previous fit exposure is explicit.

{md(compact)}

Raw row confusion totals below use the corresponding fold-specific thresholds;
they are not the fractional group confusion counts underlying the macro means.

{md(balanced[['candidate','row_tn','row_fp','row_fn','row_tp','benign_rows','attack_rows']])}

All 36 candidate/fold/policy metric rows, thresholds, row/group confusion matrices,
support, ROC/AP, rule coverage and abstention are in cv_metrics.json and
candidate_metrics.csv. Every valid assessment row activated rules; abstention is
zero on this quality-filtered panel, not on arbitrary external inputs.

## Uncertainty and stability

500 paired bootstrap resamples preserve signature groups and within-group duplicate
ties. These confidence intervals concern pooled out-of-fold group-weighted balanced
accuracy differences, while the predefined selection ranking uses the mean of fold
balanced accuracies. Both checks were required; neither B nor C improves either.
The intervals condition on fitted folds, omit model-selection uncertainty, and do
not represent independent hosts or collection sessions.

{md(uncertainty_table.round(6))}

B and C are worse than A_refit. Neither reaches the required +0.02 improvement or
a positive bootstrap lower bound. Therefore **retain A_frozen**, the exact original
baseline, under the predetermined fallback; its contextual score is not evidence
of a newly improved detector. No additional rule or threshold search followed these
unfavorable results. Candidate C reduces false alarms largely by losing attack recall.
Here 'worse' refers to the preregistered operating criterion: C's mean ROC-AUC
actually rises to about 0.692 versus 0.606 for A_refit. That favorable global-ranking
result is retained, but it does not offset its poor low-FPR alert recall. B also
improves mean AUC while failing the chosen operating criterion. The objective was
not changed to favor those secondary improvements after inspecting results.

## Alert policies are a separate operating tradeoff

For the unchanged baseline, group-weighted fold means and ranges are:

{md(policy_table)}

Exact frozen integration thresholds (from bucket 1 calibration only) are Sensitive
{policies['policies']['Sensitive']['threshold']:.12f}, Balanced
{policies['policies']['Balanced']['threshold']:.12f}, Conservative
{policies['policies']['Conservative']['threshold']:.12f}. CV uses a separately
calibrated threshold per fold, so these fold means are not an independent evaluation
of the final single integration policy. Targets are 10%/5%/1% estimated FPR.
Realized assessment FPR can exceed them. selected_policy_uncertainty.json gives
group-bootstrap intervals for pooled policy recall/FPR/balanced accuracy. These
policies reduce nuisance alerts at substantial recall cost; scores and their AUC
are identical. No improvement in the fuzzy scoring model is claimed.
The caps explicitly target signature-group-weighted FPR, not per-flow FPR.
The retained model's Balanced pooled ROW false-positive rate is
{summaries.loc[(summaries.candidate=='A_frozen')&(summaries.policy=='Balanced'),'pooled_row_fpr'].iloc[0]:.4%},
well above its approximately 5% GROUP-weighted rate. Repeated benign patterns change
the two empirical distributions. Both must remain visible; the target must never
be advertised as a demonstrated 5% per-flow false-alarm guarantee.

Feasibility audit (out of three folds): nontrivial means positive calibrated recall
within the target cap; a no-alert threshold can meet FPR without useful recall.

{md(feasibility)}

The supplemental leave-Wednesday-out stress (day_stress.json) excludes shared
signatures across days, uses other-day training/calibration, and is not used for
reselection. DoS families and Heartbleed are absent from its training population.
The frozen baseline remains warm because it was historically fitted on some such
records; only A_refit is training-role-pure there. It supplies no independent
temporal generalization claim.
''',encoding='utf-8')
    final=f'''# TASK02B final engineering decision

**No scoring-model improvement was supported. Retain the TASK02 baseline.**

## Delivered work

Audited exposure and model lineage; excluded {lineage['excluded_rows']:,} exposed or
coarse-linked flows; established a {lineage['eligible']:,}-flow eligible population;
sampled 60,000 without class balancing; separated 14,042 design rows from 45,958
rotating internal validation rows. Compared the original frozen model, a fair
fold-refitted baseline, benign-reference memberships and an 18-rule refinement.
No extra feature was justified. All unfavorable results and old baseline artifacts
are retained. No old test records were rescored or used for refinement/selection.

## Final integration artifacts

- config/fuzzy/task02b/selected_v2.json: verbatim retained scoring model, v1 model
  identity {valid['selected_model_id']}.
- config/fuzzy/task02b/selected_policies.json: frozen Sensitive/Balanced/Conservative
  operating thresholds with explicit calibration FPR targets, not guarantees.
- config/fuzzy/task02b/selected_manifest.json: candidate, versioned source hashes,
  22 rules / five inputs / internal-evidence status.
- src/fuzzy_network_risk/policy.py: PolicyRiskModel applies the selected operating
  policy without changing risk score, category, memberships or rule evidence.

The wrapper must be used for v2 policy alerts. Raw engine.predict_one retains the
historical embedded threshold 25 for strict TASK02 compatibility. No category cuts,
consequents or score parameters are silently changed. Stable explanation keys
and the complete activated-rule evidence remain available. Real eligible-design
examples of all four categories plus explicit invalid-input abstention are in
explanation_examples.json; synthetic robustness workloads are labeled as such.
The three FPR targets are signature-group-weighted. Balanced pooled raw-row FPR
is about 15.71%, not 5%; group and row rates measure different distributions.

## Main internal findings

{md(compact)}

These are internal model-selection measurements, not final-test performance. Warm
baseline fit overlap, severe population exclusions, limited scenario coverage,
rare categories, within-day dependencies and coarse-bin boundary effects remain.
The new policies make low-FPR tradeoffs explicit but miss many attacks. Neither
probability calibration, calibrated severity nor production readiness is established.

## Robustness and execution evidence

All candidate configurations and source freezes validate. All 36 policy metrics
were reproduced from saved predictions. Single/batch scores match bitwise.
Robustness covers valid zeros, huge finite values, sparse flows, benign-like bulk
workloads, direction imbalance, small-packet bursts, invalid/missing/infinite input,
near-boundary and small-perturbation measurements. Invalid cases abstain; no zero
imputation. +/-0.1% input changes have maximum observed score change under 0.15;
15 near-anchor checks at two-parts-per-million have maximum change
{robust['near_membership_anchors_max_change_at_2ppm']:.8f}. This is bounded empirical
robustness, not a proof over all possible traffic. Membership coordinate uncertainty
has larger effects and remains documented.

Measured selected-model inference: {valid['throughput_rows_per_second']:.0f} rows/s
for {valid['inference_rows']:,} design flows in {valid['inference_seconds']:.6f} seconds,
CPU only, excluding disk IO and diagnostics. A centroid workspace is 3,293,184 bytes;
multiple temporaries add to this, with outer batches recommended for large files.
DuckDB is capped at 1 GB, desktop memory budget approximately 16 GB. No dataset
download, GPU, conventional ML classifier or neural network was used.

## Tests and preservation

{test_output.strip()}

Historical artifact hashes are checked by scripts/research/task02b_integrity.py; source
datasets, TASK01 outputs, TASK02 configs/reports/scripts/tests and existing prediction
Parquet files are unchanged. New Parquet/sample/candidate-curve artifacts stay in ignored
data/fuzzy_v2; the full design threshold curve is separately ignored under reports.
Figures stay in ignored reports/figures/task02b. Small configurations,
numeric summaries, reports, tests and 5 representative explanations are versioned.
The selected configuration was copied, not overwritten in its original location.
No remote Git operation is part of this workflow.

## TASK03 readiness

Ready for an educational local UI using PolicyRiskModel, explicit policy selection,
the five exact physical-unit inputs, model/policy IDs, categories, complete fuzzy
evidence, translation keys and invalid-input states. Show that target FPR is a
calibration estimate and many attacks are missed. Do not silently present an
educational score as a trusted attack detector. No web interface was built here.
Future scientific revision requires new training-only hypotheses and a genuinely
new authorized capture/holdout; repeatedly tuning against the exposed Friday or
old grouped tests remains prohibited.
'''
    (ROOT/'reports/fuzzy/task02b_final_report.md').write_text(final,encoding='utf-8')
    # Focused scientific plots: design only or clearly labeled internal assessments.
    ds=pd.read_parquet(D/'design_baseline_scores.parquet')
    concentration=ds.score.value_counts().head(10).rename_axis('score').rename('rows').reset_index()
    concentration['design_percent']=concentration.rows/len(ds)*100
    concentration.to_csv(R/'design_score_concentration.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for label,mask in [('Benign',~ds.truth),('Attack',ds.truth)]:
        values=ds.loc[mask,'score'].to_numpy(); axes[0].hist(values,bins=np.arange(0,102,2),alpha=.5,density=True,label=label)
        ordered=np.sort(values); axes[1].plot(ordered,np.arange(1,len(ordered)+1)/len(ordered),label=label)
    axes[0].set(xlabel='Risk score',ylabel='Density',title='Eligible design panel'); axes[1].set(xlabel='Risk score',ylabel='Empirical CDF',title='Design score overlap')
    for ax in axes: ax.legend()
    fig.tight_layout(); fig.savefig(FIG/'design_score_overlap.png',dpi=150); plt.close(fig)
    curve=pd.read_csv(R/'design_threshold_tradeoff.csv')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot(curve.recall,curve.precision); axes[0].set(xlabel='Recall',ylabel='Precision',title='Design group-weighted PR tradeoff')
    axes[1].plot(curve.fpr,curve.recall); axes[1].set(xlabel='FPR',ylabel='Recall',title='Design group-weighted FPR tradeoff')
    for cap in [.01,.05,.1]: axes[1].axvline(cap,linestyle=':',alpha=.4)
    fig.tight_layout(); fig.savefig(FIG/'design_policy_tradeoff.png',dpi=150); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for candidate in plan['candidates']:
        rows=sorted([x for x in cv if x['candidate']==candidate and x['policy']=='Balanced'],key=lambda r:r['fold'])
        axes[0].plot([0,1,2],[r['group_metrics']['balanced_accuracy'] for r in rows],marker='o',label=candidate)
        axes[1].plot([0,1,2],[r['group_metrics']['recall'] for r in rows],marker='o',label=candidate)
    axes[0].set(xlabel='Internal assessment fold',ylabel='Balanced accuracy'); axes[1].set(xlabel='Internal assessment fold',ylabel='Recall at calibrated 5% FPR target')
    for ax in axes: ax.legend(fontsize=8); ax.set_xticks([0,1,2])
    fig.tight_layout(); fig.savefig(FIG/'internal_candidate_stability.png',dpi=150); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    axes[0].bar(rule.id,rule.benign_fraction,label='Benign',alpha=.6); axes[0].bar(rule.id,rule.attack_fraction,label='Attack',alpha=.5)
    axes[0].set_ylabel('Meaningful activation fraction'); axes[0].set_title('Design rule associations'); axes[0].tick_params(axis='x',rotation=90); axes[0].legend()
    axes[1].bar(sensitivity.rule,sensitivity.mean_score_contribution_on_retained_coverage)
    axes[1].set_title('Design leave-one-rule-out sensitivity'); axes[1].set_ylabel('Mean score: full minus removed'); axes[1].tick_params(axis='x',rotation=90)
    fig.tight_layout(); fig.savefig(FIG/'design_rule_diagnostics.png',dpi=150); plt.close(fig)
    print('Generated five English reports, internal comparison summaries, uncertainty and four figures.',flush=True)

if __name__=='__main__': render()
