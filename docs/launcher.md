# Cross-platform Make startup

## Quick start

With the system prerequisites available, run from the repository root:

```sh
make
```

The default target is `run`. It checks the frozen model/display files and ports,
creates a repository-local `.venv` when absent, synchronizes the exact Python pins,
uses `npm ci` for missing/changed frontend dependencies, and starts both services.
First setup requires package-registry access and can take several minutes.

Open **http://127.0.0.1:5173**. The API is **http://127.0.0.1:8000**, with offline
documentation at **http://127.0.0.1:8000/docs**. Ctrl+C stops the owned services and
their descendants. Keep the launcher terminal open while working. Vite serves the
development source and HMR client; `/api`, `/docs` and `/openapi.json` proxy to 8000.

Later runs validate installed versions/imports and skip installation when unchanged.
They do not contact package registries merely to check for newer versions. Runtime
uses only the small tracked model, example and metric files.

## System prerequisites

- **Python 3.12+**, with `venv`/`ensurepip`; Python 3.14 matches the validated stack.
- **Node.js 24.15+ LTS**, or 22.22.2+ with bundled **npm 10+**. Locked jsdom/Vitest
  require newer Node versions than Vite alone; Node 20 and 23/25 are rejected.
  Node 26+ is also permitted by the current lockfile engines.
- **GNU Make**. It is an external prerequisite and is never installed by startup.
- Git/Git LFS are needed for normal cloning/data distribution, not web runtime.

Download Python from [python.org](https://www.python.org/downloads/) and Node from
[nodejs.org](https://nodejs.org/). No administrator operation, system Python/Node
installation, global package installation or automatic upgrade is performed by the
launcher. Existing unrelated/invalid/linked environments are not replaced.

The Makefile probes `py`/`python` on Windows and `python3`/`python` on POSIX. The
standard-library bootstrap can locate installed Python 3.12+ runtimes when launched
by an older Python 3.8+ interpreter. Windows Python Manager automatic runtime
installation is explicitly disabled. Override the bootstrap executable if needed:

```sh
make PYTHON="/path with spaces/to/python3"
```

`PYTHON` is one executable path, not a shell command containing additional options.

## Windows 10/11

Use native Python and Node installers matching the machine architecture and ensure
their commands are on PATH. The orchestrator invokes Node's actual `npm-cli.js` via
`node.exe`, so PowerShell script execution policy does not block npm startup.
Neither Git Bash, WSL nor a package manager is required.

If GNU Make is not already installed, one explicit project-local option is the
[gnumake PyPI wheel](https://pypi.org/project/gnumake/), which supplies GNU Make:

```powershell
# Explicit optional tool installation, not part of automatic startup:
py -3 -m pip install --target .tools/gnumake --no-deps gnumake==4.4.1
$env:Path = "$PWD\.tools\gnumake\bin;$env:Path"
make --version
make
```

This places the tool inside the checkout, not in global Python or system folders.
The PATH change applies only to the current PowerShell session. The validated wheel
is Windows x64; use a suitable native GNU Make distribution for other architectures.
If pip is unavailable, install Python with pip enabled or choose an existing GNU Make
distribution yourself. The launcher does not install a toolchain or package manager.

The original production PowerShell script remains supported and unchanged:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-web.ps1 -Install -Build
# Subsequent production-like starts:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-web.ps1
```

That is a separate production-build workflow. `make` uses Vite development mode.
The process-scoped invocation does not alter the saved execution policy.

## macOS Intel and Apple Silicon

Install Xcode Command Line Tools if `make` is absent:

```sh
xcode-select --install
```

Complete Apple's installer yourself, then use native Python 3.14 and Node 24 for
your architecture. Python.org universal2 packages or the appropriate native Node
installer are suitable options. If you already use Homebrew, native Python/Node
formulae are another option; Homebrew itself is not assumed or installed.
On Apple Silicon prefer arm64 Python and Node. No Rosetta command or x86 translation
is used. Dependencies are installed for the interpreter/Node architecture actually
running. A copied Windows `.venv` is invalid and must be moved/recreated by its owner.

The POSIX path uses `.venv/bin/python`, `fcntl` locks and independent process sessions.
Shutdown signals only the sessions created by this launcher. Native macOS Intel,
native Apple Silicon and native Linux execution were **not available for testing**;
the POSIX branches were inspected and tested with platform-specific mocks. Pinned
wheel availability may depend on OS/Python/CPU versions; installation errors remain
visible rather than silently changing pins or building an unrelated environment.

## Commands

| Target | Behavior |
|---|---|
| `make`, `make run` | Prepare dependencies and supervise backend + Vite |
| `make setup` | Prepare/adopt validated local environments |
| `make backend` | Prepare Python only; backend on 8000 |
| `make frontend` | Prepare npm only; frontend on 5173; API requires a backend |
| `make test` | Full pytest suite and frontend Vitest suite (contributor profile) |
| `make lint` | Ruff lint, Ruff format check and TypeScript typecheck; changes nothing |
| `make build` | TypeScript validation and production frontend build |
| `make check` | Readiness checks without installation or state-marker writes |
| `make help` | Command summary |

For independent terminals, `make backend` and `make frontend` can run together.
`make run` refuses to reuse already-occupied ports. Stop the existing service yourself;
the launcher never chooses another port silently or kills an unrelated listener.
Preparation/build/tests require the relevant service locks; stop running development
commands first. No destructive `clean` target is supplied.

Without Make, the same orchestrator is available as `python scripts/dev.py run`
(`python3` on macOS). This fallback still requires compatible Python and Node/npm.

## Dependency state and recovery

Python declarations are profile specific: `run`, `setup`, `backend` and `build`
use `requirements-web.txt`; `test` uses `requirements-dev.txt` (web, optional
capture, research modules and pytest). Each profile's recursive pinned includes
and `pyproject.toml` are hashed into its own marker, so switching between `run`
and `test` does not reinstall anything. Conflicting pins across includes are
rejected. They are hashed with interpreter/platform identity. Installed
distribution versions and actual web imports are checked every time. Healthy
existing environments can be adopted without reinstallation; declaration changes
synchronize through that environment's own `python -m pip`. Missing pip is bootstrapped
with its own `ensurepip`. Broken imports with otherwise matching package metadata
trigger a pinned force-reinstall. No global pip operation occurs.

The frontend checks package/lock hashes, Node/npm/architecture, package versions,
essential executable shims and imports including the native Vite binding. Missing,
changed or incomplete installations trigger `npm ci --include=dev`. The tracked
lockfile is never regenerated or upgraded. Linked `node_modules` is refused before
reinstallation. Existing successful markers are not replaced on installation failure.

Markers, lock files, test scratch and local caches live under ignored `.tmp`/`.cache`.
OS locks release on exit, including crashes; they do not depend on stale PID files.
Windows uses separate console process groups plus kill-on-close Job Objects, while
macOS/Linux use owned POSIX sessions. Startup failure, unexpected child exit and
interrupts all clean up the children. Repeated Ctrl+C is ignored during final cleanup.
Windows hosts without a shared console use the Job Object cleanup guarantee.

## Troubleshooting

- **`make` not recognized:** install GNU Make explicitly and add its bin directory
  to this terminal's PATH, or use the Python CLI / existing PowerShell fallback.
- **Old Python/Node:** install a compatible native runtime yourself, restart the
  terminal and run `make check`; no runtime is downloaded by the launcher.
- **Invalid `.venv`:** the launcher preserves it and reports the problem. Move or
  repair it manually; then `make setup` can create a fresh local environment.
- **Package registry unavailable:** first/changed setup needs registry access.
  Rerun when available. Healthy cached installations start without reinstalling.
- **Port occupied / another launcher active:** stop its owning terminal, then retry.
  No process is killed to resolve conflicts and no PID file should be deleted.
- **Missing model/report files:** restore the tracked files from your checkout.
  Training, Git LFS downloads and full dataset reconstruction are not a remedy.
- **LF/CRLF checkout:** frozen JSON checks permit only line-ending conversion while
  preserving the original hash contract. Changed values or added spaces still fail.
- **Native npm binding missing after architecture change:** `make setup` detects the
  failed import and runs the existing lockfile through npm ci for the current host.

## Validation scope

Windows native tests include fresh pinned Python/npm setup in a Unicode/spaced path,
repeat setup without installs, default GNU Make startup without any dataset directory,
Vite HMR/proxy requests, all 27 example/policy predictions and targeted native console
interruption. Both ports are checked free **before** the smoke harness's independent
safety cleanup. Unit tests cover ordinary KeyboardInterrupt cleanup and Windows-owned
grandchildren, plus mocked POSIX session behavior. Targeted Windows console testing
uses Ctrl+Break; normal interactive Ctrl+C enters the same cleanup path. An interrupted
GNU Make may return a nonzero interrupt code even when cleanup succeeds.

See `reports/launcher/` for actual test/build, smoke, audit and preservation evidence.
No model parameters, policies, source datasets, LFS archive or frontend design changed.
