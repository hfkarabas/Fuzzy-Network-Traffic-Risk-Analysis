# TASK04 scientific evaluation and integration report

**No defensible scoring improvement was demonstrated. Retain the existing fuzzy model and operating policies.**

## Audit and dataset foundation

TASK01 verified 2,830,743 records / 79 columns / 15 labels, 2,827,761 fuzzy-ready flows. TASK02 built grouped_v1 and day_v1 Mamdani models. TASK02B actually implemented frozen/refit, benign-reference membership, and 18-rule candidates; none passed its gate. TASK03 loaded selected_v2 (a verbatim copy of grouped_v1) with separate TASK02B policies. The dashboard displayed historical TASK02 tests separately from TASK02B internal validation. The historical model has 22 rules and five exact leading-space input names. Its score is a behavioral index, never an attack probability or class-derived severity.

## Integrity and lineage

Eligible population is 297,916 Monday–Thursday flows after excluding 2,529,845 exposed or leakage-linked flows from 2,827,761 quality-eligible flows. 703,945 were directly exposed; 1,825,900 more linked rows were excluded. TASK04 reads the saved eligible 60,000-row sample only, checks source IDs, original groups and coarse signatures against metadata-only exposure manifest, excludes all Friday, and does not read exposed labels/scores/errors. 14,042 design rows inform descriptive diagnostics; 45,958 comparison rows rotate through three disjoint train/calibration/assessment signature buckets. Each fold contains exactly one bucket per role. Exact selected-input duplicates cannot cross these roles. Capture days are recorded, but observations from a day can occur in multiple roles.

These development folds were already assessed in TASK02B and are adaptively reused here. Historical frozen membership fitting overlaps some eligible development data. A_frozen is contextual/warm; A_refit is the fair training-only comparator. No untouched independent test exists. No new shuffled subset is called a test. Conditional bootstrap intervals and fold SD omit adaptive selection, host/session dependence and population-exclusion bias.

Residual near-duplicate audit found 3169 cross-role neighboring-bin representative pairs involving 5384 signatures. This is a bounded one-axis adjacency check, not exhaustive matching. It demonstrates why signature disjointness does not prove independence. Design contains 1 identical five-input vectors with multiple labels (not necessarily identical full flows). Earlier full-data audit found 698 conflicting-label numerical observation groups and 308,381 duplicate rows beyond first. No source labels were repaired or deleted.

## Predeclared hypotheses and selection

config/fuzzy/task04/protocol.json freezes source/data hashes, candidates and selection before TASK04 results. A_frozen retains original scoring; A_refit refits original p25/p60/p90 anchors on training rows. B uses equal-signature training medians to reduce repeated-flow influence. C uses training-row memberships and exactly four rule changes: R07/R19 become Low; R10/R11 additionally require volume many. D combines B and C. All retain five features, 22 explicit rules and stable rule IDs. There is no Cartesian rule generation, classifier or black-box fitting. No post-result candidate search was performed.

Primary gate: mean Balanced group-weighted balanced accuracy; mean FPR <=7.5%; >=2 percentage-point improvement over BOTH refit and frozen baselines with positive paired signature-bootstrap lower95 against both. Otherwise retain original scoring and policies. This stricter gate prevents promoting a clean refit that is worse than the already active educational model.

## Feature and membership evidence

training_feature_audit.csv profiles all five inputs and ten extra candidates separately on each training fold, with missing/invalid rates, zeros, quantiles, rank redundancy and day-specific univariate AUC. Duration/IAT/header measurements strongly overlap existing volume/rate, bytes/s couples packet size and rate, flags are zero-heavy and day-unstable, and minimum segment size has collection-artifact concerns. No extra feature passed the pre-registration design justification; feature-enhanced E was not implemented. This does not prove five inputs sufficient. Timing/application context may ultimately be necessary, but requires a separately justified study. No API schema expansion is warranted here.

Rate and volume overlap is a rate-duration identity issue: high rate from a tiny denominator does not imply sustained load. Packet-length variation has a large zero mass; zero can mean a one-response flow, not malicious repetition. Forward/backward ratio is exported as an integer and loses fractional asymmetry. Class distributions and attack scenarios shift by capture day. All current inputs have overlapping benign/attack patterns.

Training-only triangular/trapezoidal sets use log1p for rate, count and response variation, identity for packet mean and exported ratio; shoulders saturate finite extremes. Direction anchors remain 0/1/2 by domain convention. B changes the reference population, not the transparent quantile rule. Final membership curves and all raw/transformed parameters are frozen in selected_v4.json and membership_diagnostics.csv/figures. Too much saturation and overlap remain; no hard set assignments were introduced.

## Root-cause diagnostics

rule_diagnostics.csv records all 22 rules: frequency >=0.1, average strength, benign/attack activation and association with FP/FN at the deployed Balanced threshold. rule_redundancy.csv retains activation rank correlations. R07/R10/R11/R19 co-activate often on benign design traffic; R02/R03 also cover many attacks, including slow flows. Removing broad rules can suppress benign alerts but also removes attack signal: the candidates demonstrate this tradeoff rather than solve it. Activation association is not causal contribution under max aggregation.

Low and High/Critical rules simultaneously activate >=0.1 on 25.33% of design flows. Min clipping, max aggregation and centroid combine their output areas, not a count or sum of rules; duplicate high rules do not add evidence. Centroids concentrate in moderate bands when several outputs conflict. All score/category cuts remain [25,50,75], distinct from binary alert thresholds. Large unusual transfers can be legitimate; low-rate attacks can resemble ordinary exchanges.

## Candidate comparison — internal validation only

Metrics below are means of three signature-group-weighted fold rates. CM is separately pooled raw flow TN/FP/FN/TP; it must not be used to reconstruct group-weighted rates. Every candidate has 39,159 benign and 6,799 attack assessment rows. All 45 policy/fold rows, per-fold supports, exact thresholds, uncertainty and raw metrics are saved in machine-readable files.

| Candidate | Precision | Recall | F1 | FPR | FNR | BA ± fold SD | ROC-AUC | AP | Raw CM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A_frozen | 0.1746 | 0.2108 | 0.1910 | 0.0491 | 0.7892 | 0.5808 ± 0.0165 | 0.6383 | 0.1184 | 33008/6151/5418/1381 |
| A_refit | 0.0954 | 0.1004 | 0.0978 | 0.0476 | 0.8996 | 0.5264 ± 0.0197 | 0.6056 | 0.0695 | 34451/4708/6105/694 |
| B_group_membership | 0.0675 | 0.0468 | 0.0552 | 0.0320 | 0.9532 | 0.5074 ± 0.0075 | 0.5389 | 0.0557 | 37967/1192/6556/243 |
| C_context_rules | 0.0037 | 0.0025 | 0.0028 | 0.0287 | 0.9975 | 0.4869 ± 0.0093 | 0.5570 | 0.0506 | 38234/925/6796/3 |
| D_combined | 0.0000 | 0.0000 | 0.0000 | 0.0274 | 1.0000 | 0.4863 ± 0.0127 | 0.4279 | 0.0382 | 38227/932/6799/0 |

A higher ranking AUC does not establish useful detection at a low-FPR threshold. The refined candidates failed the predeclared operating-point gate; all unfavorable results remain saved. uncertainty.json reports 500 paired signature-group bootstrap intervals against both baselines. Assessment labels select candidates, so this table is selection evidence, not independent performance.

## Policies and selected artifact

Selected: A_frozen. config/fuzzy/task04/selected_v4.json is a versioned exact copy of the retained model; selected_policies.json preserves existing bytes. selected_manifest.json records model ID and hashes. No new deployed threshold was fitted after results. Fold-specific policy calibration is separate from this deployed artifact.

Sensitive/Balanced/Conservative optimize calibration group recall at respective 10%/5%/1% estimated group FPR caps. Targets are not guarantees or raw flow FPR. Frozen deployed thresholds are 49.632522849397134 / 51.809236850031304 / 59.465890915130174. A policy changes only alert decisions, not score, memberships, category or rule activation.

| Policy | Group recall | Group FPR | Raw recall | Raw FPR |
|---|---:|---:|---:|---:|
| Sensitive | 0.2720 | 0.0992 | 0.2443 | 0.2131 |
| Balanced | 0.2108 | 0.0491 | 0.2031 | 0.1571 |
| Conservative | 0.0604 | 0.0098 | 0.0602 | 0.0110 |

## Post-selection day-shift stress

Each Tuesday/Wednesday/Thursday is excluded from refit training/calibration; all its coarse signatures are also removed from other days. Remaining signatures split deterministically for train/calibration. The frozen model remains warm historically and is explicitly not a day-clean fit. These results did not influence candidate selection or thresholds. Monday has no attacks and is omitted from two-class stress metrics.

| Day | Candidate | Rows | Recall | FPR | Unseen classes |
|---|---|---:|---:|---:|---|
| Tuesday | A_refit | 9090 | 0.4336 | 0.0574 | FTP-Patator, SSH-Patator |
| Tuesday | A_frozen | 9090 | 0.4336 | 0.0892 | FTP-Patator, SSH-Patator |
| Wednesday | A_refit | 14085 | 0.0659 | 0.0223 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Wednesday | A_frozen | 14085 | 0.1981 | 0.0273 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Thursday | A_refit | 10243 | 0.0000 | 0.0650 | Infiltration, Web Attack � Brute Force |
| Thursday | A_frozen | 10243 | 0.0000 | 0.0593 | Infiltration, Web Attack � Brute Force |

per_class.csv provides internal support, alert counts and missed attacks; rare supports cannot establish class reliability. error_examples.json contains three deterministic FP and FN examples with exact inputs, source IDs, labels, fold threshold and full rule evidence. They were generated after selection and not used to tune it. explanation_examples.json identifies naturally observed Low/Medium/High/Critical design examples; no category example is invented.

## Robustness, performance and integration

Measured 112,077 rows/s on 14,042 design flows in 0.125289s, CPU only excluding disk IO. Centroid batch workspace is 3,293,184 bytes before other NumPy temporaries. Batch size remains 2,048. +0.1% feature perturbations have maximum observed score change 0.138878; 15 near-anchor checks at two ppm yield maximum 0.00005177. These are measured workloads, not universal bounds or production SLAs.

Missing/NaN/infinite/negative inputs abstain; no silent zero imputation. Extreme finite values saturate shoulders with out-of-range notices; valid zeros infer normally. Single/batch, reload, rule evidence and all-policy score invariance were checked. A separate metric-reproduction pass verified all 45 saved policy rows.

The FastAPI service loads the TASK04 manifest/configuration while preserving the same scoring/policy IDs. API schema and five inputs remain backward compatible. Historical example source rows and predictions remain valid. The existing React layout/pages/navigation/CSS are retained; the evaluation page adds a compact scientific comparison and explicit model/protocol identification. Historical TASK02 tests and TASK02B evidence remain separately labeled. Newly reused validation metrics are never presented as new independent tests.

## Reproduction and limitations

Run .venv/Scripts/python.exe scripts/task04_experiment.py compare after checking the registered source hashes; it regenerates candidate configs and comparison from unchanged eligible cache. Run scripts/task04_diagnostics.py for diagnostics/figures/stress/robustness. Freeze is one-time and refuses overwrite. Transient OOF/curves are under ignored .tmp/task04; figures under ignored reports/figures/task04. No dataset download, classifier training, GPU or remote Git operation is needed.

The user-approved educational web application is usable, but detection reliability has not improved. The project is ready for presentation review, not operational deployment. Present the negative experiment honestly, distinguish scores/categories/alerts, show a real false negative, and retain the scenario-shift and group-vs-flow caveats. Further scientific progress needs new training hypotheses and genuinely independent captures, not more adaptive tuning on this benchmark. See validation.json for executed test/build/integration evidence and preservation.json for historical hashes.

## Executed release checks

129 Python tests and 15 frontend tests passed; zero failures. TypeScript and production build passed. All 27 live API/direct-engine comparisons, 45 saved policy metric rows and 15 training-only model reproductions passed. Historical integrity verified 176 unchanged artifacts plus 129 prior tracked configs/reports/CSS/catalog files. Browser inspection confirmed the TASK04 findings, preserved inference page and no mobile horizontal overflow. Initial Windows sandbox ACL errors were resolved by an authorized test execution environment; no tests were weakened.
