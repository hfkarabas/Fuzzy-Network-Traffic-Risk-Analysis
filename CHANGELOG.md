# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the application
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Versioning policy

- **Application version** (`MAJOR.MINOR.PATCH`): one value for the Python package,
  HTTP API, OpenAPI schema and web frontend. The single source of truth is
  `fuzzy_network_risk.__version__` in `src/fuzzy_network_risk/__init__.py`;
  `pyproject.toml` reads it dynamically and `web/package.json` /
  `web/package-lock.json` must match (`tests/test_versioning.py` enforces this).
  It is reported by `GET /api/health` (`app_version`), `GET /api/model` and the
  System Information page.
  - MAJOR: incompatible API, CLI or response-schema changes.
  - MINOR: backwards-compatible features.
  - PATCH: backwards-compatible fixes.
- **Model identity** is versioned independently and never changes with the
  application version: `model_id` (SHA-256 of the configuration),
  `configuration_version` and `model_version` in
  `config/fuzzy/task04/selected_manifest.json`. A new model requires a new
  configuration file and manifest, not an application release alone.
- **Releases** are marked with annotated Git tags `vMAJOR.MINOR.PATCH` on `main`
  after the release pull requests are merged. Each pull request adds its entry
  under the upcoming version below.

## [2.0.0] - Unreleased

### Changed

- **Breaking (API):** the application is English only. Responses no longer
  contain `explanation_tr`, `risk_level_tr`, `conditions_tr` or `text_tr`;
  `explanation` is the English rule-based explanation and activated rules carry
  `conditions` and `text`. Error messages, notices and `/docs` are English.
- **Breaking (CLI):** `scripts/score_flow.py` scores with the deployed model and
  a calibrated alert policy (Balanced by default, `--policy` to choose) instead
  of the historical model's embedded threshold 25. The old behaviour is
  available explicitly with `--embedded-threshold`. Documented exit codes.
- Live monitoring attributes packet loss and rejected packets to the affected
  flows only (`capture_queue_loss`, `endpoint_packet_rejected`,
  `concurrent_capture_error`) instead of disabling scoring for the rest of the
  session; new `impaired_flows` counter.
- Python dependencies split into lock files per purpose (`requirements.txt`,
  `-web`, `-live`, `-research`, `-dev`) with matching `pyproject.toml` extras;
  the web application no longer installs research and test tooling.
- One application version for Python, API and frontend (this policy).

### Added

- `app_version` in `/api/health` and `/api/model`; shown on System Information.
- `scripts/build_web_test_fixture.py` regenerates all frontend fixtures.

### Removed

- Turkish interface, runtime translation layer and language switcher.

### Fixed

- Platform-dependent last-digit float differences no longer fail fixture tests;
  slow machines no longer fail full-page frontend tests by timeout.

## [1.0.0] - 2026-11-03

First complete release (TASK 01–10): CIC-IDS2017 acquisition and preparation,
frozen 22-rule Mamdani risk engine with Sensitive/Balanced/Conservative alert
policies, FastAPI backend, bilingual React dashboard, opt-in live flow
monitoring with synthetic replay, Git LFS dataset archive and research reports.
Corresponds to commit `60b3738`.

[2.0.0]: https://github.com/hfkarabas/Fuzzy-Network-Traffic-Risk-Analysis/compare/60b3738...HEAD
[1.0.0]: https://github.com/hfkarabas/Fuzzy-Network-Traffic-Risk-Analysis/tree/60b3738
