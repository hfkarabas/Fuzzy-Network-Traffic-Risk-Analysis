# Implemented fuzzy system (v1)

## Architecture and scope

The implementation is a genuine five-input, one-output Mamdani system. It trains
no conventional classifier or neural network. Fuzzification uses three overlapping
sets per input; AND uses minimum, OR maximum, implication minimum clipping,
aggregation maximum and defuzzification a numerical centroid. Twenty-two explicit
hand-written rules are shared by both models. Rules are hypotheses about load and
behavior, not attack-type proofs. No web interface or additional dependency was added.

Memberships are derived separately for the grouped-development and coarse-day
protocols. Grouped train has 8,217 deliberately class-stratified
observations; day train has 1,607,145 eligible nonquarantined
Monday–Wednesday observations at their original proportions. Training labels are
used for diagnostics only; the fitting function accepts exactly the five numerical
input columns and rejects labels/metadata. Class-stratified sampling indirectly
affects training distributions, so the two scores are model-relative indices.

## Input semantics and fitted anchors

| scenario | column | unit | transform | training_min | training_max | low_anchor | middle_anchor | high_anchor | zero_fraction | basis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| grouped | " Flow Packets/s" | packets/second | log1p | 0.016810297 | 3000000.0 | 0.679313445 | 7.351800761799999 | 45454.54545 | 0.0 | training_p25_p60_p90 |
| grouped | " Total Fwd Packets" | packets | log1p | 1.0 | 5523.0 | 2.0 | 4.0 | 10.0 | 0.0 | training_p25_p60_p90 |
| grouped | " Packet Length Mean" | bytes | identity | 0.0 | 1797.637931 | 0.0 | 12.04 | 853.0285714400001 | 0.30059632469271025 | training_p25_p60_p90 |
| grouped | " Bwd Packet Length Std" | bytes | log1p | 0.0 | 5816.0 | 72.23111056 | 1762.5 | 3562.314293800001 | 0.6407447973713034 | training_positive_p25_p60_p90 |
| grouped | " Down/Up Ratio" | dimensionless | identity | 0.0 | 6.0 | 0.0 | 1.0 | 2.0 | 0.5526347815504442 | domain_backward_forward_ratio_0_1_2 |
| day | " Flow Packets/s" | packets/second | log1p | 0.0167017113 | 3000000.0 | 1.950462726 | 165.0777929 | 60606.0606060606 | 0.0 | training_p25_p60_p90 |
| day | " Total Fwd Packets" | packets | log1p | 1.0 | 219759.0 | 2.0 | 3.0 | 13.0 | 0.0 | training_p25_p60_p90 |
| day | " Packet Length Mean" | bytes | identity | 0.0 | 3337.142857 | 6.0 | 76.4 | 793.2 | 0.16973266257867212 | training_p25_p60_p90 |
| day | " Bwd Packet Length Std" | bytes | log1p | 0.0 | 6715.738331 | 396.788471210025 | 864.4572478343 | 2537.820147 | 0.6754630104937638 | training_positive_p25_p60_p90 |
| day | " Down/Up Ratio" | dimensionless | identity | 0.0 | 108.0 | 0.0 | 1.0 | 2.0 | 0.4068058575921899 | domain_backward_forward_ratio_0_1_2 |

Rate is packets/second, volume packets, mean packet length and response standard
deviation bytes. Physical units follow the source's CICFlowMeter naming convention,
not unit-tagged Arrow metadata. Forward/backward are flow directions, not proof of
client/server identity. The integer Down/Up Ratio equals floor(backward packets /
forward packets) in all 1,607,145 checked day-train rows.
Thus ratio zero means backward count is LESS than forward count; it does not imply
no responses. A ratio of one also covers some backward-heavy flows due to quantization.
The compact terms forward/balanced/backward are approximate directional descriptions.
In rule rationale R19, 'forward-only' is a hypothesis shorthand, never an inference
that the export proves absence of response packets. Response standard deviation
zero can mean uniform packets or too few/no responses, not maliciousness.

Rate, volume and variation use log1p to compress skew; packet size and ratio use
identity. Except ratio, anchors use training p25/p60/p90; variation uses positive
training values because zero is a large discrete mass. Repeated anchors are expanded
deterministically by max(1 physical unit, 1% of the first anchor). This prevents
degenerate triangles; it is a numerical fallback, not label-based optimization.
Ratio anchors 0/1/2 express forward domination, approximate balance and backward
domination based on domain semantics. Exact quantiles and all triangle/trapezoid
vertices are serialized in config/fuzzy/*_v1.json. Full TASK 01 or test quantiles
were not used to fit memberships.

Each low set is trap(0,0,a,b), middle tri(a,b,c), high trap(b,c,U,U), with U at least
the transformed training maximum and c. This is a complete, overlapping partition
of the saturated nonnegative domain. Extreme finite values saturate at U; valid
values outside observed training min/max are separately flagged. There is no
outlier deletion, normalization fit, or invalid-to-zero imputation. Internally a
safe placeholder is used only for arithmetic; invalid rows have zero activations
and no returned score.

## Output, centroid and categories

Fixed output sets: Low trap(0,0,15,35); Medium tri(20,45,65); High tri(50,70,85);
Critical trap(75,90,100,100). These are transparent design choices for a behavior
index, not estimated severity labels. The centroid integrates the maximum clipped
membership on 201 equally spaced points from 0 to 100, using trapezoidal quadrature.
Rules with a common consequent reduce by maximum before constructing four clipped
output sets; this is algebraically identical to aggregating every rule's output.
The score is bounded in [0,100]; centroid geometry need not attain exactly 0 or 100.
With no aggregate area the engine abstains. No-rule abstention is tested even
though the baseline rate/volume rules cover the approved valid domain.

Categories use lower-inclusive cut points: Low [0,25), Medium [25,50),
High [50,75), Critical [75,100]. They are intentionally fixed rather than tuned to
traffic labels. The separate binary alert threshold is 25.0
for grouped and 75.0 for day; a Medium category can therefore
raise an alert in the grouped model. Scores are neither attack probabilities nor
calibrated risk severity. Rule consequents need not equal the final category when
several output sets aggregate.

## Freeze/calibration protocol

Rules were written before evaluation and never optimized from test labels.
Training-only memberships were fitted first. Validation considered exactly six
alert thresholds (25,35,45,55,65,75), maximizing balanced accuracy, with the highest
threshold winning ties. No membership boundary, output set, rule weight or rule
consequent was tuned on validation or test. Configurations were persisted and their
SHA256 identifiers frozen before test inference; scripts assert unchanged digests.
Calibration tables record every choice. The day validation best balanced accuracy
is below chance: its selected threshold is a failed calibration outcome, not a
recommended operational setting. No test-driven repair was made.

## APIs and invalid-input policy

`MamdaniRiskEngine.load(path).predict_one(mapping)` returns status, score, category,
alert, membership degrees, every positive-strength rule, consequents, rationale,
translation keys and explanation text. `predict_batch(DataFrame)` provides arrays
of scores/statuses/categories, memberships, rule strengths and range flags.
Only the five exact column names are accepted; extra labels/metadata raise ValueError.
Missing columns, null, NaN, either infinity, negative values, numeric strings,
booleans and malformed values produce invalid_input and no score. Unrepresentable
integers are also unavailable. Valid zeros are processed normally. No rule produces
status no_rule_activation with no score. Batch unavailable scores use NaN internally;
single-record JSON converts them to null. The CLI is scripts/score_flow.py.
Structured message/risk/rule/feature/term keys permit a later Turkish display layer;
English prose is separate from the inference evidence. Explanations describe
activations, not a causal decomposition of the centroid or proof of an attack.

## Numerical and performance validation

On 256 training records per model, single/batch scores were bitwise identical,
including reload and different batch sizes. Against a 2,001-point output grid,
maximum absolute score differences were 0.009647
(grouped) and 0.007485 (day).
This bounded numerical check is not a proof over every possible input.
See numerical_validation.json for exact results and single-record timing.
