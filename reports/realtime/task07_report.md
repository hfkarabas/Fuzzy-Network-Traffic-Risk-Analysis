# TASK 07 — local real-time monitoring integration

## Outcome and evidence boundary

An opt-in **Canlı Trafik** page, monitoring API, optional Scapy capture backend,
bounded bidirectional flow tracker and adapter to the unchanged production model
are implemented. The complete application path is validated with deterministic
serialized synthetic IPv4 TCP/UDP packets and actual localhost HTTP through Vite
and FastAPI. The React tests consume a real replay-response fixture.

**Actual captured traffic validation is NOT COMPLETE:** this Windows workstation
has no usable Npcap provider. No driver was installed, no interface was secretly
selected, and no real-capture success is claimed. Linux/macOS capture code has no
native validation here. Replay success is not evidence of intrusion-detection
accuracy or exact historical CICFlowMeter equivalence.

## Initial repository findings

Baseline was clean TASK06B commit `29471e132cbbd2189b8807880a286056ebeb24c6`.
FastAPI entrypoint is `fuzzy_network_risk.webapp.api:app`, with a lifespan-loaded
WebService and offline manual/example analysis at `/api/analyze`. React uses
`web/src/App.tsx`, Vite on 5173 and API proxy to 8000. Production build is also
served by FastAPI. Existing Make and PowerShell launchers bind loopback.

The active model is `config/fuzzy/task04/selected_v4.json`, the original five-input,
22-rule min/max/centroid Mamdani system. TASK05 research hierarchies were not
promoted. Selected manifest/policy checks and model identity remain unchanged:
`ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b`.
Policy thresholds remain Sensitive 49.632522849397134, Balanced
51.809236850031304, Conservative 59.465890915130174. Risk categories stay
Low/Medium/High/Critical at 25/50/75. Scores are not attack probabilities.

TASK01 cleaning retains labels outside inference and nulls invalid measurements.
The existing model applies log1p to rate/count/variation and identity to mean/ratio,
then frozen-domain saturation. Five exact leading-space column names are authoritative;
live packets cannot directly supply all dataset columns. There was no previous
packet-capture, flow-state or monitoring component. Python pytest, Vitest, TypeScript
and Vite infrastructure were reused. No fitting or dataset acquisition was run.

## Design decisions and feature compatibility

Responsibilities are separated into lazy capture/discovery/decoding, pure flow
statistics, session/queue/inference management, local HTTP API and a React page.
Scapy 2.8.0 is an optional pinned dependency in `requirements-live.txt`, outside
normal setup. Npcap/libpcap remains an explicit OS prerequisite. Opening the app or
monitoring page does not open a capture socket. Synthetic replay is a separate,
explicitly named mode, not a fallback presented as genuine captured traffic.

`docs/realtime-monitoring.md` contains the feature-by-feature mapping, source
references, units and compatibility assessment. The versioned live profile uses
transport-payload lengths, sample backward std, first-observation forward direction,
integer backward/forward ratio and a duplicated first length in the mean to follow
the inspected legacy reference. It is not a generic frame-length substitution.
The precise 2017 exporter build/timeout is unknown; exact compatibility remains
unverified and every result is labeled experimental.

Only required features and inspectable directional counts/byte totals/duration are
computed. Unsupported features are not filled with zero. Singleton/equal-timestamp
flows abstain because rate is unavailable. Truncation, fragments, timestamp disorder,
queue loss and capture errors are surfaced. Conservative quality gating withholds
scores after capture-quality loss in the current session. Inference errors remain
separate from capture-quality errors. No label, day, identifier or payload is an
inference input. All three policies share the same frozen score.

The software keeps at most 4,096 active flows, a 4,096-item metadata queue, 200
recent results and 20 recent errors. Online moments avoid retaining packets. TCP
RST/bidirectional FIN, idle 15s, maximum age 120s, tuple restart, eviction and stop
cover lifecycle. Stop/restart/maximum/eviction segments are labeled provisional;
closed observed segments do not prove complete connection capture. The worker
expires idle flows even during silence, drains on stop, releases capture resources
and is joined on ASGI shutdown. One backend worker/process is supported.

Controls require loopback peer, allowed browser Origin and a process-local secret
header; cross-site requests are rejected. No arbitrary BPF, file path, payload,
remote interface selection or capture command is accepted. Capture uses the exact
enumerated interface, fixed IPv4 TCP/UDP filter, `promisc=False` and `store=False`.
No payload persistence, credentials, injection, service installation or automatic
capture restart exists. Monitoring continues across browser navigation until stop
or server shutdown; the UI explains that lifecycle.

## Actual validation results

| Check | Result |
|---|---|
| Complete Python suite | **227 passed, 0 failed**; previous 202 retained, 25 new cases |
| Complete frontend suite | **21 passed, 0 failed**; previous 15 retained, 6 new cases |
| TypeScript / production build | Passed; existing lockfile/dependencies reused |
| Native HTTP integration | Passed through running Vite proxy and FastAPI |
| Packet replay | 6 serialized synthetic packets → 1 bidirectional TCP + 1 bidirectional UDP flow |
| Policy parity | All 6 flow/policy analyses exactly equal direct WebService inference |
| Offline regression | Actual HTTP offline score matches original catalog |
| Startup behavior | Stopped initially; no capture socket opened automatically |
| Cleanup | Monitoring worker shutdown and owned app processes released ports 8000/5173 |
| Optional capture absence | Npcap-unavailable response; offline inference still works |
| Real captured packets | **Not run — Npcap unavailable** |
| Native Linux/macOS capture | **Not run** |

Independent TCP arithmetic reference: four packets over 300,000µs, two forward/two
backward, payloads 10/20/40/0. Packet rate 13.333333333333334/s, legacy mean 16 bytes,
backward sample std √200 = 14.142135623730951 bytes, integer ratio 1. The actual
replay score is **15.998872142222703 / Low**. UDP has two packets over 100,000µs,
rate 20/s, one forward packet, legacy mean 16 bytes, backward std 0, ratio 1;
score **17.837383028039127 / Low**. These are synthetic test observations, not
captured traffic, and no High/Critical examples are fabricated.

Tests cover directional assignment, UDP/TCP separation, units, sample variance,
FIN/RST/SYN lifecycle, idle/max/eviction, malformed/fragmented/truncated/unsupported
packets, insufficient-data handling, loss gating, capture/inference failures,
dead-socket detection, cleanup failure, API security/validation, policy parity,
serialization over HTTP, frontend states and existing-app navigation. Missing
optional Scapy is tested without disabling offline analysis. No external target,
scan, attack, generated training dataset or full-data experiment was used.

## Reproduction and artifacts

1. Install optional capture dependencies as documented; ordinary `make` still works
   without them. Do not reinstall healthy packages unnecessarily.
2. Run `make test` and `make build`.
3. With free ports, run `.venv/Scripts/python.exe scripts/validate_realtime.py`
   (POSIX: `.venv/bin/python`). Default is explicitly synthetic replay.
4. Optional `--live-interface "exact loopback ID"` permits a future separately
   selected real localhost UDP capture test after driver/permission setup.

`integration.json` is actual bounded HTTP evidence. `test_run.txt` and `build.txt`
store normalized command output. `validation.json` records source versions,
historical/source preservation, archive hash, exact test counts and limitations.
`scripts/validate_realtime_integrity.py` rechecks stored local evidence and hashes;
it is an explicit development audit, not part of normal startup. The small React
fixture contains documentation IPs, deterministic synthetic features and actual
engine output; its runtime token/session metadata are replaced with test-only IDs.

Added files: `requirements-live.txt`; `src/fuzzy_network_risk/realtime/` modules;
`web/src/LiveTraffic.tsx`, its tests and small JSON fixture; `tests/test_realtime.py`;
two validation scripts; monitoring documentation and these new reports.
Modified files: API lifespan/routes, App navigation/about text, scoped CSS, one
additional App test, README and packet-capture ignore patterns. Existing models,
datasets, LFS settings, preprocessing, launchers, lockfiles and historical reports
are preserved. Large/generated captures and temporary logs are ignored.

## Remaining risks and final status

The replay-capable educational integration satisfies the functional completion
criteria through the explicitly permitted deterministic path. Physical capture is
implemented but still needs native driver/permissions and independent validation.
Exact exporter parity requires authorized reference PCAPs and the original exporter
build. Capture drops below Python, NIC offload, mid-connection start, timeout/split
differences, trailing FIN ACKs and loopback duplicate/control traffic can materially
change features. Queue loss is measured, kernel/NIC drops are not. A valid numeric
score does not prove a correct or complete network observation.

The unchanged model's previously documented temporal and scenario-generalization
weaknesses continue to apply. No independent real-network performance evaluation,
accuracy improvement or production-readiness claim is made. No remote Git operation
was executed. One local implementation commit is created after validation; its
hash is supplied in the final response rather than self-embedded in this report.
