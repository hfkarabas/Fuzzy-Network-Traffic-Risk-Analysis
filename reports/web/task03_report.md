# TASK03 completed application report

## Architecture and implemented functionality

FastAPI loads the original selected Mamdani engine once through its lifespan.
Three PolicyRiskModel wrappers share it and read exact frozen thresholds. A React,
TypeScript and Vite frontend uses HTTP; FastAPI serves the production bundle on
127.0.0.1:8000, while optional Vite development mode proxies to it on 127.0.0.1:5173.
No inference is duplicated in JavaScript. The model/rules/memberships/policies were
not altered. Model identity: ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b.

All five Turkish sections are complete: overview, manual analysis, real dataset
examples, evaluation and system information. Manual inputs have units, behavior
descriptions and non-definitive security interpretations. Results include a gauge,
explicit category ranges, separate binary alert, model/policy identities, human
explanation and range flags. The evidence panel renders server-computed degrees,
actual membership-function points, the current measurement marker, activated-rule
conditions/strengths/consequents and a six-step inference diagram. Weak positive
activations are not rounded into an apparent zero; precise values remain in API
responses. Scientific formatting keeps extreme finite measurements compact.

Policy switching sends a real request and preserves the fuzzy score while changing
the policy decision. Real source row 1674387 scores 53.274634837391 / High: Balanced
alerts and Conservative does not. Its archived label is BENIGN, displayed separately
and never passed to inference. The catalog has nine unique eligible design rows,
including all four naturally observed risk categories, benign/attack labels, false
positive, false negative and a threshold-contrast example. Physical source values,
labels, groups and provenance were verified exactly. Catalog startup rechecks model
predictions. The application never loads Parquet; runtime needs no dataset download.

## Measured-results honesty

Historical grouped and day tests use the existing metrics.json; internal validation
uses the existing comparison_summary.csv. No metrics were recomputed. Historical
test thresholds remain visible. The UI separates internal group-weighted fold means
from raw-flow confusion totals and displays both 4.91% group FPR and 15.71% raw-flow
FPR for Balanced policy. Fold-specific CV thresholds are not misrepresented as a
new final test of the single integration threshold. No credible untouched holdout,
attack-probability interpretation, calibrated severity or production readiness is
claimed. Original performance failures and negative refinement findings remain visible.

## API and validation

GET /api/health, /api/model, /api/policies, /api/examples and /api/evaluation are
implemented. POST /api/analyze uses strict Pydantic aliases for the five exact
feature names, a fixed policy enumeration and a typed response. Labels/extra fields,
numeric strings, booleans, negative/nonfinite values and missing keys are rejected.
Validation responses explicitly abstain with null score/category/alert. Null
measurements use the engine's existing abstention behavior. Zero and extreme finite
values follow unchanged engine semantics. Unexpected failures never expose stack
traces. OpenAPI JSON and a local /docs reference work without CDN dependencies.

## Executed release evidence

- Python tests: **112 passed, 0 failed**, including the original 91.
- Frontend tests: **14 passed, 0 failed** across three files; captured
  real Python responses support rendering, rule evidence, policy switching, invalid
  data, disconnection, malformed responses, navigation/filtering and keyboard tabs.
- TypeScript checking: PASS. Production build: PASS.
- Live HTTP: 27 example/policy comparisons against direct
  Python inference, for all 9 examples; same checks also
  passed through the actual Vite development proxy. Root/assets, strict abstention,
  metrics identity and offline documentation were checked.
- Mean production analyze HTTP latency in the recorded local check:
  2.200 ms. This small loopback measurement is
  not a general load-test guarantee.
- Browser QA: all five pages; actual rule evidence and policy contrast; invalid
  inputs and deliberate backend disconnection without fabricated scores. Laptop
  1280px, tablet 768px and mobile 390px had no horizontal overflow. Mobile navigation,
  hidden closed sidebar, result ranges and six-step explanation were checked.
- No unexpected browser console errors before the intentional disconnect test.
- PASS: 176 historical artifacts unchanged

Dark navy/cyan styling uses local system typography and bundled SVG icons. Labels,
focus states, keyboard controls, arrow-key tabs, Escape dismissal, skip navigation,
reduced motion and textual/color-independent risk descriptions are implemented.
Screenshots are saved under reports/web/screenshots and ignored by Git. No requested
core visual feature is missing. Physical mobile-device and full assistive-technology
certification were not performed; this is not a formal WCAG audit.

## Running and repository output

First setup: scripts/start-web.ps1 -Install -Build. Later offline use:
scripts/start-web.ps1. Optional development: scripts/start-web.ps1 -Dev.
The one-command production and development scripts were both executed successfully.
QA-owned servers were stopped after validation. See docs/web_application.md for
exact Windows/manual commands, dependencies, API payloads and troubleshooting.

New code is under src/fuzzy_network_risk/webapp and web/src; the original engine
and policy wrapper source remain unchanged. requirements-web.txt and package-lock.json
pin web dependencies. A tiny curated catalog and genuine-response test fixture are
versioned; node_modules, dist, screenshots and large datasets remain ignored. No
remote Git synchronization, cloud publishing, user account, database, live capture,
GPU work, training or evaluation rerun occurred. A local source/config/test/docs
commit completes the task; the resulting hash is reported in the final response.

## Remaining limitations and presentation recommendation

The existing false alarms, missed attacks, scenario/class shift, duplicate and
near-duplicate dependence and limited five-feature representation remain unchanged.
Curated examples are not accuracy evidence. Future revisions require suitable
training/validation and fresh evaluation evidence. For the course presentation,
load the policy-contrast example, inspect simultaneous Moderate/Intensive memberships,
show its active rules, switch policy without changing score, then examine a false
negative and the transparent evaluation dashboard. A functioning explainable fuzzy
engine and a reliable operational detector are different achievements.
