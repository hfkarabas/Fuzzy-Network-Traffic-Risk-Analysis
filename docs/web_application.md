# TASK03 local web application

The English dashboard wraps the unchanged scoring model, retained again in TASK04.
The backend now loads `config/fuzzy/task04/selected_v4.json` and its manifest/policies.
These scoring and policy files are byte-identical to TASK02B selections. TASK04
candidate results appear separately as reused internal validation; historical tests
are preserved. See `reports/fuzzy/task04/scientific_report.md` for the failed
improvement hypotheses and remaining scientific limitations.
It is an educational demonstration, not a reliable operational IDS. No fitting,
rule changes, policy recalibration, dataset downloads or live capture occur here.

## Run on Windows

From PowerShell in the repository, with the existing `.venv` and Node.js installed:

```powershell
cd C:\Fuzzy-Network-Traffic-Risk-Analysis
# First installation/build (package installation requires network access):
.\scripts\start-web.ps1 -Install -Build
# Later starts use installed packages and the built frontend, offline:
.\scripts\start-web.ps1
```

If Windows disables scripts, run the following process-scoped command instead;
it does not modify the saved execution policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-web.ps1 -Build
```

Open **http://127.0.0.1:8000**. The PowerShell process owns the foreground backend;
Ctrl+C stops it. It binds only to loopback. A matching already-running backend is
reused rather than duplicated. Temporary logs/caches remain repository-local.

Development mode starts the API as a hidden owned child when necessary and Vite in
the foreground; it stops its owned backend when Vite exits:

```powershell
.\scripts\start-web.ps1 -Dev
```

Development frontend: **http://127.0.0.1:5173**. Its `/api`, `/docs` and OpenAPI
requests proxy to port 8000. A backend already running separately is reused and
will not be stopped by this script. No CORS configuration is needed.

Manual commands, including when local script execution is restricted:

```powershell
py -m pip --python .venv install -r requirements-web.txt
npm --prefix web ci
npm --prefix web run build
.\.venv\Scripts\python -m uvicorn fuzzy_network_risk.webapp.api:app --app-dir src --host 127.0.0.1 --port 8000
# Optional second terminal for frontend development:
npm --prefix web run dev
```

Python 3.14 and Node 24 were used in this environment. requirements-web.txt is the
exact lock for the web application (core engine + FastAPI/Uvicorn); see the
dependency profiles in the README. package-lock.json
locks frontend dependencies. No environment variables or secrets need configuring.
Node/npm are needed for installation/build/development, not to serve an existing
production build. `web/dist` is generated and ignored, so a fresh checkout needs
the first install/build. All runtime fonts, SVG icons, code and data are local.

## Architecture

React + TypeScript + Vite renders five complete sections: overview, traffic
analysis, dataset examples, measured performance, and system information. A hash
router keeps production serving simple: FastAPI serves index.html and bundled
assets; a second Node process is unnecessary for the local production-like build.

Backend files live under src/fuzzy_network_risk/webapp:

- api.py: FastAPI lifespan, strict request/typed response schemas, safe errors,
  loopback-host validation, local frontend/static serving and offline API reference.
- service.py: cached small JSON/CSV data, authoritative model/policy metadata,
  actual Python inference adaptation and sampled membership curves.
- content.py: English feature descriptions, linguistic terms and rule presentation.

The FastAPI lifespan loads MamdaniRiskEngine once. Three PolicyRiskModel wrappers
share that engine; all thresholds come from selected_policies.json. The original
scoring model and 22 rules are never modified. Frontend code renders supplied
memberships and curve points; it does not implement membership evaluation, rule
firing, aggregation or defuzzification. Model/policy identity and input range flags
remain available in each result. Only presentation and chart coordinates are added.

## API contract

| Endpoint | Purpose |
| --- | --- |
| GET /api/health | loaded model identity and local status |
| GET /api/model | dataset/model metadata, real membership curves, rule inventory |
| GET /api/policies | three exact frozen thresholds and policy identities |
| POST /api/analyze | five numerical features and selected policy |
| GET /api/examples | curated real examples; historical label separate from inputs |
| GET /api/evaluation | recorded historical/internal metrics, scope and limitations |
| GET /openapi.json | FastAPI-generated request/response schema |
| GET /docs | offline API reference with no Swagger/ReDoc CDN dependency |

Example request:

```json
{
  "features": {
    " Flow Packets/s": 518.613723,
    " Total Fwd Packets": 26,
    " Packet Length Mean": 388.8085106,
    " Bwd Packet Length Std": 899.9799998,
    " Down/Up Ratio": 0
  },
  "policy": "Balanced"
}
```

This real eligible example scores 53.274634837391 / High. Balanced raises an alert;
Conservative does not, with the same score, memberships and rules. R06 and R09
activate. The original historical label is BENIGN; it is not sent to inference.

Responses contain status, score/category/alert (nullable on abstention), exact
applied policy/model identities, memberships, all positive-strength rules with
conditions/consequents/strengths, structured explanation keys, an English explanation,
input values, chart positions and out-of-training-range feature names.

Strict schema validation rejects strings masquerading as numbers, booleans,
negative/nonfinite measurements, missing fields, unknown policies and all extra
keys, including dataset labels. HTTP 422 returns explicit invalid_input with null
score/category/alert and safe validation messages. Explicit JSON null measurements
reach the frozen engine's abstention path and return HTTP 200 / invalid_input, also
with null outputs. Valid zero/extreme finite inputs follow the original engine
policy; extreme measurements saturate and carry range flags. Server failures return
a generic HTTP 500 message; stack traces stay out of responses. No inputs are saved.

## Real example catalog and metrics

web/catalog/examples.json contains nine unique real source rows from the eligible
TASK02B design bucket. Deterministic SHA256 priority selects four risk categories,
benign/attack labels, a false positive, a false negative and a policy-contrast case.
All reference predictions use the actual engine with Balanced policy. The contrast
case lies between frozen Balanced and Conservative thresholds. Source row/day,
observation group, signature, original label, model ID, source artifact hash and
selection method are retained. This is a curated teaching catalog, not a performance
sample. Every startup verifies its stored predictions against the frozen model.

The application never opens a Parquet file. Catalog rebuilding is optional and
requires only the existing bounded development artifact:

```powershell
.\.venv\Scripts\python scripts/build_web_catalog.py
.\.venv\Scripts\python scripts/build_web_test_fixture.py
```

The second command captures genuine adapter responses for isolated React tests;
that test fixture is not part of the production bundle. Neither command fits a
model, runs old tests, downloads data or changes historical artifacts.

The performance view reads existing reports/fuzzy/metrics.json and
reports/fuzzy/task02b/comparison_summary.csv at startup. It never recomputes metrics.
Historical grouped/day tests and TASK02B internal validation are shown separately.
Internal group-weighted fold averages and pooled raw-flow confusion matrices are
explicitly distinguished. The selected internal Balanced group FPR is 4.91%, while
raw-flow FPR is 15.71%; the UI presents both. No independent holdout or operational
error-rate guarantee is claimed. Internal CV used fold-specific calibrated thresholds,
not a new test of the single integration threshold. Risk categories remain the
authoritative model cuts 25/50/75; alert thresholds remain separate.

## Validation and QA

```powershell
.\.venv\Scripts\python -m pytest -q
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
# With the application running:
.\.venv\Scripts\python scripts/validate_web_http.py
# With the optional Vite frontend running:
.\.venv\Scripts\python scripts/validate_web_http.py --base http://127.0.0.1:5173 --output reports/web/dev_proxy_integration.json
.\.venv\Scripts\python scripts/task03_integrity.py
```

Windows sandbox temporary-file restrictions may require an explicitly local pytest
directory: `-p no:cacheprovider --basetemp=.tmp/pytest-local`. Actual logs and HTTP
checks are under reports/web. The HTTP verifier compares all nine examples under
all three policies against direct Python invocation and checks root/assets/docs,
metric identity, policy switching and invalid-input abstention.

Browser QA uses the served production build. Responsive navigation, actual analysis,
policy switching, rule evidence, explicit abstention and weighting distinctions are
checked. Focus styles, semantic form labels, keyboard-operable controls, arrow-key
tabs, Escape dismissal, reduced-motion support and a skip link are included. Mobile
off-canvas navigation is hidden from focus when closed. Risk is conveyed in text,
not color alone. This is not a certification of complete assistive-technology or
WCAG conformance. Screenshots are local generated QA artifacts and ignored by Git.

## Troubleshooting

- Port 8000 occupied: stop the other service, or inspect whether this app is already
  serving there. The startup script checks the loaded model ID before reusing it.
- Port 5173 occupied: stop the old Vite process; strictPort avoids silent URL changes.
- Frontend missing: run npm ci and npm run build under web; default startup also
  builds when dist is absent. Restart after backend code changes; Vite handles its
  own frontend HMR in development.
- API disconnect: a retry/error state appears and no new score is fabricated.
- Catalog/config mismatch: startup fails rather than displaying stale predictions.
- Decimal input: the HTML numerical field sends JSON numbers; API numeric strings
  are deliberately rejected. Exact leading spaces in feature keys are required.

Known detection weaknesses, scenario shift, duplicate/near-duplicate dependence,
limited five-feature representation and the lack of independent validation remain
unchanged. For a final course presentation, demonstrate a real policy-contrast
flow, inspect its memberships and rules, then show the false-positive/false-negative
catalog and measured limitations. Do not present curated examples as accuracy evidence.
