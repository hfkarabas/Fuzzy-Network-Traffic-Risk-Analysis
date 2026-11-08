"""Reports/figures from frozen configurations and saved predictions; no refitting."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_fuzzy import ROOT,REPORT,CONFIG,GENERATED,connect,write_json
from fuzzy_network_risk.engine import MamdaniRiskEngine,LEVELS
from fuzzy_network_risk.membership import membership
from fuzzy_network_risk.data import INPUTS,LABEL,SEED

FIG=ROOT/'reports/figures/fuzzy'

def table(frame):
    rows=['| '+' | '.join(map(str,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    for row in frame.itertuples(index=False,name=None):
        rows.append('| '+' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in row)+' |')
    return '\n'.join(rows)

def pct(value): return f'{value*100:.3f}%'

def overlap_diagnostics():
    c=connect(); result={}
    fields=','.join('"'+v+'"' for v in INPUTS)
    sources={'grouped':"SELECT * FROM development",'day':"SELECT f.*,s.temporal_partition AS day_partition FROM full_data f JOIN sessions s USING(source_row_id) WHERE s.temporal_partition!='quarantine'"}
    for scenario,source in sources.items():
        partition='partition' if scenario=='grouped' else 'day_partition'
        row=c.execute(f'''SELECT count(*),coalesce(sum(test_rows),0),coalesce(sum(k),0) FROM
          (SELECT count(*) k,sum(({partition}='test')::INTEGER) test_rows
           FROM ({source}) GROUP BY {fields} HAVING count(DISTINCT {partition})>1)''').fetchone()
        # Selected-input equality can hide differing other original features.
        result[scenario]={'five_input_groups_spanning_partitions':int(row[0]),
                          'test_rows_in_those_groups':int(row[1]),'total_rows_in_those_groups':int(row[2]),
                          'definition':'Exact equality of five selected input values; full-original-feature groups are still disjoint'}
    write_json(REPORT/'projected_input_overlap.json',result)
    return result

def make_figures(models,metrics):
    FIG.mkdir(parents=True,exist_ok=True)
    for scenario,e in models.items():
        fig,axes=plt.subplots(2,3,figsize=(14,8))
        for ax,(key,f) in zip(axes.flat,e.config['features'].items()):
            upper=min(f['upper'],4.) if key=='balance' else f['upper']
            vertices=[v for spec in f['sets'].values() for v in spec['parameters'] if 0<=v<=upper]
            x=np.unique(np.r_[np.linspace(0,upper,1000),vertices])
            if key=='size':
                x=np.unique(np.r_[x,0.,np.geomspace(.001,upper,1000)])
            for term,spec in f['sets'].items(): ax.plot(x,membership(x,spec),label=term)
            ax.set_title(f['column'].strip()); ax.set_ylim(-.03,1.08)
            ax.set_xlabel(('log1p('+f['unit']+')') if f['transform']=='log1p' else f['unit'])
            if key=='size':
                ax.set_xscale('symlog',linthresh=1.)
                ax.set_xlabel('bytes (symlog display only)')
            ax.set_ylabel('Membership'); ax.legend(fontsize=8)
        for level in LEVELS: axes.flat[-1].plot(e.grid,membership(e.grid,e.config['output']['sets'][level]),label=level)
        axes.flat[-1].set_title('Output risk'); axes.flat[-1].set_xlabel('Risk score'); axes.flat[-1].legend(fontsize=8)
        fig.suptitle(f'{scenario.title()} model: training-only memberships (ratio view 0–4; shoulder continues)')
        fig.tight_layout(); fig.savefig(FIG/f'{scenario}_memberships.png',dpi=150); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    curves,curves_axes=plt.subplots(1,2,figsize=(11,4))
    cm_fig,cm_axes=plt.subplots(1,2,figsize=(10,4))
    for ax,cm_ax,(scenario,e) in zip(axes,cm_axes,models.items()):
        p=pd.read_parquet(GENERATED/f'{scenario}_test_predictions.parquet')
        for name,mask in [('Benign',p[LABEL]=='BENIGN'),('Attack',p[LABEL]!='BENIGN')]:
            ax.hist(p.loc[mask,'risk_score'],bins=np.arange(0,102,2),alpha=.5,density=True,label=name)
        ax.axvline(e.config['alert_threshold'],color='black',linestyle='--',label='Alert threshold')
        ax.set_title(f'{scenario.title()} test'); ax.set_xlabel('Risk score'); ax.set_ylabel('Density'); ax.legend(fontsize=8)
        m=metrics[scenario]['row_weighted']; cm=m['confusion_matrix']
        matrix=np.array([[cm['tn'],cm['fp']],[cm['fn'],cm['tp']]])
        cm_ax.imshow(np.log1p(matrix),cmap='Blues')
        for i in range(2):
            for j in range(2): cm_ax.text(j,i,f'{int(matrix[i,j]):,}',ha='center',va='center',bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
        cm_ax.set_xticks([0,1],['No alert','Alert']); cm_ax.set_yticks([0,1],['Benign','Attack'])
        cm_ax.set_xlabel('Prediction'); cm_ax.set_ylabel('Actual'); cm_ax.set_title(scenario.title()+' test (log color)')
        order=np.argsort(-p.risk_score.to_numpy(),kind='stable')
        y=(p[LABEL]!='BENIGN').to_numpy()[order]; s=p.risk_score.to_numpy()[order]
        ends=np.r_[np.flatnonzero(s[1:]!=s[:-1]),len(s)-1]
        tp=np.cumsum(y)[ends]; fp=np.cumsum(~y)[ends]
        recall=tp/y.sum(); precision=tp/(tp+fp); fpr=fp/(~y).sum()
        curves_axes[0].plot(np.r_[0,fpr],np.r_[0,recall],label=f"{scenario}: AUC={m['roc_auc']:.3f}")
        curves_axes[1].step(np.r_[0,recall],np.r_[1,precision],where='pre',label=f"{scenario}: AP={m['pr_auc_average_precision']:.3f}")
        curves_axes[1].axhline(y.mean(),linestyle=':',alpha=.5,label=f'{scenario} attack prevalence {y.mean():.3f}')
    curves_axes[0].plot([0,1],[0,1],'k--',alpha=.4)
    curves_axes[0].set(xlabel='False positive rate',ylabel='Recall',title='ROC (row-weighted)')
    curves_axes[1].set(xlabel='Recall',ylabel='Precision',title='Precision–recall (different test prevalences)')
    for ax in curves_axes: ax.legend(fontsize=8)
    for figure,name in [(fig,'test_score_distributions'),(curves,'roc_pr'),(cm_fig,'confusion_matrices')]:
        figure.tight_layout(); figure.savefig(FIG/(name+'.png'),dpi=150); plt.close(figure)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for ax,scenario in zip(axes,['grouped','day']):
        rules=pd.read_csv(REPORT/f'{scenario}_test_rules.csv')
        ax.bar(rules.rule_id,rules.active_meaningful/rules.rows*100)
        ax.tick_params(axis='x',rotation=90); ax.set_title(scenario.title()+' meaningful rule coverage')
        ax.set_ylabel('Test rows activating rule (%)')
    fig.tight_layout(); fig.savefig(FIG/'rule_coverage.png',dpi=150); plt.close(fig)

def render():
    metrics=json.loads((REPORT/'metrics.json').read_text(encoding='utf-8'))
    for result in metrics.values():
        result['performance']['timed_scope']='input coercion, memberships, rules, aggregation, centroid and output arrays; excludes coverage diagnostics, disk IO and metric sorting'
    write_json(REPORT/'metrics.json',metrics)
    fit=json.loads((REPORT/'fit_records.json').read_text(encoding='utf-8'))
    numeric=json.loads((REPORT/'numerical_validation.json').read_text(encoding='utf-8'))
    models={s:MamdaniRiskEngine.load(CONFIG/f'{s}_v1.json') for s in ['grouped','day']}
    # Refresh display-only explanation fields without changing any evaluated score,
    # membership/rule parameter, threshold, or frozen configuration identifier.
    examples=json.loads((REPORT/'error_examples.json').read_text(encoding='utf-8'))
    for x in examples:
        current=models[x['scenario']].predict_one(x['inputs'])
        assert current['risk_score']==x['prediction']['risk_score'] and current['model_id']==x['prediction']['model_id']
        x['prediction']=current
        strongest=current['activated_rules'][:3]
        x['possible_error_reason']=' '.join(r['rationale_en'] for r in strongest)+ ' These hypotheses overlap benign/attack behavior; their aggregated score falls on the wrong side of the frozen alert threshold. This is a possible explanation, not a verified attack mechanism.'
    write_json(REPORT/'error_examples.json',examples)
    write_json(REPORT/'example_prediction.json',examples[0])
    overlaps=overlap_diagnostics()
    make_figures(models,metrics)
    anchors=[]
    for scenario,e in models.items():
        for key,f in e.config['features'].items():
            anchors.append({'scenario':scenario,'column':json.dumps(f['column']),'unit':f['unit'],
                            'transform':f['transform'],'training_min':f['training_min'],'training_max':f['training_max'],
                            'low_anchor':f['raw_anchors'][0],'middle_anchor':f['raw_anchors'][1],'high_anchor':f['raw_anchors'][2],
                            'zero_fraction':f['zero_fraction'],'basis':f['anchor_basis']})
    anchors=pd.DataFrame(anchors); anchors.to_csv(REPORT/'membership_anchors.csv',index=False)
    (REPORT/'fuzzy_system_design.md').write_text(f'''# Implemented fuzzy system (v1)

## Architecture and scope

The implementation is a genuine five-input, one-output Mamdani system. It trains
no conventional classifier or neural network. Fuzzification uses three overlapping
sets per input; AND uses minimum, OR maximum, implication minimum clipping,
aggregation maximum and defuzzification a numerical centroid. Twenty-two explicit
hand-written rules are shared by both models. Rules are hypotheses about load and
behavior, not attack-type proofs. No web interface or additional dependency was added.

Memberships are derived separately for the grouped-development and coarse-day
protocols. Grouped train has {fit['grouped']['training_rows']:,} deliberately class-stratified
observations; day train has {fit['day']['training_rows']:,} eligible nonquarantined
Monday–Wednesday observations at their original proportions. Training labels are
used for diagnostics only; the fitting function accepts exactly the five numerical
input columns and rejects labels/metadata. Class-stratified sampling indirectly
affects training distributions, so the two scores are model-relative indices.

## Input semantics and fitted anchors

{table(anchors)}

Rate is packets/second, volume packets, mean packet length and response standard
deviation bytes. Physical units follow the source's CICFlowMeter naming convention,
not unit-tagged Arrow metadata. Forward/backward are flow directions, not proof of
client/server identity. The integer Down/Up Ratio equals floor(backward packets /
forward packets) in all {numeric['training_semantics_check']['rows']:,} checked day-train rows.
Thus ratio zero means backward count is LESS than forward count; it does not imply
no responses. A ratio of one also covers some backward-heavy flows due to quantization.
The compact terms forward/balanced/backward are approximate directional descriptions.
In rule rationale R19, 'forward-only' is a hypothesis shorthand, never an inference
that the export proves absence of response packets. Response standard deviation
zero can mean uniform packets or too few/no responses, not maliciousness.

Rate, volume and variation use log1p to compress skew; packet size and ratio use
identity. Except ratio, anchors use training p25/p60/p90; variation uses positive
training values because zero is a large discrete mass. Repeated anchors are expanded
deterministically by max(1 physical unit, 1% of the first anchor). This prevents
degenerate triangles; it is a numerical fallback, not label-based optimization.
Ratio anchors 0/1/2 express forward domination, approximate balance and backward
domination based on domain semantics. Exact quantiles and all triangle/trapezoid
vertices are serialized in config/fuzzy/*_v1.json. Full TASK 01 or test quantiles
were not used to fit memberships.

Each low set is trap(0,0,a,b), middle tri(a,b,c), high trap(b,c,U,U), with U at least
the transformed training maximum and c. This is a complete, overlapping partition
of the saturated nonnegative domain. Extreme finite values saturate at U; valid
values outside observed training min/max are separately flagged. There is no
outlier deletion, normalization fit, or invalid-to-zero imputation. Internally a
safe placeholder is used only for arithmetic; invalid rows have zero activations
and no returned score.

## Output, centroid and categories

Fixed output sets: Low trap(0,0,15,35); Medium tri(20,45,65); High tri(50,70,85);
Critical trap(75,90,100,100). These are transparent design choices for a behavior
index, not estimated severity labels. The centroid integrates the maximum clipped
membership on 201 equally spaced points from 0 to 100, using trapezoidal quadrature.
Rules with a common consequent reduce by maximum before constructing four clipped
output sets; this is algebraically identical to aggregating every rule's output.
The score is bounded in [0,100]; centroid geometry need not attain exactly 0 or 100.
With no aggregate area the engine abstains. No-rule abstention is tested even
though the baseline rate/volume rules cover the approved valid domain.

Categories use lower-inclusive cut points: Low [0,25), Medium [25,50),
High [50,75), Critical [75,100]. They are intentionally fixed rather than tuned to
traffic labels. The separate binary alert threshold is {models['grouped'].config['alert_threshold']}
for grouped and {models['day'].config['alert_threshold']} for day; a Medium category can therefore
raise an alert in the grouped model. Scores are neither attack probabilities nor
calibrated risk severity. Rule consequents need not equal the final category when
several output sets aggregate.

## Freeze/calibration protocol

Rules were written before evaluation and never optimized from test labels.
Training-only memberships were fitted first. Validation considered exactly six
alert thresholds (25,35,45,55,65,75), maximizing balanced accuracy, with the highest
threshold winning ties. No membership boundary, output set, rule weight or rule
consequent was tuned on validation or test. Configurations were persisted and their
SHA256 identifiers frozen before test inference; scripts assert unchanged digests.
Calibration tables record every choice. The day validation best balanced accuracy
is below chance: its selected threshold is a failed calibration outcome, not a
recommended operational setting. No test-driven repair was made.

## APIs and invalid-input policy

`MamdaniRiskEngine.load(path).predict_one(mapping)` returns status, score, category,
alert, membership degrees, every positive-strength rule, consequents, rationale,
translation keys and explanation text. `predict_batch(DataFrame)` provides arrays
of scores/statuses/categories, memberships, rule strengths and range flags.
Only the five exact column names are accepted; extra labels/metadata raise ValueError.
Missing columns, null, NaN, either infinity, negative values, numeric strings,
booleans and malformed values produce invalid_input and no score. Unrepresentable
integers are also unavailable. Valid zeros are processed normally. No rule produces
status no_rule_activation with no score. Batch unavailable scores use NaN internally;
single-record JSON converts them to null. The CLI is scripts/score_flow.py.
Structured message/risk/rule/feature/term keys permit a later Turkish display layer;
English prose is separate from the inference evidence. Explanations describe
activations, not a causal decomposition of the centroid or proof of an attack.

## Numerical and performance validation

On 256 training records per model, single/batch scores were bitwise identical,
including reload and different batch sizes. Against a 2,001-point output grid,
maximum absolute score differences were {numeric['grouped']['quadrature_max_absolute_error_vs_2001_grid']:.6f}
(grouped) and {numeric['day']['quadrature_max_absolute_error_vs_2001_grid']:.6f} (day).
This bounded numerical check is not a proof over every possible input.
See numerical_validation.json for exact results and single-record timing.
''',encoding='utf-8')
    rule_rows=[]
    for r in models['grouped'].config['rules']:
        conditions=' AND '.join(f"{e['feature']} is {e['term']}" for e in r['antecedent']['all'])
        rule_rows.append({'ID':r['id'],'antecedent':conditions,'consequent':r['consequent'],'rationale':r['rationale']})
    rules=pd.DataFrame(rule_rows); rules.to_csv(REPORT/'rule_inventory.csv',index=False)
    coverage_rows=[]
    for s,m in metrics.items(): coverage_rows.append(dict(scenario=s,**m['coverage']))
    (REPORT/'rule_base_analysis.md').write_text(f'''# Rule base and empirical coverage

## Fixed interpretable rules

{table(rules)}

The first nine manually authored rate/volume rules guarantee a conservative base
response for all valid combinations of those two variables. They are not an
automatic enumeration of 243 five-variable combinations. Every rule uses at least
two behavioral antecedents. Rules 10–22 add multivariate concerns and benign
counter-hypotheses. All weights are 1. Zero evidence in a single unusual measurement
never determines the output alone. OR support is implemented/tested, although the
current fixed rule base uses AND to keep its interpretation compact.

## Actual test coverage

{table(pd.DataFrame(coverage_rows))}

Meaningful activation means strength >=0.1; any activation means >0. The baseline
coverage is 100%, not evidence of detection quality. Low-versus-High/Critical
conflict means at least one rule from each side reaches 0.1. Conflicts affect
{pct(metrics['grouped']['coverage']['conflicting_low_high_fraction'])} of grouped and
{pct(metrics['day']['coverage']['conflicting_low_high_fraction'])} of day test records.
Both activation sets are preserved; maximum aggregation resolves them without
deleting contradictory evidence. These conflicts help explain compressed scores.
Dominant counts choose the first rule on tied strengths only for diagnostics;
ties do not alter inference. Max aggregation means duplicated or overlapping rules
with the same consequent do not cumulatively add evidence.

## Training plausibility checks and failures

Training rule tables use all 8,217 grouped training records and a deterministic,
class-preserving day-training diagnostic capped at 1,000 per class (7,011 records).
Membership fitting still uses every eligible day-training row. These diagnostic
label proportions are not prevalence estimates. The tables explicitly separate
benign and attack activations. Low baseline patterns activate on many attacks,
while high/critical patterns also activate on benign traffic. Load-related security
hypotheses therefore do not establish attack discrimination in these features.

On grouped test, R07 (intensive rate/few packets -> Medium) and R02 (sparse rate/
moderate volume -> Low) are frequent dominant rules. R22 activates meaningfully
on only one grouped test record. On day test, R07 dominates 255,105 records;
R11 (intensive/small/uniform -> High) activates meaningfully on 96,324 benign
records and 158,177 attack records. R10's Critical pattern activates meaningfully
on 34,541 benign versus 1,165 attack records. These are co-activation counts, NOT
isolated causal false-alarm contributions; other rules aggregate simultaneously.
R21/R22 are relatively rare. Inspect *_training_rules.csv and *_test_rules.csv for
every activation count, mean strength and dominant frequency. No rule was removed
or changed after the test results were observed.
''',encoding='utf-8')
    comparison=[]
    for scenario,m in metrics.items():
        for weighting,key in [('rows','row_weighted'),('observation groups','observation_group_weighted')]:
            x=m[key]
            comparison.append({'scenario':scenario,'weighting':weighting,'test_rows':x['rows'],'threshold':x['threshold'],
                               **{k:round(x[k],6) for k in ['precision','recall','f1','false_positive_rate','false_negative_rate','balanced_accuracy','roc_auc','pr_auc_average_precision']}})
    comparison=pd.DataFrame(comparison); comparison.to_csv(REPORT/'metric_comparison.csv',index=False)
    perclass='\n\n'.join(f"### {s.title()} test\n\n"+table(pd.read_csv(REPORT/f'{s}_per_class.csv').fillna('not applicable')) for s in metrics)
    confusions='\n\n'.join(f"{s.title()}: TN={int(m['row_weighted']['confusion_matrix']['tn']):,}, FP={int(m['row_weighted']['confusion_matrix']['fp']):,}, FN={int(m['row_weighted']['confusion_matrix']['fn']):,}, TP={int(m['row_weighted']['confusion_matrix']['tp']):,}." for s,m in metrics.items())
    (REPORT/'model_evaluation.md').write_text(f'''# Frozen-model evaluation

## Main finding

The fuzzy engine is implemented and numerically validated, but these hand-written
load/behavior rules are NOT a reliable operational attack detector. Grouped test
balanced accuracy is 0.56375 with a 76% false-positive rate. Day-based validation
selected threshold 75 and day test then misses almost all attacks. Results are
reported without test-driven threshold or rule repair. High grouped precision/F1
largely reflect attack-heavy stratification and must not be presented as strong
real-world detection performance.

## Protocols and actual dimensions

Scenario A uses the unchanged development sample: train 8,217, validation 1,753,
test 1,750. Its test contains only 150 benign versus 1,600 attack observations:
attack prevalence is 91.429%. Memberships are fitted on its training partition;
binary threshold 25 is selected on validation only. It is a development comparison,
not an estimate of source or operational prevalence.

Scenario B fits memberships on all 1,607,145 eligible Monday–Wednesday training
records, selects threshold 75 using all 422,299 eligible Thursday validation records,
and tests all 666,572 eligible Friday records. The original temporal manifest
quarantines 132,348 source rows (131,745 fuzzy-eligible), because their full-feature
observation groups span nominal day partitions. No quarantined record enters fit,
calibration or test. Validation has web attacks and infiltration unseen in training;
Friday test has Bot, DDoS and PortScan, all absent from day training. Categories
differ by capture day; this measures substantial scenario/category shift. Day test
attack prevalence is about 43.16%. Inputs unavailable under TASK 01 are excluded
by the existing fuzzy-ready policy, so these metrics concern eligible flows only.
No abstentions occurred among evaluated eligible rows; abstention is tested separately.

## Metrics

BENIGN is negative; every other original traffic label is positive. Alerts use
score >= threshold. No label is an inference input. Confusion matrices use actual
rows, not normalized percentages. Zero-denominator rates are null; no-alert precision
is conventionally zero. ROC-AUC treats tied scores together. PR-AUC is average
precision (step-integrated precision over recall), with trapezoidal PR area also
provided separately in metrics.json. The two PR definitions need not agree for
discrete scores. Positive prevalence is the random-ranking AP baseline.

{table(comparison)}

{confusions}

Group-weighted metrics assign each full-observation group total weight one,
distributing its weight among its rows, including conflicting labels. They measure
a different empirical distribution, not independent hosts or sessions. Duplicate
weighting reduces day ROC-AUC from 0.74255 to 0.70052. Both are reported.

## Per-class recall and false negatives

{perclass}

Heartbleed has only two grouped test examples; 2/2 detections do not establish
reliable performance. Day training contains all 11 Heartbleed examples and Friday
contains none, so day Heartbleed recall is unavailable. SQL injection is missed
on all three grouped examples. No attack type is inferred by the engine itself.

## Leakage and independence limitations

Full-original-feature observation groups do not cross the saved grouped/day
partitions; TASK 01 explicitly verified this. This does not imply independence of
the selected five-variable projections. projected_input_overlap.json additionally
measures exact five-input patterns spanning partitions:

{table(pd.DataFrame([dict(scenario=s,**{k:v for k,v in o.items() if k!='definition'}) for s,o in overlaps.items()]))}

Some distinct original flows collapse to identical selected inputs. This is an
additional evaluation limitation, not evidence that a fitted classifier memorized
labels; the engine uses fixed rules and quantile-based sets. Near-duplicate flows,
shared hosts and within-day sessions remain unresolved. Day quarantine does not
restore fine-grained temporal metadata. Full-dataset EDA was already viewed in
TASK 01, so neither test is a perfectly blind external holdout.

## Interpretation and next decisions

Score distributions overlap substantially; high/low conflicts concentrate many
scores around Medium/High boundaries. Thursday validation does not generalize to
Friday novel categories. The six-choice calibration objective performs below
chance in day validation, making the deployment threshold unsuitable. AUC and AP
describe ranking, not the safety or usefulness of the frozen alert operating point.
No attack severity ground truth exists; this evaluates alert agreement with traffic
categories, not calibration of Low/Medium/High/Critical risk. For future scientific
improvements, revise rules/memberships only on train and validation, version them,
and use a newly reserved evaluation set rather than repeatedly optimizing this test.
''',encoding='utf-8')
    examples=json.loads((REPORT/'error_examples.json').read_text(encoding='utf-8'))
    error_sections=[]
    for x in examples:
        p=x['prediction']; top=p['activated_rules'][:3]
        terms={c:max(m,key=m.get) for c,m in p['membership_degrees'].items()}
        interpretation='; '.join(r['rationale_en'] for r in top)
        error_sections.append(f"### {x['scenario']} {x['error_type']} — source row {x['source_row_id']}\n\n"
                              f"Actual label: {x['actual_label']}. Score {p['risk_score']:.6f}, {p['risk_level']}; alert={p['alert']}.\n\n"
                              f"Inputs: `{json.dumps(x['inputs'])}`.\n\nDominant input terms: `{json.dumps(terms)}`.\n\n"
                              f"Strongest rules: "+', '.join(f"{r['id']} -> {r['consequent']} ({r['strength']:.4f})" for r in top)+
                              f".\n\nPossible error mechanism: {interpretation} Those behavior hypotheses overlap the actual traffic label; the aggregated centroid crosses the selected alert threshold in the wrong direction. This is an explanatory hypothesis, not a verified attack mechanism.\n")
    (REPORT/'error_analysis.md').write_text(f'''# Error analysis

## Observed failure patterns

The grouped model raises 114 false alarms among 150 benign flows. R03's Medium
output alone has centroid 43.333, above its calibrated threshold 25, so legitimate
long low-rate exchanges become alerts. Benign median score 38.466 and attack median
37.172 demonstrate strong overlap. A high aggregate F1 does not cure that overlap.
Low-rate and low-volume attacks activate conservative Low rules; small application
attacks may be behaviorally indistinguishable from benign transactions. Grouped
SQL injection recall is 0/3, Bot and Slowhttptest miss 40/150 each, and slowloris
misses 33/150. These cases show the limits of load-oriented aggregate inputs.

Day threshold 75 is selected because none of the tested thresholds performs well
on Thursday validation. Friday attack scores concentrate mostly below it (attack
median 50.573), producing 287,709 false negatives. PortScan has 157,751/157,751
misses, Bot 1,956/1,956, and DDoS 128,002/128,020. Simultaneous Low and High rules
can suppress a concern rule's centroid. Only 18 attacks exceed the day threshold.
This threshold collapse must remain visible in a future demonstration UI.

## Extreme values, duplicates and label ambiguity

Valid extreme measurements saturate shoulder memberships, rather than producing
invalid scores or being removed. No grouped test input is outside its observed
training range; two day test rows are. Out-of-range flags and error examples remain
available. Bounded training-only numerical stress tests also cover huge values.
The grouped test repeats 126 full-observation rows beyond first occurrences; day
test repeats 71,336. Group-weighted metrics quantify sensitivity to duplication.
One conflicting-label group with two day test rows has the same behavioral
evidence but two labels; no deterministic feature-only engine can satisfy both.
Excluding it barely changes the metrics (see metrics.json), so label conflicts do
not explain the model's main failures. The development subset happens to contain
no conflicting full-observation group in its test; the 698 source conflicts still
exist and were not relabeled. Exact equality of five-feature projections adds a
separate ambiguity/overlap risk quantified in projected_input_overlap.json.

## Deterministic representative examples

Five false positives and five false negatives per scenario are chosen by stable
row-ID hash priority with seed {SEED}. They are diagnostic examples, not a random
estimate of error prevalence. Full inputs, all memberships, every activated rule,
strengths, consequents, model hashes and explanation keys are in error_examples.json.
No rules were automatically changed from these examples.

'''+ '\n'.join(error_sections),encoding='utf-8')
    print('Generated four English reports and six focused figures.',flush=True)

if __name__=='__main__': render()
