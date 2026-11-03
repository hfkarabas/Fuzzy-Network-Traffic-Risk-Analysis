# TASK05 final engineering decision

**Keep production unchanged. C_hierarchy is a promising research candidate, not a promoted model.**

Implemented and executed a systematic78-column audit, expanded eight-input flat Mamdani, four-module hierarchy and three behavior-module hierarchy. Original/refitted baselines are preserved. Exact features, membership parameters, rule rationales, intermediate outputs, configs, policy thresholds and actual metrics are versioned. No classifier, probability model or arbitrary score averaging was introduced.

C_hierarchy has the highest internal Balanced recall31.66% versus frozen21.08%, with FPR4.53% versus4.91%. D_behavior reaches30.18% recall/FPR3.57% with fewer rules. Both show positive conditional group-bootstrap recall gains; neither passes the registered day stability gate. Their Tuesday/Wednesday holdout recall is zero. Highest internal recall therefore does not justify production promotion. No post-outcome tuning was performed.

## Frozen artifacts and production

config/fuzzy/task05/protocol.json records the pre-result architecture and selection freeze. All15 fold configurations and fold_policies.json are saved. recommendation.json points back to config/fuzzy/task04/selected_v4.json. Production scoring ID remains ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b with its existing policies49.632522849397134/51.809236850031304/59.465890915130174. The FastAPI backend, React source, styles, all pages, metadata, catalog, API schema and previous reports are unmodified. Research files do not change active model loading.

## Explainability and execution

explanation_example.json contains a real eligible design row, label outside inference, full eight-feature memberships, per-module rules/strengths/centroids, final-layer rules/strengths and risk result. example_input.json has inputs only. Example command:

```powershell
.\.venv\Scripts\python.exe scripts/task05_predict.py --model config/fuzzy/task05/C_hierarchy_fold0.json --input reports/fuzzy/task05/example_input.json --policy-key C_hierarchy_0 --policy Balanced
```

Changing policy uses the existing transparent PolicyRiskModel wrapper and changes only the alert decision. Model-specific frozen fold thresholds are research artifacts, not new production policies. Invalid/unknown inputs abstain; intermediate output failure forces final abstention. Missing categories are reported as unavailable rather than fabricated.

## Performance and robustness

| Candidate | Design rows | Seconds | Rows/s | Max +0.1% score change | Near-anchor2ppm max |
|---|---:|---:|---:|---:|---:|
| B_flat8 | 14042 | 0.136316 | 103010 | 0.101600 | 0.00008162 |
| C_hierarchy | 14042 | 0.636833 | 22050 | 0.060438 | 0.00001631 |
| D_behavior | 14042 | 0.472698 | 29706 | 0.060438 | 0.00001631 |

CPU only, excluding disk IO. Per-layer centroid workspace is1,646,592 bytes for1024x201 float64; additional temporaries and retained explanation arrays increase total memory. The60k x78 research cache is bounded to tens of MB of numeric data; joins use DuckDB1GB memory cap/two threads. Full2.8M table is not materialized. No new dataset download. Hierarchies are several times slower than flat inference because they perform four/five Mamdani layers; measured desktop throughput remains suitable for experiments but is not a production SLA. Perturbation results cover1000 design rows with discrete SYN held unchanged, not a universal robustness bound.

## Reproducibility and validation

Run scripts/task05_research.py once to regenerate the eligible feature cache; scripts/task05_experiment.py freeze is one-time and refuses overwrite. The registered evaluate phase reproduces all candidate fitting/calibration/assessment/day-stress results and selection without source changes. scripts/task05_validate.py separately reproduces15 models,15 calibration policy sets,45 fold/policy metrics and15 day-stress metric sets, verifies exposed exclusions and historical hashes. scripts/task05_reports.py regenerates post-selection diagnostics, figures and these reports. All full prediction/curve/research caches are ignored under .tmp/task05. New small source/configs/numerical summaries are versioned. validation.json records final tests/build/API results.

Independent generalization remains unproven. Prior development assessments were adaptively reused, signature boundaries do not remove all near-duplicate/host dependencies, and capture-day scenario shift dominates stress. The educational web app remains intact; no improved-model integration is authorized by the failed promotion gate. Future work should predeclare a compact feature ablation and evaluate newly reserved independent network captures, retaining visible false-negative/false-alarm limitations. No remote Git operation is part of this workflow.

## Executed completion checks

164 Python tests and 15 frontend tests passed, zero failures. TypeScript and production build passed. All27 live unchanged-production API/direct-engine comparisons passed. Separate verification reproduced15 training-only models,15 calibration policy sets,45 policy metric rows,15 day-stress metric sets and the retained-model decision. The experimental CLI emitted the exact same complete explanation as direct Python inference. Integrity checks verified176 historical raw artifact hashes and242 prior tracked source/config/report/web files unchanged. No baseline tests were weakened.

Measured deep research dataframe size: 44,945,679 bytes; eight-input frame: 3,840,132 bytes. Eight-input conflicting-label vector groups: 6. Near-duplicate bin-boundary limitations remain. See resource_usage.json for scope; these are not peak RSS measurements.
