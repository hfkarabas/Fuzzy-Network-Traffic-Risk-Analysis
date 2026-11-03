# TASK05 failure analysis

No single cause explains all errors. Expanded flat B loses nearly all attack recall at calibrated low FPR: mixed rule-output areas still overlap benign scores, and added evidence is insufficient under this particular rule design. This rejects this 15-rule flat hypothesis, not every possible flat eight-input system.

C/D improve mixed-day low-FPR recall, suggesting that separating timing/structure/load before final aggregation can reduce conflicts for some development behavior. However, their own per-day tests collapse on withheld Tuesday/Wednesday. Wednesday C calibration explicitly chooses a no-alert threshold 100 at the 5% cap: threshold transfer and a feasible operating policy are part of the failure, not only membership/rule discrimination. Packet and timing distributions, attack scenarios and benign applications change across days; previously absent classes cannot be inferred from labels the model never saw. No timing boundary was refitted on the held-out day. Thursday gains are supported by very few rare attack observations and do not rescue the promotion gate.

SYN export has very low nonzero prevalence, so the connection module is often Low. It cannot count attempts across flows and the integer ratio hides fractional response asymmetry. Timing and structure modules can respond to related long-transfer phenomena, so their corroboration may double-count ordinary downloads. High duration/IAT can reflect exporter timeout/application idle behavior rather than attacks. Membership saturation maps extreme-but-different observations to similar degrees; source-range notices do not repair lost context.

Intermediate centroids are deliberately compressed behavioral summaries; re-fuzzification can erase within-module distinctions. The final max/min union may concentrate scores around a few bands. Critical was not naturally produced by any new architecture on the design panel; no Critical example was invented. Its absence is a score-range/capacity limitation of these particular memberships and rules, not proof that no critical traffic exists. A high ROC-AUC does not guarantee useful recall at a strict FPR threshold; conversely D has lower global AUC but a better low-FPR internal operating point. Tables/curves retain both facts. More features or deeper layers are not automatically better.

rule_diagnostics.csv reports each module/final rule activation, mean strength and benign/attack/FP/FN associations; layer_conflicts.json records Low versus High/Critical overlap and coverage. Such associations are not causal contributions under max aggregation. membership_diagnostics.csv records term coverage/saturation. rule correlations are retained by layer. score_distributions.csv shows overlap and category-boundary concentration. explanation_examples.json includes deterministic real design FP/FN evidence generated only after selection; no rules were changed from these examples.

## Measured layer conflicts on eligible design data

| Candidate | Layer | Low/high conflict | Coverage | Median output |
|---|---|---:|---:|---:|
| B_flat8 | final | 17.55% | 100.00% | 16.4139 |
| C_hierarchy | intensity | 2.73% | 100.00% | 14.6066 |
| C_hierarchy | timing | 0.00% | 100.00% | 25.9465 |
| C_hierarchy | connection | 0.00% | 100.00% | 13.1650 |
| C_hierarchy | structure | 0.00% | 100.00% | 13.1650 |
| C_hierarchy | final | 0.00% | 100.00% | 35.0453 |
| D_behavior | flood | 2.73% | 100.00% | 13.1650 |
| D_behavior | intermittent | 0.00% | 100.00% | 25.9465 |
| D_behavior | connection | 0.00% | 100.00% | 13.1650 |
| D_behavior | final | 0.00% | 100.00% | 27.2286 |

## Per-class coverage — post-selection raw internal counts

C gains are concentrated in the dominant DoS Hulk class and trade away FTP-Patator coverage. This is development error analysis after selection, not an attack-label-based module or a new tuning round. Rare supports (especially Heartbleed1) do not establish class reliability. The table gives alerts, not calibrated severity.

| Label | Support | A_frozen alerts | C_hierarchy alerts | D_behavior alerts |
|---|---:|---:|---:|---:|
| BENIGN | 39159 | 6151 | 1278 | 1619 |
| DoS GoldenEye | 320 | 40 | 69 | 8 |
| DoS Hulk | 6059 | 1208 | 3882 | 3942 |
| DoS Slowhttptest | 168 | 0 | 2 | 16 |
| DoS slowloris | 92 | 22 | 0 | 1 |
| FTP-Patator | 118 | 110 | 0 | 0 |
| Heartbleed | 1 | 1 | 0 | 0 |
| Infiltration | 7 | 0 | 1 | 2 |
| SSH-Patator | 31 | 0 | 0 | 0 |
| Web Attack � Brute Force | 3 | 0 | 0 | 0 |

No confident attribution to feature insufficiency versus rule choice is possible from this limited comparison alone. Within-day dependence, known benchmark reuse, conflicting labels, selected-cohort exclusions, rare supports and unobserved host/session metadata remain. A new independent capture and predeclared factorial feature/architecture ablation are needed before claiming unseen-day detection improvement.
