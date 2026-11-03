# TASK05 candidate evaluation

**Reused internal development validation only. No untouched independent holdout exists.**

The unchanged eligible population is 297,916 flows after excluding 2,529,845 exposed or linked quality-eligible rows, including all Friday and old grouped-test source/group/coarse-signature links. The saved 60,000-row sample preserves IDs, source files and capture days. Design: 14,042 rows. Assessment panel: 45,958 rows (39,159 benign, 6,799 attacks) across three original signature buckets. For fold k, training is (k+2)%3 and policy calibration (k+1)%3. Each comparison record is assessed once. No original group, coarse signature or exact expanded eight-input vector crosses roles. Metadata-only exposed IDs/groups/signatures are checked before fitting.

TASK02B/TASK04 already assessed this development panel. Expanded feature profiling is new measurement on previously used records; the new architecture outcomes are adaptively reused internal validation. The day-stress hash split is new, but its observations were already development evidence. It is not an untouched temporal test. A_frozen is warm because its historical membership fitting overlaps eligible data; A_refit is the clean within-fold fit comparator.

The full selection objective was frozen before candidate outcomes in config/fuzzy/task05/protocol.json with source/cache SHA256 hashes. Promotion requires >=5pp mean Balanced group-recall gain over both baselines; positive 500-resample paired signature-bootstrap lower95 against both; mean FPR<=7.5%, every fold<=10%; fold recall no worse than frozen minus2pp; zero abstentions. Additionally each Tuesday/Wednesday/Thursday holdout requires FPR<=10% and recall no worse than its day-clean refit minus2pp. Simpler systems within2pp recall are preferred. No criterion or rule was changed after outcomes.

Sensitive/Balanced/Conservative calibrate thresholds exclusively on calibration rows to maximize signature-weighted recall at estimated FPR caps10%/5%/1%. Ties and no-alert candidate follow the existing policy procedure. These are not guaranteed rates or attack probabilities. All 45 fold/policy rows and exact thresholds are in metrics.json/fold_policies.json. Thresholds vary by architecture, never fixed arbitrarily across incompatible scores.

| Candidate | Rules | Precision | Recall ± fold SD | F1 | FPR | FNR | BA | ROC-AUC | AP | Raw TN/FP/FN/TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A_frozen | 22 | 0.1746 | 0.2108 ± 0.0320 | 0.1910 | 0.0491 | 0.7892 | 0.5808 | 0.6383 | 0.1184 | 33008/6151/5418/1381 |
| A_refit | 22 | 0.0954 | 0.1004 ± 0.0360 | 0.0978 | 0.0476 | 0.8996 | 0.5264 | 0.6056 | 0.0695 | 34451/4708/6105/694 |
| B_flat8 | 15 | 0.0050 | 0.0009 ± 0.0015 | 0.0015 | 0.0044 | 0.9991 | 0.4982 | 0.4631 | 0.0419 | 38934/225/6798/1 |
| C_hierarchy | 34 | 0.2576 | 0.3166 ± 0.0253 | 0.2838 | 0.0453 | 0.6834 | 0.6357 | 0.6553 | 0.3503 | 37881/1278/2845/3954 |
| D_behavior | 25 | 0.3351 | 0.3018 ± 0.0145 | 0.3059 | 0.0357 | 0.6982 | 0.6331 | 0.5507 | 0.3098 | 37540/1619/2830/3969 |

Rates are means of signature-group-weighted fold metrics; confusion counts are separately pooled RAW flows. One signature receives total weight one, including conflicting-label rows proportionally. Raw confusion cannot reconstruct weighted rates. Full row metrics, support, coverage, abstention and throughput are retained in comparison.csv/metrics.json. All candidates have 100% final rule coverage and zero abstention on this common valid cohort.

## Multiple operating points

| Candidate | Policy | Group recall | Group FPR | Raw recall | Raw FPR |
|---|---|---:|---:|---:|---:|
| A_frozen | Sensitive | 0.2720 | 0.0992 | 0.2443 | 0.2131 |
| A_frozen | Balanced | 0.2108 | 0.0491 | 0.2031 | 0.1571 |
| A_frozen | Conservative | 0.0604 | 0.0098 | 0.0602 | 0.0110 |
| A_refit | Sensitive | 0.1550 | 0.0967 | 0.1630 | 0.2012 |
| A_refit | Balanced | 0.1004 | 0.0476 | 0.1021 | 0.1202 |
| A_refit | Conservative | 0.0365 | 0.0083 | 0.0347 | 0.0085 |
| B_flat8 | Sensitive | 0.0021 | 0.0498 | 0.0004 | 0.0393 |
| B_flat8 | Balanced | 0.0009 | 0.0044 | 0.0001 | 0.0057 |
| B_flat8 | Conservative | 0.0009 | 0.0027 | 0.0001 | 0.0043 |
| C_hierarchy | Sensitive | 0.3336 | 0.0904 | 0.5852 | 0.0661 |
| C_hierarchy | Balanced | 0.3166 | 0.0453 | 0.5816 | 0.0326 |
| C_hierarchy | Conservative | 0.3030 | 0.0084 | 0.5771 | 0.0060 |
| D_behavior | Sensitive | 0.3521 | 0.1003 | 0.6021 | 0.0948 |
| D_behavior | Balanced | 0.3018 | 0.0357 | 0.5838 | 0.0413 |
| D_behavior | Conservative | 0.2576 | 0.0095 | 0.5729 | 0.0146 |

C_hierarchy improves mean group recall from21.08% to31.66%, with4.53% FPR compared to4.91%. Conditional paired bootstrap recall-gain95 is approximately[6.79,14.23]pp versus frozen. D_behavior reaches30.18% recall with3.57% FPR and gain interval[5.24,12.67]pp. These indicate a promising internal architectural hypothesis, not independent generalization. Bootstrap resamples signatures, not rows; it is conditional on fitted folds and excludes selection/adaptive reuse and day/host uncertainty.

## Registered capture-day stability gate

| Day | Candidate | Recall | FPR | Unseen labels |
|---|---|---:|---:|---|
| Tuesday | A_frozen | 0.4336 | 0.0953 | FTP-Patator, SSH-Patator |
| Tuesday | A_refit | 0.4336 | 0.0731 | FTP-Patator, SSH-Patator |
| Tuesday | B_flat8 | 0.0000 | 0.0103 | FTP-Patator, SSH-Patator |
| Tuesday | C_hierarchy | 0.0000 | 0.0496 | FTP-Patator, SSH-Patator |
| Tuesday | D_behavior | 0.0000 | 0.0379 | FTP-Patator, SSH-Patator |
| Wednesday | A_frozen | 0.1981 | 0.0273 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Wednesday | A_refit | 0.0350 | 0.0089 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Wednesday | B_flat8 | 0.0009 | 0.0240 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Wednesday | C_hierarchy | 0.0000 | 0.0000 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Wednesday | D_behavior | 0.0000 | 0.0018 | DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, Heartbleed |
| Thursday | A_frozen | 0.0000 | 0.0613 | Infiltration, Web Attack � Brute Force |
| Thursday | A_refit | 0.0000 | 0.0652 | Infiltration, Web Attack � Brute Force |
| Thursday | B_flat8 | 0.3750 | 0.0300 | Infiltration, Web Attack � Brute Force |
| Thursday | C_hierarchy | 0.1250 | 0.0548 | Infiltration, Web Attack � Brute Force |
| Thursday | D_behavior | 0.1250 | 0.0209 | Infiltration, Web Attack � Brute Force |

Entire assessment-day signatures are removed from other-day training/calibration; remaining groups split deterministically by task05-day SHA256 suffix. Monday contains only benign traffic and is not used for two-class day stress. A_frozen remains historically warm; only refitted candidates are day-clean for this diagnostic. Tuesday and Wednesday C/D recall are zero, violating the frozen gate. Wednesday C calibration chose the no-alert threshold 100 because no nontrivial calibration recall met the 5% FPR cap; zero assessment recall is then an explicit operating-policy consequence, not proof that score ranking contains no information. The full pipeline still fails the registered practical gate. Thus no new architecture is promoted, despite improved mixed-day internal results. Very small Thursday and rare-class supports prohibit stable attack-category conclusions. See per_class.csv; one Heartbleed assessment example cannot establish reliability.

Historical TASK02 exposed-test metrics remain unchanged and were not recomputed or used to tune architectures. No Friday labels/scores/errors or old grouped-test individual records entered selection. Near-duplicate bin-boundary dependence remains: TASK04 identified3169 adjacent-bin cross-role representative pairs. Original 698 conflicting-label full numerical groups and308381 extra exact rows remain documented. Severe exclusions change the evaluation population; these rates cannot estimate general traffic prevalence.

Figures: reports/figures/task05/{comparison,tradeoffs,scores_modules,memberships,rules,confusion}.png. They are regenerated local artifacts, ignored by Git. All unfavorable outcomes are preserved.
