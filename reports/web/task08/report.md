# TASK 08 — unified fuzzy analysis visualization

## Implementation

Baseline: `1b45fb79ccf521fd191732128c571bb435e02800`, initially clean.
Historical analysis already had a server-sampled MembershipChart, ScoreGauge,
ResultPanel and tabbed Evidence with rule-strength bars. These components were
embedded in App.tsx. Live details instead rendered raw membership JSON and text.
Neither page had an actual aggregated-output/centroid plot; only the gauge and
text explained defuzzification.

The historical presentation was extracted to `web/src/components/FuzzyAnalysis.tsx`.
Both pages now reuse its exact input curves/scaling, numeric memberships, risk
gauge, categories, Turkish explanations and all activated-rule bars. Tab prefixes
avoid collisions; rules are sorted without mutating backend results.

`LiveFlowDetail.tsx` provides an inline detail view with endpoints/ports, protocol,
duration, completion reason, provisional status and inference eligibility. Five
read-only observed values use existing formatting with full-precision hover text.
The selected flow is pinned when polling evicts it; close restores keyboard focus.
Valid partial segments retain a prominent experimental-score warning. Invalid,
insufficient or mismatched-model flows retain metadata but render no inference
graphs or fabricated score.

Sensitive/Balanced/Conservative comparison cards use existing backend decisions.
A selected policy absent from a pinned record is obtained from existing
`/api/analyze`; its score must equal the original flow score. The policy-independent
membership/output chart stays mounted across policy changes.

## Read-only output data

`OutputVisualization.tsx` is shared by historical and live analysis. It draws the
four actual output membership sets, actual max-aggregated clipped output, and
centroid marker. It consumes `POST /api/visualization/output` using the existing
five-feature request schema. The response must match the selected model ID and
exact risk score; malformed/unavailable/stale data produces a message, never
invented curves. Frontend code performs only SVG coordinate mapping, not inference.

The engine's existing `_infer` can optionally expose its already-computed aggregate;
the numerical operations, centroid algorithm, default prediction return contract,
model configuration and policy semantics are unchanged. The endpoint calls that
same calculation for one record. Invalid/no-rule cases return no curves or centroid.
No hardcoded membership parameters, new charting library or dependency was added.

## Validation executed

- **69 focused Python tests passed, zero failures:**
  `tests/test_visualization.py`, `tests/test_web_api.py`, `tests/test_fuzzy.py`.
- **36 frontend tests passed, zero failures**, including all previous application
  tests plus shared-component, live detail, invalid/partial/model-mismatch,
  policy-invariance, retention and keyboard-focus coverage.
- TypeScript `tsc --noEmit` and Vite production build passed.
- Every saved historical analysis response (27 example/policy responses) matches
  its original fixture exactly. Both original replay flow responses match exactly.
- Eleven vectors (nine historical examples + TCP/UDP replay) were checked under
  all three policies: output curves equal the frozen engine sets, aggregate equals
  the independently assembled max/min clipped-rule reference, and centroid equals
  the original score. Output visualization does not change subsequent predictions.
- New visualization fixtures are checked against the engine; existing historical
  and live reference JSON files were not edited.

Actual normalized test/build output and source hashes are recorded alongside this
report in `backend_tests.txt`, `frontend_tests.txt`, `build.txt`, `validation.json`.
The initial build identified test callers that needed the newly explicit model-data
prop; they were updated. An evidence-parser initially matched Vitest's six test
files instead of its 36 tests and was corrected. Neither required a model change.

## Scope and remaining limitations

Changed: App/LiveTraffic wiring and focused test callers, scoped styles, shared/new
visualization/detail components and tests, a small new plot fixture, read-only
engine/API diagnostics, and the brief inspection section in live documentation.

Protected paths were compared with the baseline: datasets/LFS settings, frozen
configurations, capture/flow-management modules, memberships/policies, preprocessing
and launchers, dependency manifests/lockfile, historical reference outputs and
previous evaluation reports are unchanged. No full dataset loading, preprocessing,
TASK04/TASK05 experiment, capture or model optimization was run. No remote Git
operation was executed. No unrelated page was redesigned.

Validation is automated DOM/SVG rendering and API/type/build testing; no native
browser screenshot check was performed. Existing live-feature compatibility and
model-generalization limitations still apply. Restart an older backend to make the
new read-only output endpoint available; a missing endpoint leaves the existing
score intact and explains why its additional plot is unavailable. The local commit
hash and final working-tree state are supplied in the final response.
