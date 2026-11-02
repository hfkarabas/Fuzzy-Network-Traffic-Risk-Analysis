# Candidate comparison — internal validation only

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

Assessment support: 39,159 benign and
6,799 attack rows, 24,956
signature groups, across three assessments. Each group is trained on in one rotation,
calibrated on in another and assessed only when excluded from both those roles.
No future final test is claimed. Main table entries are means of group-weighted
fold metrics using Balanced policy; A_frozen's previous fit exposure is explicit.

| candidate | precision | recall | f1 | false_positive_rate | false_negative_rate | balanced_accuracy | roc_auc | pr_auc_average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A_frozen | 0.174595 | 0.210755 | 0.190959 | 0.049102 | 0.789245 | 0.580827 | 0.638296 | 0.11837 |
| A_refit | 0.095352 | 0.100406 | 0.097783 | 0.047568 | 0.899594 | 0.526419 | 0.605639 | 0.069478 |
| B_membership | 0.067745 | 0.071878 | 0.069656 | 0.047957 | 0.928122 | 0.51196 | 0.636173 | 0.071958 |
| C_rules | 0.011205 | 0.009521 | 0.010237 | 0.027991 | 0.990479 | 0.490765 | 0.692035 | 0.083236 |

Raw row confusion totals below use the corresponding fold-specific thresholds;
they are not the fractional group confusion counts underlying the macro means.

| candidate | row_tn | row_fp | row_fn | row_tp | benign_rows | attack_rows |
| --- | --- | --- | --- | --- | --- | --- |
| A_frozen | 33008 | 6151 | 5418 | 1381 | 39159 | 6799 |
| A_refit | 34451 | 4708 | 6105 | 694 | 39159 | 6799 |
| B_membership | 32985 | 6174 | 6321 | 478 | 39159 | 6799 |
| C_rules | 38355 | 804 | 6767 | 32 | 39159 | 6799 |

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

| candidate | paired_difference_CI_low | paired_difference_CI_high |
| --- | --- | --- |
| A_refit | 0.0 | 0.0 |
| B_membership | -0.019839 | -0.008684 |
| C_rules | -0.044522 | -0.028294 |

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

| policy | precision | recall | false_positive_rate | pooled_row_fpr | pooled_row_recall | false_negative_rate | balanced_accuracy | minimum_fold_recall | maximum_fold_recall | minimum_fold_fpr | maximum_fold_fpr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sensitive | 0.119248 | 0.271975 | 0.09915 | 0.21308 | 0.244301 | 0.728025 | 0.586413 | 0.244008 | 0.293923 | 0.09431 | 0.104863 |
| Balanced | 0.174595 | 0.210755 | 0.049102 | 0.157078 | 0.203118 | 0.789245 | 0.580827 | 0.174228 | 0.233821 | 0.048449 | 0.050342 |
| Conservative | 0.231512 | 0.060402 | 0.009842 | 0.011032 | 0.060156 | 0.939598 | 0.52528 | 0.045279 | 0.072075 | 0.009464 | 0.010067 |

Exact frozen integration thresholds (from bucket 1 calibration only) are Sensitive
49.632522849397, Balanced
51.809236850031, Conservative
59.465890915130. CV uses a separately
calibrated threshold per fold, so these fold means are not an independent evaluation
of the final single integration policy. Targets are 10%/5%/1% estimated FPR.
Realized assessment FPR can exceed them. selected_policy_uncertainty.json gives
group-bootstrap intervals for pooled policy recall/FPR/balanced accuracy. These
policies reduce nuisance alerts at substantial recall cost; scores and their AUC
are identical. No improvement in the fuzzy scoring model is claimed.
The caps explicitly target signature-group-weighted FPR, not per-flow FPR.
The retained model's Balanced pooled ROW false-positive rate is
15.7078%,
well above its approximately 5% GROUP-weighted rate. Repeated benign patterns change
the two empirical distributions. Both must remain visible; the target must never
be advertised as a demonstrated 5% per-flow false-alarm guarantee.

Feasibility audit (out of three folds): nontrivial means positive calibrated recall
within the target cap; a no-alert threshold can meet FPR without useful recall.

| candidate | policy | nontrivial_calibration_folds | assessment_fpr_cap_exceeded_folds |
| --- | --- | --- | --- |
| A_frozen | Sensitive | 3 | 1 |
| A_frozen | Balanced | 3 | 1 |
| A_frozen | Conservative | 3 | 1 |
| A_refit | Sensitive | 3 | 1 |
| A_refit | Balanced | 3 | 1 |
| A_refit | Conservative | 3 | 1 |
| B_membership | Sensitive | 3 | 0 |
| B_membership | Balanced | 3 | 1 |
| B_membership | Conservative | 3 | 1 |
| C_rules | Sensitive | 3 | 1 |
| C_rules | Balanced | 3 | 0 |
| C_rules | Conservative | 1 | 0 |

The supplemental leave-Wednesday-out stress (day_stress.json) excludes shared
signatures across days, uses other-day training/calibration, and is not used for
reselection. DoS families and Heartbleed are absent from its training population.
The frozen baseline remains warm because it was historically fitted on some such
records; only A_refit is training-role-pure there. It supplies no independent
temporal generalization claim.
