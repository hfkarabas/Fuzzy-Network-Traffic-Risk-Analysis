# Rule base and empirical coverage

## Fixed interpretable rules

| ID | antecedent | consequent | rationale |
| --- | --- | --- | --- |
| R01 | rate is sparse AND volume is few | Low | Sparse small flows alone provide little evidence of abnormal load; low-rate scans may evade this. |
| R02 | rate is sparse AND volume is moderate | Low | Modest traffic at a low packet rate has weak load evidence. |
| R03 | rate is sparse AND volume is many | Medium | Large low-rate flows merit context but may be legitimate long sessions. |
| R04 | rate is moderate AND volume is few | Low | Few packets at ordinary intensity can be routine transactions. |
| R05 | rate is moderate AND volume is moderate | Low | Ordinary rate and volume form a conservative low-load baseline. |
| R06 | rate is moderate AND volume is many | Medium | Large packet volume increases load concern without implying an attack. |
| R07 | rate is intensive AND volume is few | Medium | A tiny duration can inflate rate for a few packets; avoid critical risk from rate alone. |
| R08 | rate is intensive AND volume is moderate | High | Intensive activity with nontrivial volume supports load concern. |
| R09 | rate is intensive AND volume is many | High | High intensity and volume jointly support sustained-load concern. |
| R10 | rate is intensive AND size is small AND balance is forward | Critical | Small intensive forward-dominated traffic can resemble repeated request/control floods. |
| R11 | rate is intensive AND size is small AND variation is uniform | High | Intensive small packets with uniform responses can resemble repetitive traffic. |
| R12 | rate is moderate AND size is small AND balance is forward | High | Small forward-heavy transactions warrant investigation; legitimate one-way traffic overlaps. |
| R13 | volume is many AND size is small AND balance is forward | High | Many small forward packets can indicate repeated requests. |
| R14 | volume is many AND size is large AND variation is highly_variable | High | Large varied responses at high volume can produce resource pressure; benign transfers overlap. |
| R15 | rate is sparse AND size is large AND variation is highly_variable | Medium | Large varied responses at sparse rate are ambiguous rather than inherently safe. |
| R16 | rate is moderate AND size is large AND variation is highly_variable | High | Varied large responses at ordinary intensity may still describe costly transactions. |
| R17 | rate is moderate AND size is medium AND balance is balanced | Low | Balanced medium-size transactions provide a routine-traffic counter-hypothesis. |
| R18 | rate is sparse AND size is medium AND balance is balanced | Low | Sparse balanced transactions provide weak evidence of abnormal resource load. |
| R19 | volume is few AND size is small AND balance is forward | Medium | Small forward-only exchanges merit context, including scanning, but are not definitive. |
| R20 | rate is moderate AND variation is variable AND balance is balanced | Low | Ordinary intensity with varied balanced exchanges supports a benign counter-hypothesis. |
| R21 | rate is intensive AND size is large AND balance is backward | Medium | Fast backward-heavy payload transfer can be an ordinary download. |
| R22 | volume is many AND variation is uniform AND balance is backward | Medium | Large uniform directional transfer is ambiguous without application context. |

The first nine manually authored rate/volume rules guarantee a conservative base
response for all valid combinations of those two variables. They are not an
automatic enumeration of 243 five-variable combinations. Every rule uses at least
two behavioral antecedents. Rules 10–22 add multivariate concerns and benign
counter-hypotheses. All weights are 1. Zero evidence in a single unusual measurement
never determines the output alone. OR support is implemented/tested, although the
current fixed rule base uses AND to keep its interpretation compact.

## Actual test coverage

| scenario | rows | valid_scores | any_rule_fraction | multiple_rule_fraction | meaningful_rule_fraction | multiple_meaningful_rule_fraction | conflicting_low_high_fraction | outside_training_range_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| grouped | 1750 | 1750 | 1.0 | 0.9377142857142857 | 1.0 | 0.9137142857142857 | 0.3182857142857143 | 0.0 |
| day | 666572 | 666572 | 1.0 | 0.9453262363255582 | 1.0 | 0.9334850548777927 | 0.3967808428796889 | 3.000426060500591e-06 |

Meaningful activation means strength >=0.1; any activation means >0. The baseline
coverage is 100%, not evidence of detection quality. Low-versus-High/Critical
conflict means at least one rule from each side reaches 0.1. Conflicts affect
31.829% of grouped and
39.678% of day test records.
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
