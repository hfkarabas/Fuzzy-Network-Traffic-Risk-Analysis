# Feature sufficiency audit — TASK02B

Only the 14,042-row eligible design panel was used for feature
screening. No exposed or comparison-assessment feature/label associations informed
feature changes. All exact names, missingness, zero frequency, ranges, medians,
p95, correlations and descriptive per-day univariate AUCs are in
task02b/feature_audit.csv and design_feature_correlations.csv. These are descriptive
associations, not trained classifiers or feature-importance explanations.

| feature | invalid_percent | zero_percent | max_abs_existing_spearman | univariate_direction_stable_across_days |
| --- | --- | --- | --- | --- |
|  Flow Packets/s | 0.0 | 0.0 | 0.70538 | False |
|  Total Fwd Packets | 0.0 | 0.0 | 0.723662 | False |
|  Packet Length Mean | 0.0 | 1.887196 | 0.892604 | False |
|  Bwd Packet Length Std | 0.0 | 38.249537 | 0.892604 | False |
|  Down/Up Ratio | 0.0 | 61.579547 | 0.41511 | False |
|  Flow Duration | 0.0 | 0.0 | 0.965121 | True |
|  Flow IAT Mean | 0.0 | 0.0 | 0.998544 | False |
|  Flow IAT Std | 0.0 | 25.936476 | 0.966066 | False |
| Flow Bytes/s | 0.0 | 1.887196 | 0.856143 | True |
|  Total Backward Packets | 0.0 | 28.122775 | 0.896722 | False |
|  SYN Flag Count | 0.0 | 95.392394 | 0.155356 | False |
|  ACK Flag Count | 0.0 | 82.224754 | 0.141454 | False |
|  PSH Flag Count | 0.0 | 30.686512 | 0.348269 | False |
|  Fwd Header Length | 0.007121 | 0.028486 | 0.977454 | False |
|  min_seg_size_forward | 0.007121 | 0.028486 | 0.125276 | False |

Rate and integer directional ratio alone do not capture applications, destination
semantics, host behavior, cross-flow scan frequency or complete TCP handshakes.
Mean size and backward size variation correlate about 0.893 on this design panel.
One identical five-input vector has contradictory traffic labels in this panel.
The five inputs are NOT established as sufficient for attack identification.

Duration and IAT statistics have maximum rank correlations 0.965–0.999 with the
existing inputs and can reintroduce redundant timing. Flow Bytes/s is related to
packet rate and packet size; its per-day direction alone is not evidence of
incremental value. Backward count has correlation about 0.897 with existing features,
while integer ratio already provides approximate direction. SYN/ACK/PSH exports
are binary context, not rates or proof of handshake failure. Their label association
changes across days and scenario mix. Header length strongly tracks volume
(correlation about 0.977), with some unavailable measurements; minimum segment size
has extraction/stack/artifact concerns and inconsistent cross-day behavior.
No identifiers or ports are candidates. Zero measurements are not treated as invalid.

Feature screening is uncertain: Monday has only benign traffic and retained
Thursday attack support is tiny. Direction-consistent AUC flags therefore do NOT
establish stability or causation. Per-day attack counts are in partition_classes.csv.
Given redundancy, unstable associations and no convincing conditional benefit,
Candidate D was explicitly NOT implemented. This decision was frozen before any
candidate comparison. A six/seven-input system is deferred, not rejected forever.
The current task evaluates two compact five-input refinements, preserving physical
interpretability and avoiding complexity unsupported by eligible development evidence.
