# Fuzzy inference API and integration contract

The public implementation is `fuzzy_network_risk.engine.MamdaniRiskEngine`.
Load a versioned model with `MamdaniRiskEngine.load(path)` and treat its configuration
as immutable. No network service, web framework or GPU is required. The default
educational demonstration configuration is `config/fuzzy/grouped_v1.json`; the day
configuration is a separate evaluation model, not an automatically switched model.

## Input

Pass a mapping to `predict_one` or a list of mappings / DataFrame to `predict_batch`.
Only these exact keys are permitted:

| Exact JSON key | Meaning | Unit |
| --- | --- | --- |
| `" Flow Packets/s"` | exported flow packet rate | packets/second |
| `" Total Fwd Packets"` | forward packet volume | packets |
| `" Packet Length Mean"` | mean packet length | bytes |
| `" Bwd Packet Length Std"` | backward-direction size standard deviation | bytes |
| `" Down/Up Ratio"` | integer backward/forward packet ratio | dimensionless |

Forward/backward do not necessarily identify client/server. In all checked day-train
rows the ratio equals floor(backward packets / forward packets). Thus zero means
forward domination, not necessarily no response; a value of one loses fractional
backward domination. Zero response variation is also ambiguous. R19's historical
English rationale uses 'forward-only' as a hypothesis shorthand; structured evidence
and the caveat keys must not be presented as proof of no responses.

Numeric JSON values must be finite and nonnegative. Zero is valid. Negative,
missing, null, infinity, NaN, boolean, numeric-string, malformed and unrepresentable
values produce invalid_input, with the affected feature names. Extra keys, including
the target or source IDs, raise ValueError as a schema error. The future UI should
convert user-entered text to validated numbers before calling the engine.

## Single-record result

- `status`: `ok`, `invalid_input`, or `no_rule_activation`.
- `risk_score`: float in [0,100], or JSON null on abstention.
- `risk_level`: Low / Medium / High / Critical, or null.
- `alert`: score >= the model's frozen alert threshold, or null.
- `membership_degrees`: exact source keys -> linguistic terms -> [0,1] degrees.
- `activated_rules`: every rule with strength >0, sorted by descending strength
  then ID. Includes strength, consequent, antecedent, `reason_key`, and English rationale.
- `explanation_data`: stable message/risk/rule/caveat keys, invalid feature names
  and outside-training-range names for a translation layer.
- `explanation`: English display prose, separate from structured evidence.
- `model_id`: SHA256 of the full serialized model configuration.

`invalid_input` and `no_rule_activation` never silently mean Low risk. A future UI
should display an unavailable result, not coerce null to zero. Numeric strings are
intentionally rejected at the engine boundary. Values above the training range
remain valid, saturate shoulder memberships and carry a range flag. Scores do not
represent a probability or attack type; output categories do not have severity truth.
Risk category boundaries are 25/50/75; binary alert thresholds are separately
calibrated (25 grouped, 75 day), so a grouped Medium result may raise an alert.

## Batch result and memory

`predict_batch(inputs, batch_size=2048)` returns numerical/status/category arrays,
a row-by-rule strength matrix, memberships keyed by model feature/term and a
row-by-feature range mask. Invalid score array entries are NaN internally; use
`predict_one` for JSON-safe results or explicitly convert unavailable batch values
to null before serializing. Input-row order is preserved, not the DataFrame index.
An empty batch returns empty arrays. No-rule configurations abstain safely.

Inference is vectorized over rows. It loops over five features, 22 rules and four
output sets. Centroid workspace is bounded by the internal batch size; returning
all memberships/strengths still costs O(number of rows). For millions of records,
stream outer frames such as 8,192 rows and write compact predictions as in
`scripts/run_fuzzy.py`. A 2,048 x 201 float64 grid is about 3.3 MB per workspace;
aggregation/integration temporaries add several such arrays. Large evaluation
metric sorting and saved prediction summaries consume memory separately.

## Reproducibility and evaluation

Model parameters and rules are in JSON. `config/fuzzy/frozen_manifest.json` records
configuration digests frozen before testing. Training/validation calibration audit
records and every six-threshold choice are in reports/fuzzy. No labels enter the
five-column inference frame. No sklearn model or neural network is trained.

Grouped and temporal metrics differ greatly. This implementation is suitable for
explaining fuzzy inference in a local course-project UI. Its measured false alarms
and misses do not support operational security deployment. The future UI should
include that empirical limitation rather than implying trusted attack detection.
