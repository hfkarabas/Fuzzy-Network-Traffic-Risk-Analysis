# TASK 06B repository audit

Baseline: `ca49a972c1b29f1edd75a4b85ece09d5d5ee64ae`. The working tree was clean
before implementation. No remote Git command was executed.

## Existing application

- Backend: `fuzzy_network_risk.webapp.api:app`, Uvicorn `--app-dir src`, port 8000.
- Frontend: React/TypeScript, Vite config `web/vite.config.ts`, port 5173,
  `/api`, `/docs`, `/openapi.json` forwarded to the backend. npm scripts already
  provide `dev`, `test` and `build`; build runs TypeScript checking first.
- Existing production launcher: `scripts/start-web.ps1`, with `-Install`, `-Build`
  and `-Dev`; retained without modification, as was `scripts/setup.ps1`.
- Python pins: `requirements-web.txt` includes the existing `requirements.txt`.
  Existing `.venv` contained the full working stack, initially without pip.
- Frozen active model: `config/fuzzy/task04/selected_v4.json`, 22-rule/five-input
  Mamdani, model ID
  `ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b`.
  Policies and metadata use adjacent selected manifest/policy JSON files.
- Original dataset: LFS Parquet `datasets/cic_ids2017_v1.parquet`. Web startup
  already uses small tracked artifacts and does not need the source dataset.

## Prerequisite findings

Native validation used Windows x64, Python 3.14.7, Node 24.19.0, npm 11.17.0.
GNU Make was absent from the system PATH. GNU Make 4.4.1 was explicitly installed
into ignored `.tmp/task06b-tools` for validation only, without a system/global
installation or persistent PATH modification.

The existing lockfile is stricter than Vite alone: jsdom requires Node 22.22.2+
or 24.15+ or 26+, while Vitest excludes odd Node 23/25. The launcher checks this
intersection and npm >=10. Existing dependency pins/lockfiles were preserved.

## Cross-platform integrity issue found

The selected manifest stores hashes of CRLF JSON content. A macOS-style LF checkout
would fail the original byte-only model/policy verification. The shared
`config_integrity.frozen_text_matches` helper accepts only the original bytes or
their LF/CRLF representations. Values, additional whitespace and model/policy
changes still fail verification. An LF-only fixture successfully loaded the actual
WebService without any dataset directory. Model identity and predictions remain
unchanged, including all nine examples under all three policies.

## Preservation method

`scripts/validate_launcher.py` verifies the prior historical raw-file manifest,
the complete LFS archive SHA-256, and every baseline tracked file (text compared
after LF/CRLF normalization). Only README, `.gitignore` and the narrowly scoped
WebService hash check may differ among pre-existing files. New startup code,
tests, documentation and validation evidence are added separately. See
`validation.json` for exact counts, sizes and hashes.
