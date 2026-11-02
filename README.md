# Fuzzy Logic-Based Network Traffic Risk Analysis

A university Fuzzy Logic project: numerical network-flow characteristics will feed
interpretable membership functions and IF–THEN rules to produce a 0–100 risk score,
Low/Medium/High/Critical categories and explanations. The fuzzy inference engine is
the central algorithm. TASK 02 implements a working, explainable Mamdani engine.
No conventional classifier, neural network or web UI is included.

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

## Fuzzy engine (TASK 02 complete)

The five-input Mamdani system uses 22 hand-written rules, minimum AND/implication,
maximum OR/aggregation and centroid defuzzification. Three overlapping memberships
per input are derived from the appropriate training partition. Rate, volume and
response variation use log1p; size and directional ratio retain physical coordinates.
Separate frozen configurations represent grouped-development and day-based protocols.

Risk categories are Low [0,25), Medium [25,50), High [50,75), Critical [75,100].
Binary alerts use a separate validation-selected threshold: 25 grouped, 75 day.
Invalid or missing input produces explicit abstention; no silent zero substitution.
Scores express behavioral rule output, not attack probability or calibrated severity.

```powershell
# Offline single-record CLI; preserves exact column names including leading spaces.
./.venv/Scripts/python scripts/score_flow.py --input config/fuzzy/example_flow.json
# Standalone numerical validation and source/output integrity checks:
./.venv/Scripts/python scripts/validate_fuzzy.py
./.venv/Scripts/python scripts/task02_integrity.py
# Complete experiment replay, using existing TASK 01 outputs (no download):
./.venv/Scripts/python scripts/run_fuzzy.py all
```

Replay refits from training, calibrates only six alert thresholds on validation,
freezes JSON configurations, evaluates each test once, validates numerical behavior
on training records and regenerates reports/figures. Individual `fit`, `evaluate`
and `report` phases are also supported. Scores/parameters are deterministic; wall
timings can vary. `report` reuses saved predictions and does not refit or rescore
the complete test set. No test-driven parameter search is performed.

Python API (run with `PYTHONPATH=src`, or from an installed package):

```python
from fuzzy_network_risk.engine import MamdaniRiskEngine
engine = MamdaniRiskEngine.load("config/fuzzy/grouped_v1.json")
record = {" Flow Packets/s": 100000.0, " Total Fwd Packets": 100.0,
          " Packet Length Mean": 6.0, " Bwd Packet Length Std": 0.0,
          " Down/Up Ratio": 0.0}
prediction = engine.predict_one(record)
batch = engine.predict_batch([record, record])
```

Only these five columns are accepted; explicitly select them from labeled frames.
For large files, stream outer batches (the evaluation script uses 8,192 rows).
The centroid workspace is capped internally at 2,048 rows by default. Structured
membership/rule strengths, consequents and translation keys support a future
Turkish interface; English explanation text is separate. See [API details](docs/fuzzy_api.md).

Actual evaluation exposes major detection weaknesses: grouped test recall 88.75%
but false-positive rate 76%; day test recall 0.00626% at the frozen threshold 75.
These are unsuitable operational alert settings. The engine is ready for an
educational local UI integration, with those limitations visible. Do not present
high grouped F1 as real-world detection effectiveness: its test is 91.43% attack.

- [System design](reports/fuzzy/fuzzy_system_design.md)
- [Rule analysis](reports/fuzzy/rule_base_analysis.md)
- [Model evaluation](reports/fuzzy/model_evaluation.md)
- [Error analysis](reports/fuzzy/error_analysis.md)
- [Machine-readable metrics](reports/fuzzy/metrics.json)

Original source and TASK 01 outputs/reports are SHA256-protected and unchanged.
Generated predictions live in ignored `data/fuzzy_v1/`, with figures in ignored
`reports/figures/fuzzy/`. Small model configurations, metrics, test results and
deterministic error examples are versioned. No extra dependencies were required.

## TASK 03

Integrate the engine into a local web interface with validated physical-unit inputs,
explicit invalid-input status, model identity, score/category, rule evidence and
measurement caveats. Zero integer direction ratio does not imply no responses.
Full-original-feature groups are disjoint across partitions, but selected-input
patterns can overlap; within-day sessions, near-duplicates and category shift
remain concerns. The current tests have now been examined. Any future scientific
rule revision must use training/validation and a newly reserved final evaluation,
rather than optimizing repeatedly against the reported test results.
