# TASK 09C — Dataset Information

Added the seventh bilingual route, `#dataset`, with the existing sidebar, language
switcher, dark theme and responsive navigation. The original six routes remain
operational; academic branding and large disclaimer panels were not restored.

## Content and sources

- Overview/class distribution: existing model metadata, source revision and
  `reports/dataset/classes.csv` (2,830,743 records, 79 columns including the label,
  15 labels). Source category names, including original encoding artifacts, remain
  verbatim. The source Hugging Face repository is linked.
- Preparation/quality: `preprocessing.json`, `quality.json` and the existing lineage
  report. Distinguishes cleaned rows, fuzzy eligibility, overlapping quality counts,
  retained duplicates, initial partitions and later exposure-linked exclusions.
- Architecture: actual five feature identifiers/transforms, configured memberships,
  22 rules, min/max operators and 201-point centroid. Reuses MembershipChart for
  all five inputs and explicitly identifies the model as rule-based Mamdani,
  not a conventionally trained classifier.
- Development: original/refit/rule refinements and flat/hierarchical/behavior
  alternatives, using existing API comparison data and the committed architecture
  comparison CSV. The failed day-stability gate and retained production selection
  are stated without claiming independent improvement.
- Calibration: active API thresholds and the selected policy artifact's FPR targets,
  calibration FPR/recall, role and model-identity check. Full precision is retained.
- Evaluation/limits: real historical metrics, group-weighted versus raw-flow scope,
  adaptive reuse, class imbalance, day shift, live-feature compatibility and lack
  of independently established live attack-detection accuracy.

Detailed recorded model comparisons moved from Model Performance to the new page.
Performance keeps its indicators, confusion matrix and concise interpretation scope,
with a link to the detailed information. No large explanatory blocks were duplicated.

## Validation and boundaries

Frontend suite: **46 passed, zero failed** (two new source-backed page tests plus
existing route/localization regressions). TypeScript and Vite build each passed
once. Only failed frontend checks were rerun: Vite 8 required both physical and
`?raw` IDs for the external CSV summaries. The development server now permits
exactly six small committed artifacts plus the two corresponding CSV query IDs;
it does not allow the repository root, dataset archives or caches.

Changed: `web/src/DatasetInformation.tsx`, its test, `App.tsx`, `App.test.tsx`,
`i18n/messages.ts`, `i18n/localization.test.tsx`, `styles.css`, `web/vite.config.ts`
and this report. No dependency, launcher, backend/inference, model/rule/policy,
capture, dataset/LFS, historical fixture, evaluation result or prior report changed.
No dataset processing, backend suite, training or optimization was run. No remote
Git operation occurred.

Remaining limits: native browser screenshots were not taken. Information reflects
committed summaries and existing API metadata, not a newly executed evaluation.
Existing source/exporter/generalization limitations remain explicit on the page.
The local commit hash and final working-tree status are in the final response.
