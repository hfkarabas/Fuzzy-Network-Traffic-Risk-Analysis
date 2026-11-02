# Dataset methodology and execution constraints

TASK 01 is a data foundation, not a classification experiment. All technical
reports are English. No remote Git synchronization is used; downloading the public
dataset through Hugging Face is separate from Git operations.

The source is preserved in a repository-local HF cache. CSV imports contain
leading spaces in column names; preserving these avoids silently changing the
schema. Original numerical types are in provenance/schema reports. Cleaned numeric
features use float64 for nullable compatibility and vectorized computation; source
integer ranges fit exact float64 representation in this verified snapshot.

Baseline statistical profiling includes finite negative values to expose issues.
Cleaned output nulls all negatives as unavailable measurements, including initial
window sentinels. Thus negative-value counts must not be described as counts of
confirmed corrupted network flows. Nulls outside the chosen five inputs do not
exclude a row from fuzzy-ready output. Full source class counts remain unchanged
in the cleaned dataset, while eligibility filtering can slightly alter fuzzy-ready
class proportions. No source rows or labels are relabeled or dropped from cleaned data.

Duplicate equality is evaluated over all raw columns in SQL. Observation equality
ignores the target. A cryptographic integrity hash protects files; separate stable
64-bit row hashes are used only to form conservative evaluation groups. A row-hash
collision would group extra observations together, never cause identical
observations to cross partitions. Nulling invalid values can also conservatively
merge observations. Future group-weighted metrics should accompany row metrics.

Development sampling is uniform by deterministic row-ID hash priority within each
label/partition, capped at 700/150/150. It intentionally is not representative of
source prevalence. All eligible observations in sufficiently rare strata survive.
Rare classes have very small evaluation counts even after preserving them, so
class-specific estimates will have substantial uncertainty.

Full-data EDA informs feature selection; the current test split is not a blind
external holdout. Membership thresholds and any later transformation must be fitted
on train only. Current correlation findings justify replacing duration with forward
volume and binary SYN context with directional ratio. No trained classifier,
neural network, fuzzy inference engine or web framework is included.

Execution issues resolved: venv ensurepip initially failed due Windows temporary
folder permissions; the global pip launcher populated only the local venv instead.
Network-restricted dependency/acquisition commands required execution outside that
sandbox. Console encoding could not print source replacement characters, resolved
with PYTHONUTF8=1. Two temporary-file unit tests initially hit Windows sandbox
permissions and were rerun successfully with local temporary paths and appropriate
execution access. None required a source substitute or manual dataset download.

Resource estimate before processing: source metadata indicated roughly 1 GB CSV
plus 1.8 GB Arrow, within the observed 262 GB free disk. DuckDB exact grouping was
limited to 1 GB with disk spill. Quantiles and finite-value unique counts are
computed one feature at a time; complete frames are never converted to pandas.
Only compact candidate columns, batches, and capped sample reservoirs are materialized.

The initial processing pass completed source profiling and exports before its
reporting module was available. A final processing pass was justified by measured
redundancy changing the selected feature schema; full-output validation then checked
the final artifacts. Final reports contain the final measurements only.

Source-day provenance was recovered from the eight cached source CSV filenames,
then verified against every original feature value and label in the datasets-loaded
table. source_sessions.parquet provides a separate temporal manifest: Monday to
Wednesday train, Thursday validation, Friday test. Entire observation groups
spanning nominal partitions are quarantined, without moving future records into
training or removing rows from the cleaned output. This provides an additional
stress test with substantial attack-category shift; it does not recover exact
timestamps, host independence or within-day sessions.
