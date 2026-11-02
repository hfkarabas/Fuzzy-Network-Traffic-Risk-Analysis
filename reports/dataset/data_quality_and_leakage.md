# Data quality and leakage

## Confirmed baseline findings

All counts describe the full 2,830,743-row source, not a sample. Row percentages
use the full source denominator; cell categories overlap.

| feature | missing | positive_inf | negative_inf | negative | minimum | maximum |
| --- | --- | --- | --- | --- | --- | --- |
| " Flow Duration" | 0 | 0 | 0 | 115 | -13.0 | 119999998.0 |
| "Flow Bytes/s" | 1358 | 1509 | 0 | 85 | -261000000.0 | 2071000000.0 |
| " Flow Packets/s" | 0 | 2867 | 0 | 115 | -2000000.0 | 4000000.0 |
| " Flow IAT Mean" | 0 | 0 | 0 | 115 | -13.0 | 120000000.0 |
| " Flow IAT Max" | 0 | 0 | 0 | 115 | -13.0 | 120000000.0 |
| " Flow IAT Min" | 0 | 0 | 0 | 2891 | -14.0 | 120000000.0 |
| " Fwd IAT Min" | 0 | 0 | 0 | 17 | -12.0 | 120000000.0 |
| " Fwd Header Length" | 0 | 0 | 0 | 35 | -32212234632.0 | 4644908.0 |
| " Bwd Header Length" | 0 | 0 | 0 | 22 | -1073741320.0 | 5838440.0 |
| " Fwd Header Length.1" | 0 | 0 | 0 | 35 | -32212234632.0 | 4644908.0 |
| "Init_Win_bytes_forward" | 0 | 0 | 0 | 1001189 | -1.0 | 65535.0 |
| " Init_Win_bytes_backward" | 0 | 0 | 0 | 1441552 | -1.0 | 65535.0 |
| " min_seg_size_forward" | 0 | 0 | 0 | 35 | -536870661.0 | 138.0 |

NaN/missing rows: 1,358 (0.0480%); infinite rows:
2,867 (0.1013%); negative-measurement rows:
1,444,427 (51.0264%). Infinity and NaN are mathematically unavailable.
Negative durations, rates, packet/header lengths and segment sizes are physically
implausible under the stated measurement interpretation. Negative initial TCP
windows (notably -1) can be unavailable/sentinel codes, not attack evidence.
All negative numerical values are conservatively nulled in derived outputs,
with no row deletion. Zero durations are retained; derived infinite rates are
nulled, without dividing by zero or reconstructing rates. Large finite rates,
long durations, extreme packet counts and heavy tails are retained. No winsorizing.
Finite values above p99 or below p01 are explicitly counted in numeric_profile.csv;
they are NOT classified as invalid. Other protocol-specific plausibility limits
cannot be reliably determined without protocol and capture metadata.

Exact duplicate source rows beyond the first: **308,381 (10.8940%)**;
95,169 repeated groups, involving
403,550 rows. These counts use exact SQL grouping
over all 79 source columns, with nulls/NaNs grouped consistently by DuckDB.
Identical numerical observations ignoring the label: 309,079
excess rows in 95,479 groups.
Contradictory labels for otherwise identical numerical observations:
698 groups involving
7,020 rows. Without flow identifiers these
may be repeated distinct flows; neither deduplication nor label relabeling is justified.
Duplicates are retained, flagged through group IDs, and never separated across partitions.

Duplicate literal column names: 0.
Constant columns: ` Bwd PSH Flags`, ` Bwd URG Flags`, `Fwd Avg Bytes/Bulk`, ` Fwd Avg Packets/Bulk`, ` Fwd Avg Bulk Rate`, ` Bwd Avg Bytes/Bulk`, ` Bwd Avg Packets/Bulk`, `Bwd Avg Bulk Rate`.
Near-constant means >=99% identical finite values among all source rows:
` Fwd URG Flags`, ` RST Flag Count`, ` CWE Flag Count`, ` ECE Flag Count`.
Very low variance is also visible in std and unique_finite in numeric_profile.csv.
`" Fwd Header Length.1"` is a semantically duplicated header feature; pair checks
in redundancy.json distinguish exact equal columns from highly correlated ones.

## Confirmed risks and controls

The target `" Label"` is explicitly excluded from INPUTS, tested and schema validated.
Ports may identify scenario services and are omitted from the initial input set.
No IP/time/session columns are supplied as source features; capture-day/file
origins are recovered separately, with exact full-row verification. Duplication makes ordinary row-random
splits optimistic. Cleaned observations are grouped ignoring labels using stable
64-bit hashes over all original cleaned numerical features. Identical observations
necessarily share hashes. Hash collisions can only conservatively merge distinct
groups, not split identical observations. Source exact counts do not rely on hashes.
Cleaning may merge records differing only in invalid measurements; this further
conservatively groups them. No fitting, imputation, normalization, or clipping is
performed. Labels are preserved verbatim. Duplicate-weighted metrics should be
reported alongside unique-observation-group metrics during evaluation.

## Suspected or unresolved risks

Within-day session/scenario confounding, almost-identical flows, collection artifacts and
possible shared hosts remain unresolved. Recovered file/day metadata supports a
coarse temporal stress test but does not restore fine-grained session independence.
There is no brute-force near-duplicate
search. Correlated duration/rate/length statistics can reflect genuine behavior;
correlation alone is not evidence of leakage. Fwd/subflow and segment-size aliases
are redundant measures, not inherently leaked targets. Per-class candidate
distributions are descriptive and do not prove operational generalization.

## Evaluation recommendation

Use the saved deterministic 70/15/15 observation-group partition as a provisional
development split. Realized sizes vary; rare classes may be absent from a partition.
Tune membership functions and rule weights only on train; choose model decisions
with validation and reserve test. Full-data exploratory summaries have been viewed:
the test set is not a fully blind external holdout. In addition, use the recovered
day manifest for a stricter temporal stress test: Monday/Tuesday/Wednesday train,
Thursday validation, Friday test. Entire groups occurring in multiple nominal
partitions are quarantined, preventing exact overlap without moving future records
into train. See temporal_partitions.csv and temporal_classes.csv for actual sizes
and class coverage. Attack classes differ across days; this tests novel scenarios
and cannot support ordinary stratified multiclass comparisons. Membership fitting
must respect whichever manifest is chosen. Prefer a separately sourced,
host/session-aware external evaluation when authorized data becomes available.
Do not claim leakage-free or independent evaluation from the current metadata.
No severity truth exists; traffic detection agreement and expert-reviewed risk
explanations are different evaluation objectives.
