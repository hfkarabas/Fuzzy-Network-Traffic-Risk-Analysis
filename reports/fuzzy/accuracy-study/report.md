# Fuzzy model accuracy study

The existing five-input Mamdani model remains the deployment choice. The hierarchy achieved 93.51% raw accuracy in reused grouped development under thresholds optimized for raw accuracy. Its group-weighted attack recall was 26.76%. A threshold calibrated for balanced accuracy raised its group-weighted recall to 30.30%, with 0.97% FPR, but the hierarchy detected no attacks in the three internal day exclusions at that operating point.

## Protocol

The study verified the historical TASK05 development cache against its registered SHA-256 and excluded the design bucket. It checked for overlaps with the prior exposure manifest using source row IDs, observation group IDs and coarse signatures. The assessment panel contained 45,958 flows, with 39,159 benign and 6,799 attack rows. Three assessment folds used separate training and threshold calibration buckets. The day stress procedure excluded the selected day's signatures and original observation groups from the remaining data before splitting it into training and calibration. Previous grouped test and Friday test observations were excluded. The panel was already used in development, and the frozen model overlaps historical training evidence. No independent test set was available.

Four predictors ran on the same data: the frozen production model, a fold-local five-input refit, its fold-local weighted version, and the existing TASK05 hierarchy refit within each split. The weighted model attenuates a rule only when the difference in mean activation between the two classes runs opposite to the rule's consequence. Low and High/Critical consequences have opposite signs, Medium retains weight one, and weights are bounded between 0.5 and 1. Each class mean uses inverse signature counts. This keeps the fitted memberships, antecedents and consequents of the fold-local refit. Labels are used for training weights and threshold calibration and are excluded from prediction inputs.

The `raw` policy maximizes raw accuracy over distinct calibration score thresholds, including a no-alert operating point. The `balanced` policy maximizes group-weighted balanced accuracy with a 10% calibration FPR cap. Both break ties by lower FPR and then higher threshold. The established application policy is evaluated separately. Research thresholds vary by split.

## Grouped internal assessment

| Model / operating point | Pooled raw accuracy | Group balanced accuracy | Group recall | Group FPR | Raw TN / FP / FN / TP |
|---|---:|---:|---:|---:|---|
| Always benign | 85.21% | 50.00% | 0.00% | 0.00% | 39159 / 0 / 6799 / 0 |
| Frozen / deployed default | 74.87% | 58.10% | 21.03% | 4.83% | 33031 / 6128 / 5420 / 1379 |
| Frozen / raw | 85.46% | 51.26% | 2.59% | 0.07% | 39134 / 25 / 6656 / 143 |
| Frozen / balanced | 73.70% | 59.12% | 24.65% | 6.40% | 32338 / 6821 / 5264 / 1535 |
| Refit / balanced | 74.96% | 52.96% | 13.63% | 7.71% | 33458 / 5701 / 5809 / 990 |
| Weighted / balanced | 74.78% | 53.21% | 14.43% | 8.00% | 33345 / 5814 / 5776 / 1023 |
| Hierarchy / raw | 93.51% | 63.33% | 26.76% | 0.10% | 39134 / 25 / 2959 / 3840 |
| Hierarchy / balanced | 93.15% | 64.67% | 30.30% | 0.97% | 38888 / 271 / 2875 / 3924 |

Group metrics are means of three signature-weighted folds. Pooled accuracy and confusion counts use raw flow rows. For example, the hierarchy's raw policy detects 3,840 out of 6,799 attack rows (56.48% raw recall), with 26.76% group-weighted recall. The two aggregations answer different questions. The frozen model's raw-accuracy calibration adds 10.59 percentage points of accuracy over the deployed default and loses 18.44 points of group recall.

Weighting improved the fold-local refit's ROC-AUC from 0.6056 to 0.6187 and group recall by 0.80 points under the balanced policy. It remained below the frozen model's ROC-AUC of 0.6383 and did not meet the practical gain criterion of five points of recall plus positive balanced accuracy gain against both controls. The hierarchy's balanced recall ranged from 28.22% to 33.43% across the three grouped folds. This within-panel stability did not extend across capture days.

## Day stress at the balanced research threshold

| Excluded capture day | Attack rows | Frozen recall / FPR | Clean refit recall / FPR | Weighted recall / FPR | Hierarchy recall / FPR |
|---|---:|---:|---:|---:|---:|
| Tuesday | 149 | 43.36% / 9.53% | 34.86% / 3.16% | 49.02% / 14.06% | 0.00% / 0.74% |
| Wednesday | 6640 | 20.64% / 3.01% | 7.67% / 8.20% | 8.74% / 9.07% | 0.00% / 0.00% |
| Thursday | 10 | 0.00% / 6.55% | 0.00% / 6.76% | 0.00% / 6.74% | 0.00% / 0.36% |

The weighted model also failed the day criterion of at most 10% FPR and recall of at least 5% or within two percentage points of the clean refit, whichever is higher. Thursday has only ten positive rows and gives limited evidence about that day's broader attack behavior. These tests are internal stress experiments on previously used records. The next useful evidence for training or promotion is an independently collected, labeled capture with separate sessions for fit, calibration and evaluation.

## Reproduce

Use the existing research environment and the registered TASK05 cache and exposure manifest. The command refuses to overwrite a report.

```powershell
.\.venv\Scripts\python.exe scripts/research/accuracy_study.py --output .tmp/accuracy-reproduction.json
```

[Machine-readable results](metrics.json) contain split counts, thresholds, raw and weighted metrics, file hashes and each fitted weighted configuration.

An independent rerun produced a byte-identical JSON result. The related advanced, refinement and optimization test files yielded 72 passes and three failures. The failures reference missing historical files `reports/fuzzy/metrics.json` and `reports/fuzzy/task05/partition_audit.json` in the current checkout.
