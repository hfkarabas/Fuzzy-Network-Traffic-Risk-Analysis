# TASK02B final engineering decision

**No scoring-model improvement was supported. Retain the TASK02 baseline.**

## Delivered work

Audited exposure and model lineage; excluded 2,529,845 exposed or
coarse-linked flows; established a 297,916-flow eligible population;
sampled 60,000 without class balancing; separated 14,042 design rows from 45,958
rotating internal validation rows. Compared the original frozen model, a fair
fold-refitted baseline, benign-reference memberships and an 18-rule refinement.
No extra feature was justified. All unfavorable results and old baseline artifacts
are retained. No old test records were rescored or used for refinement/selection.

## Final integration artifacts

- config/fuzzy/task02b/selected_v2.json: verbatim retained scoring model, v1 model
  identity ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b.
- config/fuzzy/task02b/selected_policies.json: frozen Sensitive/Balanced/Conservative
  operating thresholds with explicit calibration FPR targets, not guarantees.
- config/fuzzy/task02b/selected_manifest.json: candidate, versioned source hashes,
  22 rules / five inputs / internal-evidence status.
- src/fuzzy_network_risk/policy.py: PolicyRiskModel applies the selected operating
  policy without changing risk score, category, memberships or rule evidence.

The wrapper must be used for v2 policy alerts. Raw engine.predict_one retains the
historical embedded threshold 25 for strict TASK02 compatibility. No category cuts,
consequents or score parameters are silently changed. Stable explanation keys
and the complete activated-rule evidence remain available. Real eligible-design
examples of all four categories plus explicit invalid-input abstention are in
explanation_examples.json; synthetic robustness workloads are labeled as such.
The three FPR targets are signature-group-weighted. Balanced pooled raw-row FPR
is about 15.71%, not 5%; group and row rates measure different distributions.

## Main internal findings

| candidate | precision | recall | f1 | false_positive_rate | false_negative_rate | balanced_accuracy | roc_auc | pr_auc_average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A_frozen | 0.174595 | 0.210755 | 0.190959 | 0.049102 | 0.789245 | 0.580827 | 0.638296 | 0.11837 |
| A_refit | 0.095352 | 0.100406 | 0.097783 | 0.047568 | 0.899594 | 0.526419 | 0.605639 | 0.069478 |
| B_membership | 0.067745 | 0.071878 | 0.069656 | 0.047957 | 0.928122 | 0.51196 | 0.636173 | 0.071958 |
| C_rules | 0.011205 | 0.009521 | 0.010237 | 0.027991 | 0.990479 | 0.490765 | 0.692035 | 0.083236 |

These are internal model-selection measurements, not final-test performance. Warm
baseline fit overlap, severe population exclusions, limited scenario coverage,
rare categories, within-day dependencies and coarse-bin boundary effects remain.
The new policies make low-FPR tradeoffs explicit but miss many attacks. Neither
probability calibration, calibrated severity nor production readiness is established.

## Robustness and execution evidence

All candidate configurations and source freezes validate. All 36 policy metrics
were reproduced from saved predictions. Single/batch scores match bitwise.
Robustness covers valid zeros, huge finite values, sparse flows, benign-like bulk
workloads, direction imbalance, small-packet bursts, invalid/missing/infinite input,
near-boundary and small-perturbation measurements. Invalid cases abstain; no zero
imputation. +/-0.1% input changes have maximum observed score change under 0.15;
15 near-anchor checks at two-parts-per-million have maximum change
0.00005177. This is bounded empirical
robustness, not a proof over all possible traffic. Membership coordinate uncertainty
has larger effects and remains documented.

Measured selected-model inference: 160267 rows/s
for 14,042 design flows in 0.087616 seconds,
CPU only, excluding disk IO and diagnostics. A centroid workspace is 3,293,184 bytes;
multiple temporaries add to this, with outer batches recommended for large files.
DuckDB is capped at 1 GB, desktop memory budget approximately 16 GB. No dataset
download, GPU, conventional ML classifier or neural network was used.

## Tests and preservation

........................................................................ [ 79%]
...................                                                      [100%]
91 passed in 1.24s

Historical artifact hashes are checked by scripts/task02b_integrity.py; source
datasets, TASK01 outputs, TASK02 configs/reports/scripts/tests and existing prediction
Parquet files are unchanged. New Parquet/sample/candidate-curve artifacts stay in ignored
data/fuzzy_v2; the full design threshold curve is separately ignored under reports.
Figures stay in ignored reports/figures/task02b. Small configurations,
numeric summaries, reports, tests and 5 representative explanations are versioned.
The selected configuration was copied, not overwritten in its original location.
No remote Git operation is part of this workflow.

## TASK03 readiness

Ready for an educational local UI using PolicyRiskModel, explicit policy selection,
the five exact physical-unit inputs, model/policy IDs, categories, complete fuzzy
evidence, translation keys and invalid-input states. Show that target FPR is a
calibration estimate and many attacks are missed. Do not silently present an
educational score as a trusted attack detector. No web interface was built here.
Future scientific revision requires new training-only hypotheses and a genuinely
new authorized capture/holdout; repeatedly tuning against the exposed Friday or
old grouped tests remains prohibited.
