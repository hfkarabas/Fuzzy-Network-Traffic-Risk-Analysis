# Opt-in real-time network monitoring (TASK 07)

## Scope and evidence

This is an educational local integration of the **unchanged** five-input, 22-rule
Mamdani model and its three frozen alarm policies. It is not a retrained model or
a validated intrusion detector. Capture is opt-in and does not run on application
startup. Offline analysis does not import Scapy or open a capture socket.

The initial TASK07 Windows validation had no usable Npcap provider. Actual localhost
HTTP through Vite/FastAPI, serialized synthetic TCP/UDP packet replay, inference
and React state handling were tested. **Actual captured traffic was not tested.**
Linux/macOS capture paths are implemented but not natively tested. No claim of
real-world detection accuracy or exact CIC-IDS2017 exporter equivalence is made.

## Dependencies and permissions

Normal `make` startup is unchanged. Capture/replay additionally uses the pinned
optional library in `requirements-live.txt`: Scapy 2.8.0. Install into the local venv:

```powershell
make setup
# Existing Windows environment may not contain pip; this command uses launcher pip:
py -m pip --python .venv install -r requirements-live.txt
make
```

```sh
make setup
.venv/bin/python -m pip install -r requirements-live.txt
make
```

No system driver or global package is installed by this application. If local pip
is missing on POSIX, run `.venv/bin/python -m ensurepip` first. Optional Scapy is not
added to ordinary startup's dependency synchronization, so an offline-only clone
does not need capture support. Full packet/replay tests need the optional dependency;
those tests skip explicitly when it is absent.

On Windows install [Npcap from its official site](https://npcap.com/#download),
following the [Npcap user guide](https://npcap.com/guide/npcap-users-guide.html).
Review its license and installation options yourself. Modern Npcap supports
loopback; no legacy loopback-adapter installation is needed for modern software.
An admin-only Npcap installation may require an elevated **capture session**.
Do not elevate ordinary offline use or permanently alter PowerShell execution
policy. The application reports denied capture rather than requesting elevation
or installing drivers. Restart the backend after installing a driver.

Linux generally needs capture socket permissions and libpcap for the fixed BPF
filter; macOS uses libpcap/BPF device permissions. Use OS-approved least-privilege
access. Do not give a shared/general-purpose Python interpreter persistent broad
network capabilities just to run offline analysis. macOS Intel/ARM users should
install architecture-matching native packages. No packet injection is used.

## Backend selection and architecture

Scapy was chosen for maintained cross-platform packet decoding, synthetic packet
fixtures and capture integration. Scapy supports native sockets on some platforms
and Npcap/libpcap backends. Direct pypcap bindings would add native packaging
requirements without removing the driver requirement. A tshark subprocess would
add another system dependency and process/payload-handling surface. None is
installed or silently used as a fallback. See [Scapy usage](https://scapy.readthedocs.io/en/stable/usage.html)
and [sniff API](https://scapy.readthedocs.io/en/stable/api/scapy.sendrecv.html).

```text
Explicit local Start
  → lazy interface discovery + exact interface-ID validation
  → selected non-promiscuous socket (fixed IPv4 TCP/UDP BPF)
  → Scapy decode → scalar packet metadata (no payload content retained)
  → bounded queue → single serial flow worker
  → bidirectional flow statistics → compatibility/quality gate
  → existing WebService.analyze → PolicyRiskModel → MamdaniRiskEngine
  → bounded in-memory results → local HTTP polling → Live Traffic React section
```

The capture callback only extracts timestamp, addresses, ports, protocol, payload
**length**, and TCP flags. Short-lived packet buffers necessarily exist during
decoding; they are not logged, persisted, returned or retained in flow state.
The server does not invoke tcpdump, modify traffic or perform reassembly.

## Authoritative model contract and compatibility

Input column names, including leading spaces, are preserved. The adapter sends
exactly these five numeric inputs to existing preprocessing/inference. The existing
engine applies log1p to rate/count/backward std, identity to mean/ratio, saturates
at frozen membership domains and applies the existing rules and thresholds. No
second normalization or fitted transform is added. Labels are never inputs.

The compatibility profile is `cic-legacy-v1-experimental`. Reference semantics come
from upstream [CICFlowMeter BasicFlow.java](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/BasicFlow.java)
and [PacketReader.java](https://github.com/ahlashkari/CICFlowMeter/blob/master/src/main/java/cic/cs/unb/ca/jnetpcap/PacketReader.java),
inspected on 2026-11-03. The dataset does not identify the exact exporter source
revision. This profile is therefore a transparent compatibility hypothesis.

| Exact input | Extraction from observed segment | Units | Compatibility |
|---|---|---|---|
| `" Flow Packets/s"` | Total observed packets / (last minus first capture timestamp) | packets/s | Formula aligned; zero duration unavailable |
| `" Total Fwd Packets"` | Packets in first-observed endpoint direction | packets | Direction aligned; capture can begin mid-connection |
| `" Packet Length Mean"` | Transport payload-length mean, first observation counted twice | bytes | Legacy convention reproduced; exact 2017 build unverified |
| `" Bwd Packet Length Std"` | Sample std of backward payload lengths; n ≤ 1 gives 0 | bytes | Legacy convention; zero is not missing or proof of uniform traffic |
| `" Down/Up Ratio"` | floor(backward packets / forward packets) | dimensionless | Matches existing integer export contract |

The first-length duplication intentionally follows the referenced legacy exporter,
not ordinary arithmetic packet mean. Header/frame sizes are not substituted.
The reference uses microsecond IPv4 timestamps and payload lengths. This does not
prove equivalence to the training capture's exporter, timeout or OS behavior.

Only required statistics are computed, plus counts, directional payload-byte
totals and duration for inspection. IAT/active/idle distributions, TCP flag counts,
header-length totals and all other 79-column dataset measurements are **not model
inputs** and are not fabricated. FIN/RST/SYN flags are used only for flow lifecycle.
No unavailable measurement is replaced with zero. n≤1 backward std of zero is an
explicit exporter convention; a zero-duration rate instead causes abstention.

IP fragments, truncated/malformed packets, IPv6, non-IP and other transports are
rejected explicitly by decoding. The live BPF filter excludes IPv6/non-TCP/UDP
traffic before callbacks. Rejection counters describe callback-visible packets,
not all interface traffic. IPv6 is deliberately unsupported in v1 because legacy
IPv6 timestamp behavior differs. VLAN/tunnel/reassembly support is not claimed.

## Flow lifecycle and completeness

The key is protocol plus a canonical pair of IPv4 address/port endpoints. First
observed direction is forward; full endpoint comparison handles same-host traffic.
Statistics use constant-memory online moments; individual packets are not saved.

- RST or FIN observed in both directions finalizes a TCP segment.
- A new bare SYN after response/data finalizes a reused tuple. Repeated unanswered
  SYNs stay in the same flow. No TCP sequence/ACK reconstruction is attempted.
- Idle timeout: 15 seconds using monotonic arrival time; maximum segment age:
  120 seconds. A worker sweep runs even with no arriving packets.
- Active table cap: 4,096 flows; oldest last-used entry is finalized on overflow.
- Input queue cap: 4,096 metadata entries; recent results: 200, API defaults to
  latest 50; error history: 20. Risk counts are cumulative for the current session.
- Stop closes the source, drains queued metadata, finalizes active segments and
  joins workers. ASGI shutdown calls the same stop path. Repeated stop is safe;
  a second start while running returns 409. New sessions reset retained results.

Maximum-duration, eviction, tuple-restart and user-stop segments are marked
`provisional=true` and shown as **Partial-flow estimate**. They are finalized observed
segments, not proven completed connections. FIN/RST/idle completion still cannot
prove that the capture saw the initial packet or every packet. Single-packet or
equal-timestamp segments have no finite rate and receive no score. Out-of-order
timestamps also abstain. Inference exceptions are recorded and never produce an
invented score.

### Packet loss and rejected packets (per-flow attribution)

Capture impairments are attributed to the flows that actually missed a packet,
following the per-connection loss accounting of flow monitors such as Zeek
(`missed_bytes`, `capture_loss`) and Suricata decoder events. One bad packet
never stops scoring for the rest of the session; sensor-wide counters
(`queue_dropped_packets`, `rejected_packets`, `capture_errors`, `impaired_flows`)
and the error list report overall capture health separately.

| Event | Attribution | Quality code on the affected flow(s) |
|---|---|---|
| Decoded packet dropped because the bounded queue is full | Exact flow key | `capture_queue_loss` |
| Fragmented, truncated or malformed IPv4 TCP/UDP packet with a readable header | Flows between the same two hosts (same protocol when known) | `endpoint_packet_rejected` |
| Unattributable error (unreadable header, fatal capture failure) | Every flow active at that moment | `concurrent_capture_error` |
| IPv6, non-IP or non-TCP/UDP packet | None: not part of any analyzed flow | — (counted only) |

Impairment events travel through the same queue as packets, so they apply in
arrival order; when the queue is full they fall back to an unordered counter
that the worker applies before processing more packets. Attributed impairments
also mark a flow created with the same key or host pair within one idle timeout
(15 s), because the missed packet may have been that flow's first packet. The
pending set is deduplicated, bounded by the flow-table capacity and cleared
when monitoring stops. An impaired flow abstains (`insufficient_data`) instead
of receiving a score from incomplete statistics; flows created afterwards are
scored normally. A flow already published before a late-applied loss cannot be
retracted.

There is no provisional periodic re-scoring of active flows. Results can be delayed
until timeout, so this is not instantaneous packet attack detection. Final ACKs
after FIN closure may form unscored singleton segments. Idle/maximum settings differ
from an unknown historical exporter configuration. Capture loss below Python,
NIC offload/coalescing, timestamp precision and loopback duplicates remain unmeasured
sources of error. Local API/Vite traffic can itself be observed on loopback; it is
not silently removed. These factors can materially change scores.

## Web interface and lifecycle

Run `make`, open http://127.0.0.1:5173, choose **Live Traffic**. Select a real listed
interface, acknowledge authorization/experimental limits and click **Start
monitoring**. Stop explicitly with **Stop monitoring**. Ordinary startup and opening
the section do not capture. The separate **Sentetik packets replay** source sends
no packets: it decodes six fixed serialized test packets and labels every result
as replay. It is not a hidden fallback or presented as real interface traffic.

Status/results poll every two seconds without overlapping poll requests; unmount
cancels polling. Monitoring intentionally continues when navigating pages/closing
the browser, until explicitly stopped or the local server exits. There is no
service installation, scheduled task, persistence or automatic restart. Use
**one backend process/worker**; multiple Uvicorn workers/reload are unsupported
for monitoring ownership. Existing launchers use one worker.

The UI shows lifecycle state, processed packets, active/finalized/analyzed flows,
abstentions, capture errors, risk distribution, endpoint/port metadata, time,
protocol and completion reason. Flow inspection exposes actual five inputs,
memberships, rules/strengths, explanation and all three policy decisions. Switching
policy does not rerun capture or change fuzzy scores. Results remain session-local
in memory and are not exported by default. No fabricated initial observations or
payload viewer exists.

### Inspecting a flow (TASK 08)

Choose **Inspect flow** in the recent-flow table. The inline detail view retains
the chosen flow even when polling removes it from the recent list. Close it with
**Close flow details**; keyboard focus returns to the trigger or table heading.
Endpoints, ports, duration, finalization reason and inference eligibility appear
above the shared historical/live risk panel. A provisional segment prominently
retains **Partial-flow estimate** and its experimental-score warning.

The five observed values keep their full precision internally; formatted numbers
expose full values on hover. **Membership degrees** uses the same server-sampled
configured curves, scaling and observed-value markers as historical analysis.
**Active rules** shows actual backend rule descriptions, strengths, bars and
consequents. The output plot shows the engine's real 201-point output memberships,
max-aggregated clipped set and centroid marker; no inference runs in TypeScript.
It is supplied by the read-only `POST /api/visualization/output` endpoint using
the existing feature request schema. Its model ID and centroid must match the
selected analysis before it is drawn. A loading/error state never invents a curve.

Sensitive/Balanced/Conservative cards show backend alarm decisions and thresholds;
switching policy preserves the score and membership/output curves. Unavailable or
invalid-flow results retain available metadata and explain abstention without
membership or centroid graphs. Neither the score nor memberships are attack
probabilities. No capture lifecycle, model parameter or alarm threshold changes
were made for these visualizations.

## Local monitoring API

All `/api/live/*` routes require a loopback peer. Browser Origin, when present,
must be exactly localhost/127.0.0.1/[::1] on default HTTP ports 5173 or 8000;
cross-site fetches are denied. No CORS access is enabled. POST controls additionally
require the unpredictable process-local `X-Monitor-Token` returned by local status.
This is local CSRF protection, not authentication against malicious local software.
Do not expose/forward these services or proxy them through an untrusted server.
Use the existing loopback launchers. Interface IDs are selected from discovery,
not shell strings; the user cannot supply arbitrary filters, PCAP paths or payloads.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/live/interfaces` | Enumerate available capture devices; structured unavailable error |
| GET | `/api/live/status?policy=Balanced&limit=50` | State, control token, results, counts, bounded errors |
| POST | `/api/live/start` | `{mode:"capture",interface:"exact listed ID",authorized:true}` or `{mode:"replay",authorized:true}` |
| POST | `/api/live/stop` | Stop and return bounded final status; send JSON `{}` and control token |
| GET | `/api/live/flows` | Recent flow results, policy and limit query supported |
| GET | `/api/live/stats` | Aggregate current-session risk/count information |
| GET | `/api/live/errors` | Last 20 structured capture/inference events |

Missing/invalid request data → 422; invalid interface → 422; duplicate start → 409;
invalid local control/origin/permissions → 403; unavailable driver/dependency or
capture startup failure → 503. Offline endpoints remain available. No raw traceback
or packet content is returned to the UI.

## Reproducible checks and troubleshooting

```sh
make test
make build
# Starts/stops its own loopback services; requires both ports free:
.venv/bin/python scripts/validation/validate_realtime.py
```

On Windows replace `.venv/bin/python` with `.venv/Scripts/python.exe`. The validator
uses actual HTTP/Vite/FastAPI and synthetic replay by default. `--write-frontend-fixture`
refreshes the small, explicitly synthetic React response fixture. Optional
`--live-interface "exact loopback ID"` enables a separately authorized actual capture
test using only ephemeral localhost UDP echo sockets. It refuses a device whose
description/name does not identify loopback. No remote probes/scans/attacks occur.

- **Npcap/Scapy unavailable:** install optional components manually, restart server,
  click refresh. Offline analysis and explanatory UI remain usable.
- **Permission denied:** review capture-specific OS/driver permissions. Application
  startup itself never requires elevation.
- **Waiting/no flows:** check selected interface and IPv4 traffic; wait for TCP
  completion or idle timeout. Zero traffic legitimately produces no results.
- **Insufficient data:** inspect the flow's quality codes and the session's
  queue-loss/rejection counters. Only affected flows abstain; persistent loss
  indicates capture load. Measurements are never imputed.
- **403 control error:** refresh status in the local default-origin application;
  do not enable unrestricted CORS or remote binding as a workaround.
- **Cleanup failed:** stop the backend process; do not launch another capture until
  its socket/thread has exited. This state blocks new sessions while resources remain.

See `reports/realtime/task07_report.md` and `integration.json` for actual validation
scope. Missing independent captured-PCAP/exporter validation and the model's known
temporal/generalization failures must remain visible in any future demonstration.
