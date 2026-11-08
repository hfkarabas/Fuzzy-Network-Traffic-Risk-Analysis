# Scripts

Command-line entry points, grouped by purpose. Run every script from the
repository root with the project virtual environment, for example
`.venv/bin/python scripts/score_flow.py` (Windows: `.\.venv\Scripts\python.exe`).
Scripts locate the repository from their own path, so the working directory only
matters for relative `--input` files. The **Profile** column names the
`requirements-*.txt` lock needed (see the README's dependency profiles).

## Application (top level)

| Script | Profile | Purpose |
|---|---|---|
| `dev.py` | none (stdlib) | Cross-platform setup and supervised startup; used by `make` (`setup`, `run`, `backend`, `frontend`, `test`, `build`, `check`). |
| `start-web.ps1` | web | Windows launcher for the built dashboard on http://127.0.0.1:8000 (`-Install`, `-Build`, `-Dev`). |
| `setup.ps1` | research | Windows: create `.venv` for the offline research pipeline. |
| `score_flow.py` | core | Score flow measurements with the deployed model and alert policy; see [docs/fuzzy_api.md](../docs/fuzzy_api.md#command-line-scoring). |

## `data/` — dataset acquisition, preparation and Git LFS archive

| Script | Purpose |
|---|---|
| `acquire.py` | Acquire the pinned Hugging Face source revision; caches stay inside the repository. |
| `prepare.py` | Full-data profiling and batched preparation (uses `inspect_candidates`, `recover_sessions`, `report`). |
| `inspect_candidates.py` | Small-column diagnostics used to choose the input schema. |
| `recover_sessions.py` | Recover coarse capture-day provenance from the source CSVs. |
| `report.py` | Dataset reports and static figures. |
| `cache_integrity.py` | Hash source/cache data before processing and verify afterwards. |
| `validate_outputs.py` | Read-only validation of all preparation outputs. |
| `build_dataset_archive.py` | Create the lossless source Parquet archive from the local cache. |
| `verify_dataset_archive.py` | Verify the downloaded LFS archive (no network, no writes). |
| `restore_dataset_archive.py` | Rebuild the v1 data paths offline from the archive. |
| `validate_archive_pipeline.py` | Check a full offline reconstruction against existing outputs. |
| `validate_lfs_index.py` | Verify the LFS pointer, attributes and cached object. |
| `report_dataset_lfs.py` | Summarize local LFS checks; never stages or uploads. |

Profile: research. See [docs/methodology.md](../docs/methodology.md) and
[docs/dataset_lfs.md](../docs/dataset_lfs.md).

## `fuzzy/` — fitting, evaluation and reports of the fuzzy model

| Script | Purpose |
|---|---|
| `run_fuzzy.py` | Phases `fit`, `evaluate`, `report`, `all` (no network). |
| `fuzzy_reports.py` | Reports and figures from frozen configurations and saved predictions. |
| `validate_fuzzy.py` | Numerical stability and persisted-model reproducibility checks. |

Profile: research. See [fuzzy system design](../reports/fuzzy/fuzzy_system_design.md).

## `research/` — registered experiments (TASK 02–05)

Historical, pre-registered experiment pipelines that produced the evidence in
`reports/fuzzy/task02b`, `task04` and `task05`: preparation, design-only
diagnostics, experiments, validation, reports and integrity audits.
They require the prepared datasets under `data/` (not tracked) and the research
profile. See [docs/task02b_workflow.md](../docs/task02b_workflow.md).

| Stage | Scripts |
|---|---|
| TASK 02 integrity | `task02_integrity.py` |
| TASK 02B | `task02b_prepare.py` → `task02b_diagnostics.py` → `task02b_experiment.py` → `task02b_validate.py` → `task02b_reports.py`; `task02b_integrity.py` |
| TASK 03 integrity | `task03_integrity.py` |
| TASK 04 | `task04_experiment.py` → `task04_validate.py` → `task04_diagnostics.py` → `task04_finish.py` |
| TASK 05 | `task05_research.py` → `task05_experiment.py` → `task05_validate.py` → `task05_reports.py` → `task05_finalize.py`; `task05_predict.py` |

> **Reproducibility note.** These scripts register SHA-256 hashes of their own
> source files and of the files they depend on, and the frozen manifests under
> `config/fuzzy/` record their original `scripts/<name>.py` paths. Since 2.0.0 the
> scripts live in this folder, and some depend on application files that changed
> after 1.0.0. To re-run an experiment and compare hashes bit for bit, check out
> the `v1.0.0` tag (commit `60b3738`). The committed reports and configurations
> remain the authoritative record of those experiments.

## `webapp/` — frontend fixtures and example catalog

| Script | Profile | Purpose |
|---|---|---|
| `build_web_test_fixture.py` | live | Regenerate the three React test fixtures from the real service and a synthetic replay. Run after any API response change. |
| `build_web_catalog.py` | research | Build the curated example catalog from eligible design records. |
| `validate_web_catalog.py` | research | Provenance check of the catalog against the design rows. |
| `validate_web_http.py` | web | Exercise a running loopback API and compare every example to direct inference. |
| `summarize_web_validation.py` | web | Summarize recorded release evidence. |

## `validation/` — release and integration checks

| Script | Profile | Purpose |
|---|---|---|
| `smoke_launcher.py` | web | Real `make` startup/proxy/inference/interrupt smoke test. |
| `validate_launcher.py` | web | Recheck launcher evidence and preservation. |
| `validate_realtime.py` | live | HTTP/Vite synthetic-replay integration; optional authorized loopback capture. |
| `validate_realtime_integrity.py` | web | Local live-monitoring evidence audit. |

These are run manually before a release, not by `make test`.

## Conventions for new scripts

- Put the script in the group it belongs to; keep only user-facing entry points
  at the top level.
- Start with a one-line module docstring stating what it does and what it never
  does (downloads, writes, fitting), and add it to the table above.
- Resolve the repository as `ROOT = Path(__file__).resolve().parents[N]` (N = 1
  at top level, 2 inside a group) and add `ROOT / 'src'` to `sys.path`.
- If tests import the script, make sure its folder is in `pythonpath` in
  `pyproject.toml`.
