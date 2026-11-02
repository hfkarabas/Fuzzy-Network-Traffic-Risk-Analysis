# Fuzzy input feature selection

## Ranked initial candidates

Recommended initial set: the five behavior measurements below, covering intensity,
volume, size, response variation and directional balance. Ratio is integer-valued
and needs careful overlapping terms. Source names are JSON
quoted to make leading whitespace explicit. Ranking reflects interpretability,
security relevance, completeness, numerical behavior and redundancy, not classifier training.

1. **`" Flow Packets/s"`** — Bidirectional packet intensity; packets/second. Linguistic candidates: Sparse / Moderate / Intensive. Intensive flows may indicate flooding; tiny durations make this rate unstable and benign bursts overlap.

2. **`" Total Fwd Packets"`** — Forward-direction packet volume; packets. Linguistic candidates: Few / Moderate / Many. Separates tiny bursts from sustained packet volume; legitimate long transfers can also have many packets.

3. **`" Packet Length Mean"`** — Average packet length within the flow; bytes. Linguistic candidates: Small / Medium / Large. Small packets with high intensity suggest control/request floods; large packets can be normal transfer traffic.

4. **`" Bwd Packet Length Std"`** — Variation in responder-direction packet sizes; bytes. Linguistic candidates: Uniform / Variable / Highly variable. Describes response behavior beyond mean size; zero may mean constant sizes or too few/no response packets.

5. **`" Down/Up Ratio"`** — Exported backward-to-forward packet ratio; dimensionless. Linguistic candidates: Forward dominated / Balanced / Backward dominated. Provides directional context with little correlation to packet size; integer quantization loses detail and zero can represent few or no response packets.

| rank | exact_column | unit | min | p01 | median | p95 | p99 | max | zero_percent | missing_percent | infinite_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | " Flow Packets/s" | packets/second | -2000000.0 | 0.062464900500000003 | 109.4759992228 | 666666.666666667 | 2000000.0 | 4000000.0 | 0.0 | 0.0 | 0.1012808298033414 |
| 2 | " Total Fwd Packets" | packets | 1.0 | 1.0 | 2.0 | 19.0 | 48.0 | 219759.0 | 0.0 | 0.0 | 0.0 |
| 3 | " Packet Length Mean" | bytes | 0.0 | 0.0 | 57.2 | 917.4615385 | 1292.555556 | 3337.142857 | 12.615945707540387 | 0.0 | 0.0 |
| 4 | " Bwd Packet Length Std" | bytes | 0.0 | 0.0 | 0.0 | 2181.008184 | 4128.319301 | 8194.660487 | 71.58947315245503 | 0.0 | 0.0 |
| 5 | " Down/Up Ratio" | dimensionless | 0.0 | 0.0 | 1.0 | 1.0 | 2.0 | 156.0 | 37.02847626930456 | 0.0 | 0.0 |

All statistics above describe finite original measurements before negative-value
nulling. The saved fuzzy-ready observations have finite nonnegative values only.
Missingness and infinite rates motivate an explicit abstention/unavailable-input
policy rather than arbitrary median substitution. Every selected input is a
behavior measurement, not an identifier or label. No label is passed to inference.
benign_attack_comparison.csv supplies full-data medians/p95/means by binary traffic
group: overlap is expected and no single variable is treated as a standalone detector.

## Redundancy and alternatives

candidate_spearman.csv and candidate_pearson.csv quantify the five proposed inputs
on all eligible observations. Inspect absolute rank correlations especially above
0.85 before adding rules; correlation is a distribution-dependent indicator, not
evidence of leakage. Full-data expanded_candidate_spearman.csv showed duration
versus packet rate at -0.9804, and IAT mean versus packet rate at -0.9967: duration
and IAT were excluded from the initial set to avoid redundant timing inputs.
Packet length mean and backward-size variation correlate around 0.73 but distinguish
size from within-flow diversity. Forward volume versus response variation is about
0.72; directional ratio adds a relatively independent aspect. Redundancy remains
moderate, so compare removing response variation in TASK 02 if rule complexity grows.

Alternatives (see the same exact full-data numeric profile and redundancy.json):
`" Flow IAT Mean"` or `" Flow Duration"` (microseconds) can replace intensity;
avoid adding them alongside rate given their near-perfect rank association.
`" SYN Flag Count"` provides optional absent/present context but is mostly binary
and must not be interpreted as a rate or handshake-failure counter.
`" PSH Flag Count"` is additional
discrete context rather than a strong graded fuzzy variable. `"Active Mean"`
(microseconds) describes active periods but is zero-heavy and tied to lifetime.

Rejected from the initial set: target label (direct leakage); destination port
(service/scenario shortcut risk and categorical semantics); constant bulk/flag
columns (no information); near-constant URG/CWE-style flags (rare context only);
duplicate forward header length, subflow totals and average-segment-size aliases
(redundancy); initial windows (sentinels, host/TCP-stack effects); header/minimum
segment sizes (negative artifacts); Flow Bytes/s together with packet rate and
mean length (substantial algebraic redundancy and invalid rates).
These original features remain in the cleaned dataset for future review.

## Preliminary membership recommendations

Use train-only valid-value distributions to propose overlapping triangular or
trapezoidal sets. Consider log1p coordinates for volume/intensity and response
variation, with physical units displayed in explanations. Explicit zero membership
is appropriate for response variation; zero does not automatically mean suspicious.
Use shoulders to cover the full finite nonnegative domain rather than clipping
extreme attacks. Compare train p25/p50/p75/p95 as starting anchors; the full-data
percentiles above are exploratory, NOT finalized boundaries. Do not fit from test.
For the directional ratio, anchor terms around forward domination, approximate
balance and backward domination after checking train-only integer frequencies.
No membership functions or inference engine are implemented in this task.

## Preliminary rule concepts

- IF packet intensity is intensive AND packet size is small AND direction is
  forward dominated, THEN elevated risk is plausible; validate against legitimate bursts.
- IF forward volume is many AND intensity is intensive, THEN sustained-load concern rises.
- IF intensity is sparse AND packet size is medium AND response variation is
  variable, THEN lower risk may be plausible, without assuming every sparse flow is benign.
- IF response variation is uniform AND packets are small AND intensity is intensive,
  THEN investigate repeated requests; zero responses alone must not trigger high risk.

These are hypotheses for interpretable rules, not calibrated severity assignments.
Sparse port scans, application attacks and low-volume infiltration may remain
undetectable using five aggregate features. TASK 02 must test those weaknesses and
decide whether optional TCP flag context improves explanations. Feature engineering must
remain compact; no conventional ML model was trained.
