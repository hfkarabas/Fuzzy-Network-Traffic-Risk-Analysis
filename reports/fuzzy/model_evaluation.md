# Frozen-model evaluation

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

| scenario | weighting | test_rows | threshold | precision | recall | f1 | false_positive_rate | false_negative_rate | balanced_accuracy | roc_auc | pr_auc_average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| grouped | rows | 1750 | 25.0 | 0.925684 | 0.8875 | 0.90619 | 0.76 | 0.1125 | 0.56375 | 0.532175 | 0.912546 |
| grouped | observation groups | 1750 | 25.0 | 0.920455 | 0.878049 | 0.898752 | 0.756757 | 0.121951 | 0.560646 | 0.511328 | 0.898603 |
| day | rows | 666572 | 75.0 | 0.006309 | 6.3e-05 | 0.000124 | 0.007483 | 0.999937 | 0.49629 | 0.742552 | 0.602872 |
| day | observation groups | 666572 | 75.0 | 0.006345 | 8.2e-05 | 0.000161 | 0.007514 | 0.999918 | 0.496284 | 0.700521 | 0.498976 |

Grouped: TN=36, FP=114, FN=180, TP=1,420.

Day: TN=376,010, FP=2,835, FN=287,709, TP=18.

Group-weighted metrics assign each full-observation group total weight one,
distributing its weight among its rows, including conflicting labels. They measure
a different empirical distribution, not independent hosts or sessions. Duplicate
weighting reduces day ROC-AUC from 0.74255 to 0.70052. Both are reported.

## Per-class recall and false negatives

### Grouped test

| label | support | alert_count | false_negatives | attack_recall | benign_false_positive_rate | median_score |
| --- | --- | --- | --- | --- | --- | --- |
| BENIGN | 150 | 114 | 0 | not applicable | 0.76 | 38.46619876670859 |
| Bot | 150 | 110 | 40 | 0.7333333333333333 | not applicable | 30.46624397691712 |
| DDoS | 150 | 128 | 22 | 0.8533333333333334 | not applicable | 38.700578367258814 |
| DoS GoldenEye | 150 | 123 | 27 | 0.82 | not applicable | 42.8817565324106 |
| DoS Hulk | 150 | 144 | 6 | 0.96 | not applicable | 41.365889418561906 |
| DoS Slowhttptest | 150 | 110 | 40 | 0.7333333333333333 | not applicable | 43.61380104115651 |
| DoS slowloris | 150 | 117 | 33 | 0.78 | not applicable | 31.641476346815026 |
| FTP-Patator | 150 | 150 | 0 | 1.0 | not applicable | 53.46921365868502 |
| Heartbleed | 2 | 2 | 0 | 1.0 | not applicable | 51.59932216109414 |
| Infiltration | 4 | 3 | 1 | 0.75 | not applicable | 28.50695905127475 |
| PortScan | 150 | 150 | 0 | 1.0 | not applicable | 53.445002774931524 |
| SSH-Patator | 150 | 150 | 0 | 1.0 | not applicable | 29.19162481580878 |
| Web Attack � Brute Force | 150 | 142 | 8 | 0.9466666666666667 | not applicable | 29.1081930802564 |
| Web Attack � Sql Injection | 3 | 0 | 3 | 0.0 | not applicable | 14.177101245339426 |
| Web Attack � XSS | 91 | 91 | 0 | 1.0 | not applicable | 29.221110381625707 |

### Day test

| label | support | alert_count | false_negatives | attack_recall | benign_false_positive_rate | median_score |
| --- | --- | --- | --- | --- | --- | --- |
| BENIGN | 378845 | 2835 | 0 | not applicable | 0.007483271522654384 | 31.99644495256675 |
| Bot | 1956 | 0 | 1956 | 0.0 | not applicable | 34.50227108321895 |
| DDoS | 128020 | 18 | 128002 | 0.00014060303077644118 | not applicable | 35.16155503043186 |
| PortScan | 157751 | 0 | 157751 | 0.0 | not applicable | 52.60087970365529 |

Heartbleed has only two grouped test examples; 2/2 detections do not establish
reliable performance. Day training contains all 11 Heartbleed examples and Friday
contains none, so day Heartbleed recall is unavailable. SQL injection is missed
on all three grouped examples. No attack type is inferred by the engine itself.

## Leakage and independence limitations

Full-original-feature observation groups do not cross the saved grouped/day
partitions; TASK 01 explicitly verified this. This does not imply independence of
the selected five-variable projections. projected_input_overlap.json additionally
measures exact five-input patterns spanning partitions:

| scenario | five_input_groups_spanning_partitions | test_rows_in_those_groups | total_rows_in_those_groups |
| --- | --- | --- | --- |
| grouped | 270 | 309 | 1797 |
| day | 48289 | 187815 | 641648 |

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
