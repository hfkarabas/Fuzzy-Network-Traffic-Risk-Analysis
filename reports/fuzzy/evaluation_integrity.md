# Evaluation integrity and partition lineage

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
the supplied aggregate 114/150 FPR is 0.6857–0.8213, before accounting
for dependence or sampling bias. It is too small and unrepresentative for a precise
operational low-FPR claim. Original temporal classes vary sharply by capture day.

## Exact eligible population and exclusions

Begin with 2,827,761 quality-eligible original fuzzy-ready flows. The 2,982 unavailable
input rows are outside this quality-eligible universe. Conservatively mark every
Friday record, including previously quarantined Friday flows, plus every original
TASK02 grouped-test row. Direct exposure marks 703,945
eligible records. Exclude all original observation groups and coarse five-input
signatures linked to those marks: 2,529,845 rows excluded in total,
including 1,825,900 additional linked rows.
Remaining eligible population: **297,916** flows across Monday–Thursday.

| capture_day | rows |
| --- | --- |
| Monday | 75780 |
| Thursday | 74897 |
| Tuesday | 56675 |
| Wednesday | 90564 |

Original source IDs, observation-group IDs, source filenames, capture days and old
partition lineage remain available in ignored Parquet manifests. There are
616,530 directly exposed original groups and
47,609 blocked coarse signatures. Coarse signatures round
log1p of rate, volume, mean size and response std to a 0.10 grid, keeping the integer
direction ratio exact. Exact selected-feature repeats necessarily share a signature;
near clones within a bin also share it. All original groups were checked to map to
one signature. This is not exhaustive near-duplicate detection: close points across
bin boundaries and host/session dependencies can remain.

Excluding roughly 90% of the quality-eligible source creates a major selection
shift. The retained population has 252,213
benign and 45,703 attack flows.
Nearly all web-attack observations disappear through conservative linkage; tiny
remaining category supports cannot justify generalization claims. See
eligible_population_classes.csv for exact remaining category/day counts.

## New internal roles

Sample 60,000 rows uniformly by deterministic source-row hash,
without label stratification, AFTER exclusions. The sample has
31,142 signatures. Reserve 14,042 design
rows in separate signature groups; only that panel informs rule/feature diagnostics.
The other 45,958 rows rotate
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
