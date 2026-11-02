# Preprocessing report (v1)

Baseline profiling preceded cleaning. A 1,000-row pilot checked label preservation
and numeric dtype consistency before processing the full source in 65,536-row batches.
No GPU or fitted estimator is used. Original source files remain unchanged in the
Hugging Face cache; integrity hashes are checked separately by validate_outputs.py.

## Cleaning rules and accounting

1. Parse expected numerical fields; malformed/non-numeric values become null.
2. Replace NaN, positive/negative infinity and negative numerical measurements with null.
   This includes negative unknown window sentinels. No imputation or clipping.
3. Preserve all labels verbatim, all original features, zeros and large finite values.
4. Retain duplicates; identify observations ignoring labels and assign group partitions.
5. Add source row ID, observation group ID, partition and fuzzy eligibility metadata.
6. Export fuzzy-ready rows only when all five inputs and the label are available.

Cleaned rows: **2,830,743**; excluded cleaned rows:
**0**. Fuzzy-ready rows:
**2,827,761**; unavailable-input rows excluded from fuzzy-ready:
**2,982**. Exclusions are not claims of corrupted flows.
Invalid measurements outside the input set do not make a row fuzzy-ineligible.
Numerical features are uniformly float64; labels remain strings, source IDs int64,
group IDs uint64, eligibility boolean. Per-feature null counts (overlapping cells):

| feature | nulled_cells |
| --- | --- |
| " Flow Duration" | 115 |
| "Flow Bytes/s" | 2952 |
| " Flow Packets/s" | 2982 |
| " Flow IAT Mean" | 115 |
| " Flow IAT Max" | 115 |
| " Flow IAT Min" | 2891 |
| " Fwd IAT Min" | 17 |
| " Fwd Header Length" | 35 |
| " Bwd Header Length" | 22 |
| " Fwd Header Length.1" | 35 |
| "Init_Win_bytes_forward" | 1001189 |
| " Init_Win_bytes_backward" | 1441552 |
| " min_seg_size_forward" | 35 |

## Outputs (local, ignored by Git)

- `data/processed/v1/cleaned.parquet`: all source rows and original columns plus metadata.
- `data/processed/v1/fuzzy_ready.parquet`: five inputs plus label and row/group/partition metadata.
- `data/processed/v1/split_manifest.parquet`: every source row and its eligibility/group partition.
- `data/samples/development_v1.parquet`: 11,720 eligible observations.
- `data/processed/v1/source_sessions.parquet`: recovered CSV filename/day and coarse
  temporal partitions, joined by source_row_id. Entire cross-day-partition duplicate
  groups are quarantined from this alternative evaluation protocol.

Full eligible partition sizes: {'train': 1986854, 'validation': 418018, 'test': 422889}.
Groups crossing partitions: **0**.
Hash grouping is conservative, not a guarantee of independent sessions.

## Sampling and reproducibility

Seed: 20261103. Version v1, fixed source revision in provenance.json,
locked dependencies in requirements.txt. Source order defines stable source_row_id.
Observation-group hash mixing assigns approximately 70/15/15 train/validation/test.
The development reservoir chooses the lowest deterministic pseudorandom row-ID
hashes within each label and partition, capped at 700/150/150 (1,000 per class).
All eligible members of rare strata below those caps are retained. Full source
class proportions are retained in cleaned output; the development set deliberately
overrepresents rare categories and is NOT distribution-preserving. See
development_classes.csv for actual label/partition counts. Sampling within saved
partitions cannot introduce duplicate leakage across them. Duplicates can consume
multiple sample positions; report group-weighted metrics as well as row metrics.

## Validation

Full pipeline assertions verified row accounting, Parquet footer counts, finite
nonnegative fuzzy inputs and zero group crossings. Unit tests use synthetic data
without network/download dependencies; validation.json and test_results.txt record
actual additional checks and pytest output. requirements.txt pins the executed
environment. Full observed processing elapsed time: 56.65 seconds.
Output byte counts: {'cleaned.parquet': 330985606, 'fuzzy_ready.parquet': 64002527, 'split_manifest.parquet': 25281264}.
Rerunning overwrites only versioned generated outputs, not the HF cache/source.

## Verified source provenance and temporal stress test

Coarse capture-day/file provenance was recovered from the eight
original downloaded CSVs. Every numerical value and label was matched exactly
against all 2,830,743 rows of the datasets-loaded table.
See source_files.csv, session_recovery.json and the local source_sessions.parquet
manifest. No alternative data source was acquired. Original row order is alphabetical
by file, NOT chronological. Fine-grained timestamps, hosts and flow sessions remain unavailable.

| temporal_partition | rows | fuzzy_eligible_rows |
| --- | --- | --- |
| quarantine | 132348 | 131745.0 |
| test | 667094 | 666572.0 |
| train | 1608690 | 1607145.0 |
| validation | 422611 | 422299.0 |

Temporal eligibility counts use the same five-input policy. Quarantine applies only to this alternative manifest; no rows are deleted from cleaned or fuzzy-ready data. All nonquarantined observation groups remain in one temporal partition.
