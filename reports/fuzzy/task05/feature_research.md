# TASK05 feature research

All 78 numerical source columns were audited on the 14,042 eligible design rows and three training roles. Exact names, cleaned-stage validity, ranges, p01/p25/median/p75/p95/p99, zeros, uniqueness, redundancy and mixed-day univariate AUC are in feature_audit.csv. Every feature has a physical dimension, unit/meaning caveat and decision in feature_semantics.csv. No assessment or exposed-test labels were screened to choose the feature representation.

Set A is the original five inputs. Sets B/C/D contain those five plus Flow Duration, Flow IAT Std and SYN Flag Count, preserving leading spaces. They represent intensity/volume, structure, coarse asymmetry, persistence, spacing variability and handshake information. The hierarchical set divides them into small overlapping groups; it is not a larger input list.

Duration and IAT are correlated with rate/volume, but the research hypothesis is conditional persistence/spacing behavior, not independent univariate information. Positive-subset IAT anchors distinguish spacing spread from a point mass at zero. SYN is supplementary and zero-heavy; its cross-day class association is unstable. In this export it is observed only as 0/1, so it is modeled as absent/present rather than a count of repeated attempts. No single TCP flag establishes maliciousness.

Alternative flags, forward/backward IAT and active/idle statistics were measured, not added in an uncontrolled search. Bulk counters that are constant cannot help. Forward Header Length.1 and several subflow/segment statistics duplicate or closely derive other measurements (see duplicate_feature_columns.json). Packet variance and std are algebraically related; bytes/s shares volume/size/duration. Port is excluded as a service/scenario shortcut. Window, minimum-segment and header statistics can encode exporter/stack artifacts. These are reasons for compactness and caution, not a proof that rejected measurements contain no conditional information.

The current five features are not proven sufficient: expanded hierarchical hypotheses improve within-development recall. But expanded flat rules fail and day stress collapses, so this does not isolate an architecture-only or feature-only causal benefit. A separate preregistered ablation would be needed; no additional candidate was added after these outcomes.

The current upstream exporter source calculates duration-based rates using microseconds, exports IAT statistics and implements integer packet-ratio division. This supports semantic interpretation, but its current revision is not proof of the exact historical exporter binary used for the HF dataset. See [CICFlowMeter BasicFlow.java](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java).

| Input | Dimension | Design median | Design p95 | Missing |
|---|---|---:|---:|---:|
| ` Flow Packets/s` | intensity | 37.4623 | 41666.7 | 0.00% |
| ` Total Fwd Packets` | volume/direction | 6 | 41 | 0.00% |
| ` Packet Length Mean` | structure/direction | 137 | 998 | 0.00% |
| ` Bwd Packet Length Std` | structure/direction | 172.523 | 2566.89 | 0.00% |
| ` Down/Up Ratio` | direction | 0 | 1 | 0.00% |
| ` Flow Duration` | temporal | 398632 | 1.08956e+08 | 0.00% |
| ` Flow IAT Std` | temporal | 52135.5 | 2.71e+07 | 0.00% |
| ` SYN Flag Count` | connection | 0 | 0 | 0.00% |

These validity rates describe the unchanged TASK01 cleaned subset. Raw invalids were already nulled by documented cleaning; they cannot be retrospectively classified as new raw-source defects here. There were no extra complete-case exclusions for the eight selected inputs. Distribution/association is not causal security evidence.
