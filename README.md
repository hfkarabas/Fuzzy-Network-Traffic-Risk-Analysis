# Fuzzy Logic-Based Network Traffic Risk Analysis

A university Fuzzy Logic project: numerical network-flow characteristics will feed
interpretable membership functions and IF–THEN rules to produce a 0–100 risk score,
Low/Medium/High/Critical categories and explanations. The fuzzy inference engine is
the central planned algorithm. No conventional classifier, fuzzy engine or web UI
has been implemented in TASK 01.

Dataset: [c01dsnap/CIC-IDS2017](https://huggingface.co/datasets/c01dsnap/CIC-IDS2017).
Verified source: **2,830,743 records, 79 columns, one train split, 15 labels**.
TASK 01 supplies full-data profiling, cleaning, a five-input fuzzy-ready export,
grouped evaluation manifests, a development sample and synthetic unit tests.

## Layout

- `config/dataset.yaml`: source revision, seed, batches and exact input names.
- `src/fuzzy_network_risk/data.py`: pure validation, cleaning, grouping and sampling rules.
- `scripts/`: acquisition, analysis, preparation, reports and full-output validation.
- `tests/`: synthetic, offline tests.
- `reports/dataset/`: versioned English reports and compact CSV/JSON measurements.
- `reports/figures/`: generated charts, ignored by Git.
- `data/processed/v1/`: generated cleaned/fuzzy-ready/manifest Parquet files.
- `data/samples/`: generated small development dataset.
- `data/processed/v1/source_sessions.parquet`: verified source file/day mapping and
  an alternative day-based evaluation manifest with duplicate-group quarantine.
- `.cache/huggingface/`: original HF downloads and Arrow cache; no redundant raw copy.
- `docs/`: methodology notes. A future web directory will be added with the UI.

## Environment

Python >=3.12 is required. This run used the only installed interpreter, Python
3.14, on Windows. requirements.txt pins the complete executed environment;
compatible wheels on other platforms/Python versions may differ. No GPU is needed.
DuckDB provides memory-limited exact duplicate grouping with disk spill; pandas
and NumPy handle small-column profiles/batches, PyArrow handles Parquet, matplotlib
produces four focused figures, and pytest validates synthetic fixtures.

```powershell
# From this repository, use Python 3.12 if available, otherwise the installed compatible Python.
./scripts/setup.ps1
# Alternative conventional setup:
# py -m venv .venv
# ./.venv/Scripts/python -m pip install -r requirements.txt
```

The setup script uses the installed launcher's pip to populate `.venv` and places
temporary files inside the repository. This avoids environment-specific Windows
temp permissions encountered during this task. Normal tests do not access the network.

## Acquisition and preparation

```powershell
$env:PYTHONUTF8 = '1'
./.venv/Scripts/python scripts/acquire.py
# The primary acquisition method is exactly:
# from datasets import load_dataset
# ds = load_dataset("c01dsnap/CIC-IDS2017")
```

HF_HOME and HF_DATASETS_CACHE are set by acquire.py before importing datasets, so
the original downloads and Arrow cache stay inside this repository. Authentication
is not required for this public dataset. Large files are ignored by Git.

For the recorded source revision on a fresh machine:

```powershell
$env:DATASET_REVISION = '4e9edfa727f800b6f595bc2ee7420527156562b2'
./.venv/Scripts/python scripts/acquire.py
# Record only on first acquisition; the script refuses to replace a baseline.
# A checked-in baseline already exists; validate it if cache paths match.
./.venv/Scripts/python scripts/cache_integrity.py
./.venv/Scripts/python scripts/prepare.py
./.venv/Scripts/python scripts/validate_outputs.py
```

The mandated unpinned call was executed for initial acquisition. DATASET_REVISION
optionally enables pinned replay; preparation refuses a revision differing from
config. The integrity manifest uses relative paths and SHA256; it covers source
blobs and Arrow shards, not mutable locks or metadata files. Hugging Face may change
cache layout between library versions; review the provenance rather than silently
replacing the baseline. The original CSV blob hashes are independently checked
against their SHA256 cache names. Acquisition may require about 4 GB peak disk for
raw CSV + Arrow + generated outputs and temporary duplicate grouping; allow at
least 8 GB free disk for headroom. Profiling materializes one numeric column at a
time; candidate correlation holds only 5–10 columns. DuckDB is capped at 1 GB, but
Python/Arrow allocations are additional. Memory availability could not be queried
through Windows CIM in the execution sandbox; avoid concurrent heavy processes.

To reuse the acquired cache without network access:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:HF_DATASETS_OFFLINE = '1'
./.venv/Scripts/python scripts/prepare.py
./.venv/Scripts/python scripts/validate_outputs.py
```

Preparation overwrites generated v1 outputs only. It preserves exact original
column names, including leading spaces. All original features remain in cleaned
data; fuzzy-ready data selects five inputs and evaluation metadata. Invalid values
become null; no imputation, winsorization or model fitting is performed. Duplicate
rows remain, with conservative group partitions. The development sample is capped
per class/partition, intentionally overrepresenting rare attacks.

## Tests and reports

```powershell
./.venv/Scripts/python -m pytest -q
# If Windows temporary directory permissions are restricted:
./.venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=.tmp/pytest-local
```

Full-output validation checks every cleaned numerical value and label against the
cached source, recomputes group IDs/partitions, checks fuzzy/sample/manifests and
verifies source integrity. See:

- [Dataset profile](reports/dataset/dataset_profile.md)
- [Data quality and leakage](reports/dataset/data_quality_and_leakage.md)
- [Fuzzy feature selection](reports/dataset/fuzzy_feature_selection.md)
- [Preprocessing report](reports/dataset/preprocessing_report.md)
- [Validation results](reports/dataset/validation.json)

## TASK 02

Use train rows of development_v1.parquet to design overlapping linguistic sets
and interpretable rules; use validation for decisions and reserve test for final
checks. Exact inputs are in config; labels and metadata must never enter inference.
Keep risk severity distinct from attack labels. Decide how unavailable inputs
produce an explanation/abstention and how to validate risk scores without severity
ground truth. Implement and test the fuzzy engine before building the local web UI.
Current partitions prevent identical cleaned observations crossing, but unavailable
fine-grained session metadata and near-duplicate flows prevent claims of independent
evaluation. Original CSV file/day origins were recovered with exact verification
against every source row. Use source_sessions.parquet for a stricter temporal stress
test: Monday–Wednesday train, Thursday validation, Friday test. All duplicate groups
spanning nominal temporal partitions are quarantined in that alternative manifest.
Attack categories differ across days, so report class coverage and unseen-category
limitations alongside the class-preserving development evaluation.
