# TASK02B reproducibility and integration

The result is a negative refinement finding: retain the unchanged TASK02 scoring
model. New policies make the recall/FPR tradeoff explicit; they do not improve the
underlying fuzzy ranking. All reported new comparison results are internal validation.

## Evidence and data lineage

Read reports/fuzzy/evaluation_integrity.md before interpreting metrics. Exclusion
signatures are built without exposed labels, scores or errors. All Friday rows and
the old grouped-test records are blocked, along with their original groups and
coarse selected-input signatures. The remaining 297,916 quality-eligible flows are
strongly selected relative to the original source. The bounded sample is uniform
by source-row hash rather than balanced by class. Original provenance is retained.

The 14,042-row design panel is separate from the 45,958-row rotating comparison
panel. In each of three rotations, membership fitting, policy calibration and
assessment use distinct signature groups. Old baseline fitting/EDA means there is
no credible untouched independent holdout. A_frozen is a contextual warm baseline;
A_refit is the training-role-pure comparator for rule/membership improvements.

## Run commands (repository root, existing virtual environment)

```powershell
$env:PYTHONUTF8 = '1'
./.venv/Scripts/python scripts/task02b_integrity.py
./.venv/Scripts/python scripts/task02b_prepare.py
./.venv/Scripts/python scripts/task02b_diagnostics.py
# The candidate plan already exists and is immutable. Do not replace it.
# First-time registration on a new experiment version only:
# ./.venv/Scripts/python scripts/task02b_experiment.py freeze
./.venv/Scripts/python scripts/task02b_experiment.py compare
./.venv/Scripts/python scripts/task02b_experiment.py finalize
./.venv/Scripts/python scripts/task02b_validate.py
./.venv/Scripts/python scripts/task02b_reports.py
./.venv/Scripts/python scripts/task02b_integrity.py
```

Ordinary synthetic tests need no data download:

```powershell
./.venv/Scripts/python -m pytest -q
# For Windows temporary-path restrictions:
./.venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=.tmp/pytest-local
```

Replaying regenerates only TASK02B outputs; it does not rerun the old exposed test
scripts. Do not invoke run_fuzzy.py all for this task. The candidate plan contains
byte-exact code hashes and intentionally stops on changed source. Preserve the
recorded source version/line endings, or create a distinct registered experiment
after auditing a source change. Model hashes use canonical JSON and are independent
of whitespace. Deterministic scores/partitions/selection reproduce; timings vary.
Tests and validation reports are retained from actual executions. No dependencies
beyond the existing requirements were added.

## Selected model and alert-policy API

```python
from fuzzy_network_risk.policy import PolicyRiskModel

model = PolicyRiskModel.load(
    "config/fuzzy/task02b/selected_v2.json",
    "config/fuzzy/task02b/selected_policies.json",
    policy="Balanced",
)
record = {
    " Flow Packets/s": 100000.0,
    " Total Fwd Packets": 100.0,
    " Packet Length Mean": 6.0,
    " Bwd Packet Length Std": 0.0,
    " Down/Up Ratio": 0.0,
}
result = model.predict_one(record)
batch = model.predict_batch([record, record])
```

Set PYTHONPATH=src or import from the installed project environment. All five exact
names, membership evidence, risk categories, rule identifiers and abstention rules
remain compatible with TASK02. The scoring model is copied verbatim: its model ID
and embedded historical alert threshold 25 remain unchanged. PolicyRiskModel
explicitly overrides only the binary alert using a separately frozen threshold and
includes policy identity/name/estimated FPR target. Calling the raw engine directly
still uses threshold 25 and does not apply the new selected policy.

Sensitive/Balanced/Conservative thresholds are approximately 49.6325/51.8092/59.4659.
Their 10%/5%/1% calibration FPR targets are estimates, not promises. The FPR
targets are signature-group-weighted, not per-flow: Balanced internal pooled raw-row
FPR is about 15.71%, versus a mean group-weighted FPR of 4.91%. Keep both visible.
The risk-category
boundaries remain 25/50/75 and are independent of alert policies. Missing/invalid
inputs yield null score/category/alert; unavailable batch scores remain NaN internally.
Only the approved five inputs are accepted; labels and provenance are never inputs.

## Educational UI recommendation

Load the frozen model and policy once in a local backend; validate five numerical
inputs; call PolicyRiskModel; render structured evidence through an English message
catalog. Keep scores separate from alert policy controls. Show missing-data status,
model/policy IDs and the documented weak detection performance. No model fitting
or threshold optimization should occur in a request handler. Stream outer batches
for files; the centroid workspace is bounded internally. No web framework or UI
was added during TASK02B.

## Artifacts

Versioned: protocol, candidate/source freeze, 12 fold configurations, selected model
copy, policy configurations, numeric summaries, tests and five explanation examples.
Ignored: source/eligible/sample manifests, 60,000-row development data, saved OOF
predictions, complete calibration curves and figures. Existing TASK01/TASK02 files
and predictions are protected by a separate historical-integrity manifest. None of
the negative candidate results or original baseline metrics are deleted.
