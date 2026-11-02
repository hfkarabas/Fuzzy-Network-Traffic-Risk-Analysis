# Development-only diagnostics — TASK02B

Diagnostic scope: the 14,042-row reserved design panel
(11,612 benign, 2,430 attacks; 6,186
signature groups). This panel is separate from model-comparison roles. The original
grouped TASK02 model and embedded threshold 25 are diagnostic reference only.
Its design signature-weighted FPR is 0.877509,
recall 0.912636, ROC-AUC
0.638842. These are not old test measurements.

## Score overlap and threshold confusion

| traffic | rows | min | p05 | p25 | median | p75 | p95 | max | within_one_point_of_category_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benign | 11612 | 13.165 | 14.74483 | 31.40755 | 43.331547 | 63.940592 | 63.991498 | 79.50125 | 0.044523 |
| Attack | 2430 | 13.165 | 22.376407 | 32.512963 | 38.578505 | 44.657863 | 58.647406 | 79.50125 | 0.042387 |

Benign median score exceeds attack median. Medium-only R03 has centroid around
43.333, which exceeds the embedded binary threshold 25. Therefore benign-looking
ambiguous volume patterns become alerts even when the category is only Medium.
This is a scoring-versus-operating-policy distinction, not numerical failure.
The full design PR/FPR-recall tradeoff is saved, rather than checking six coarse
thresholds. Sensitive/Balanced/Conservative policies target estimated FPR caps of
10%/5%/1%; calibration targets are not future guarantees.

## Rule diagnostics

| id | consequent | activation_fraction | mean_strength | benign_fraction | attack_fraction | active_false_positives | active_false_negatives |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | Low | 0.032901 | 0.024156 | 0.036858 | 0.013992 | 29 | 29 |
| R02 | Low | 0.204387 | 0.103246 | 0.119015 | 0.612346 | 887 | 145 |
| R03 | Medium | 0.339909 | 0.218699 | 0.267568 | 0.685597 | 2935 | 95 |
| R04 | Low | 0.081114 | 0.044697 | 0.075181 | 0.109465 | 508 | 3 |
| R05 | Low | 0.200399 | 0.087333 | 0.199104 | 0.206584 | 1922 | 19 |
| R06 | Medium | 0.34938 | 0.198947 | 0.399845 | 0.10823 | 4564 | 12 |
| R07 | Medium | 0.333428 | 0.29227 | 0.37754 | 0.122634 | 4293 | 1 |
| R08 | High | 0.123558 | 0.04507 | 0.115742 | 0.160905 | 1299 | 7 |
| R09 | High | 0.184304 | 0.056128 | 0.211936 | 0.052263 | 2461 | 0 |
| R10 | Critical | 0.276741 | 0.220943 | 0.309766 | 0.11893 | 3597 | 0 |
| R11 | High | 0.313203 | 0.241151 | 0.339649 | 0.186831 | 3924 | 0 |
| R12 | High | 0.031121 | 0.016322 | 0.013434 | 0.115638 | 148 | 0 |
| R13 | High | 0.012463 | 0.004586 | 0.004564 | 0.050206 | 53 | 0 |
| R14 | High | 0.081684 | 0.033527 | 0.00155 | 0.464609 | 18 | 0 |
| R15 | Medium | 0.083891 | 0.054911 | 0.000861 | 0.480658 | 10 | 13 |
| R16 | High | 0.016522 | 0.005652 | 0.001206 | 0.089712 | 14 | 0 |
| R17 | Low | 0.151261 | 0.075344 | 0.169566 | 0.063786 | 1498 | 0 |
| R18 | Low | 0.123273 | 0.072481 | 0.137875 | 0.053498 | 1047 | 5 |
| R19 | Medium | 0.257727 | 0.209512 | 0.306838 | 0.023045 | 3556 | 0 |
| R20 | Low | 0.170061 | 0.093731 | 0.198071 | 0.036214 | 2119 | 10 |
| R21 | Medium | 0.010682 | 0.004984 | 0.007234 | 0.02716 | 82 | 1 |
| R22 | Medium | 0.007121 | 0.002332 | 0.008612 | 0.0 | 100 | 0 |

R06/R07 provide broad Medium evidence on benign flows. R10/R11's small, intensive
patterns and R19's few/small/forward concern are more frequent among benign design
rows than attacks. R14/R15 response-pattern concerns are comparatively specific
on this panel, but this can reflect Wednesday scenario composition. Low baseline
rules activate on attacks as well. Removing all Low patterns would suppress honest
counter-evidence and would not solve feature overlap. Low versus High/Critical
activation conflicts occur in 25.3311% of design rows.
Max aggregation means correlated same-consequent rules can be redundant and frequent
activation is not an additive score contribution. design_rule_correlations.csv
quantifies redundancy; design_rule_removal_sensitivity.csv measures algorithmic
leave-one-rule-out score changes on the first 2,048 design rows. This is not causal
evidence about malicious behavior. A few sample sensitivities:

| rule | mean_score_contribution_on_retained_coverage | max_abs_score_change | no_coverage_after_removal |
| --- | --- | --- | --- |
| R01 | -0.010879 | 5.050433 | 11 |
| R02 | -0.833983 | 20.400093 | 5 |
| R03 | 2.024401 | 25.673109 | 143 |
| R04 | -0.296166 | 38.937183 | 0 |
| R05 | -2.015581 | 38.443146 | 0 |
| R06 | -2.530136 | 24.141447 | 0 |
| R07 | 0.208569 | 23.631423 | 3 |
| R08 | 0.550848 | 48.297625 | 1 |
| R09 | 1.656798 | 13.734828 | 2 |
| R10 | 0.097269 | 12.199974 | 0 |
| R11 | 0.104993 | 10.693277 | 0 |
| R12 | 0.043576 | 10.672672 | 0 |
| R13 | 0.0 | 0.0 | 0 |
| R14 | 0.000895 | 1.421536 | 0 |
| R15 | 0.0 | 0.0 | 0 |
| R16 | 0.0 | 0.0 | 0 |
| R17 | -0.164063 | 15.775897 | 0 |
| R18 | -0.662768 | 15.663052 | 0 |
| R19 | 0.149712 | 13.601305 | 0 |
| R20 | -0.989364 | 15.751524 | 0 |
| R21 | -0.001022 | 1.991016 | 0 |
| R22 | 0.0 | 0.0 | 0 |

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
