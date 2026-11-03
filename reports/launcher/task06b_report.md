# TASK 06B implementation and validation report

## Delivered behavior

The root Makefile defaults to `run`. Supported targets are `setup`, `run`,
`backend`, `frontend`, `test`, `build`, `check` and `help`. The standard-library
`scripts/dev.py` orchestrator prepares only repository-local dependencies and
supervises FastAPI on 127.0.0.1:8000 and Vite on 127.0.0.1:5173.

Python is selected from installed compatible interpreters, with project-local
venv validation and exact pinned distribution/import checks. Missing pip is
bootstrapped inside the venv only when needed. npm is invoked through Node and
its actual CLI file, avoiding Windows `.ps1` execution-policy failures. Lockfile,
runtime version and architecture changes trigger installation; healthy repeated
starts skip pip/npm installation. Local markers/caches are ignored. No runtime,
system toolchain or global package is installed automatically.

Separate setup/service locks prevent races and duplicate launchers. Existing
occupied ports are rejected without killing or reusing unrelated services.
Readiness verifies the backend model ID/configuration version and frontend HTTP
response. Unexpected exits/timeouts fail startup and clean owned services.
Windows Job Objects and POSIX process sessions own descendant trees. Interrupts
clean up in reverse startup order. Dependency/test/build subprocesses also use
owned process trees. There is no stale PID-file cleanup or destructive clean target.

## Actual validation

| Check | Actual result |
|---|---|
| `make test`: Python | 202 passed, 0 failed (29 new launcher tests) |
| `make test`: frontend | 15 passed, 0 failed |
| `make build` | TypeScript and Vite production build passed |
| `make help`, `make check`, repeated `make setup` | Passed; repeated setup skipped installations |
| Fresh isolated Python/npm installation | Passed in `.tmp/Setup Ü Space`; pinned Python stack and 106 npm packages installed locally |
| Repeat isolated setup | Passed without another install |
| Default native GNU Make startup | Both services ready, HMR client served, API proxy healthy |
| Frozen inference compatibility | All 27 example/policy combinations matched direct engine scores, categories, alerts, memberships and rule strengths |
| Native console interruption | Targeted Windows CTRL_BREAK_EVENT; both ports released before harness safety-job closure |
| Standalone targets | `make backend` and `make frontend` started only their requested service and stopped owned descendants |
| Existing PowerShell fallback | Actual production HTML and frozen backend health served successfully; owned process tree stopped |
| No-dataset startup | Isolated checkout had neither `data/` nor `datasets/`; startup and predictions succeeded |

Raw bounded test/build evidence is stored in `test_run.txt` and `build.txt`.
Machine-readable results are `smoke.json`, `standalone.json`, `validation.json`.
The fresh installation transcript remains ignored because package-manager output
can contain machine-specific registry configuration; assertions in the preservation
validator record its observed success without publishing that transcript.

The first optional standalone smoke incorrectly requested backend JSON health from
the frontend-only target and timed out. The harness was corrected to probe Vite HTTP
and allow bounded asynchronous Windows job teardown; the application code did not
need a change. The successful final results are recorded separately. An initial
POSIX-mock test also needed Windows-absent signal APIs supplied by the mock; no
existing test was weakened.

## Integrity and reproduction

No model, membership, rule, policy, evaluation artifact, frontend source, Python
dependency pin or npm lockfile changed. The sole backend edit makes the original
frozen model/policy checksum guard portable across LF/CRLF checkouts. The LFS archive
and original/prepared datasets are checked against their existing hashes.

With prerequisites on PATH, reproduce application checks with `make test`,
`make build`, `make check`, then `make`. Maintainers can run
`python scripts/smoke_launcher.py --make /absolute/path/to/make` (requires free
ports; this smoke interrupts its own Make process). The isolated no-dataset fixture
is an ignored validation-only copy, not a second project or runtime dependency.
`python scripts/validate_launcher.py` rechecks this workstation's stored evidence
and historical hashes; it is not run during ordinary startup and intentionally
requires the existing local historical files/installation transcript.

## Limits and platform status

Windows native setup, Make, child/grandchild cleanup, API and Vite paths were tested.
Ordinary KeyboardInterrupt cleanup is unit-tested and exercised by the bounded
launcher smoke mode; the native targeted console smoke uses Ctrl+Break rather than
a physical keyboard Ctrl+C. GNU Make can return Windows interrupt code 3221225786
after successful cleanup.

macOS Intel, Apple Silicon and Linux were not available for native execution.
POSIX session/signal behavior is covered with mocks; native cross-platform success
is not claimed. Use matching native Python/Node/Make architectures; changed runtime
architecture forces dependency verification/synchronization. Missing prerequisites
remain a manual installation step. First/changed dependency setup requires package
registry access. Existing malformed/unrelated/linked virtual environments are never
silently deleted or overwritten. No live dataset download, preprocessing, Git LFS
command, model training, registry update check or remote Git operation is part of
normal startup. See `docs/launcher.md` for setup and troubleshooting.
