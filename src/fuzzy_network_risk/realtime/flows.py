"""Bounded bidirectional IPv4 TCP/UDP flow statistics, no packet retention.

Profile cic-legacy-v1 follows CICFlowMeter's payload-length statistics, sample
backward std, integer direction ratio and duplicate first length in the mean.
Exact equivalence to the unspecified 2017 exporter build is NOT established.
"""

import ipaddress
import math
from collections import OrderedDict
from dataclasses import dataclass, field

PROFILE = 'cic-legacy-v1-experimental'


# Packet-level capture impairments. A flow carrying any of these codes missed
# at least one of its packets, so its statistics are incomplete and it abstains.
# Impairment is attributed to the affected flow(s) only; it never disables
# scoring for unrelated or later flows (cf. per-connection loss accounting in
# Zeek ``missed_bytes`` / Suricata decoder events rather than sensor-wide flags).
QUEUE_LOSS = 'capture_queue_loss'  # this flow's own packet was dropped
ENDPOINT_REJECTION = 'endpoint_packet_rejected'  # unusable packet between the same hosts
UNATTRIBUTED_ERROR = 'concurrent_capture_error'  # unattributable error while flow was active
IMPAIRMENT_CODES = (QUEUE_LOSS, ENDPOINT_REJECTION, UNATTRIBUTED_ERROR)


class PacketRejected(ValueError):
    """Rejected packet. ``scope`` optionally attributes it to a host pair.

    ``scope`` is ``(protocol, address_a, address_b)`` when the IPv4 header was
    readable, otherwise ``None`` (unattributable). ``protocol`` is ``'TCP'``,
    ``'UDP'`` or ``None`` when the transport protocol is unknown.
    """

    def __init__(self, code, scope=None):
        super().__init__(code)
        self.code = code
        self.scope = scope


@dataclass(frozen=True)
class Packet:
    timestamp_us: int
    src: str
    dst: str
    sport: int
    dport: int
    protocol: str
    payload_bytes: int
    flags: int = 0

    def __post_init__(self):
        if self.protocol not in ('TCP', 'UDP'):
            raise PacketRejected('unsupported_protocol')
        if any(type(x) is not int for x in (self.timestamp_us, self.sport, self.dport, self.payload_bytes, self.flags)):
            raise PacketRejected('malformed_packet')
        if self.timestamp_us < 0 or not 0 <= self.payload_bytes <= 65535 or not 0 <= self.flags <= 255:
            raise PacketRejected('malformed_packet')
        if not (0 <= self.sport <= 65535 and 0 <= self.dport <= 65535):
            raise PacketRejected('malformed_packet')
        try:
            if any(ipaddress.ip_address(ip).version != 4 for ip in (self.src, self.dst)):
                raise PacketRejected('unsupported_ipv6')
        except ValueError as exc:
            raise PacketRejected('unsupported_or_invalid_ip') from exc

    @property
    def key(self):
        return self.protocol, tuple(sorted(((self.src, self.sport), (self.dst, self.dport))))


@dataclass
class Moments:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0
    total: int = 0

    def add(self, value):
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.total += value

    @property
    def std(self):
        return math.sqrt(max(0.0, self.m2 / (self.n - 1))) if self.n > 1 else 0.0


@dataclass
class Flow:
    first: Packet
    created_clock: float
    last_clock: float
    last_us: int
    forward: Moments = field(default_factory=Moments)
    backward: Moments = field(default_factory=Moments)
    lengths: Moments = field(default_factory=Moments)
    fins: set = field(default_factory=set)
    errors: set = field(default_factory=set)

    def add(self, packet, clock):
        direction = (packet.src, packet.sport) == (self.first.src, self.first.sport)
        if packet.timestamp_us < self.last_us:
            self.errors.add('out_of_order_timestamp')
        self.last_us = max(self.last_us, packet.timestamp_us)
        self.last_clock = clock
        if not self.lengths.n:
            self.lengths.add(packet.payload_bytes)  # Versioned legacy exporter behavior.
        self.lengths.add(packet.payload_bytes)
        (self.forward if direction else self.backward).add(packet.payload_bytes)
        if packet.protocol == 'TCP' and packet.flags & 1:
            self.fins.add(direction)

    def finish(self, reason):
        duration = self.last_us - self.first.timestamp_us
        if duration <= 0:
            self.errors.add('zero_duration_rate_unavailable')
        features = {
            ' Flow Packets/s': (self.forward.n + self.backward.n) * 1_000_000 / duration if duration > 0 else None,
            ' Total Fwd Packets': self.forward.n,
            ' Packet Length Mean': self.lengths.mean,
            ' Bwd Packet Length Std': self.backward.std,
            ' Down/Up Ratio': self.backward.n // self.forward.n,
        }
        return {
            'source': self.first.src,
            'destination': self.first.dst,
            'source_port': self.first.sport,
            'destination_port': self.first.dport,
            'protocol': self.first.protocol,
            'started_us': self.first.timestamp_us,
            'ended_us': self.last_us,
            'duration_us': duration,
            'forward_packets': self.forward.n,
            'backward_packets': self.backward.n,
            'forward_payload_bytes': self.forward.total,
            'backward_payload_bytes': self.backward.total,
            'finalization': reason,
            'provisional': reason in ('capacity_eviction', 'maximum_duration', 'monitoring_stopped', 'new_syn'),
            'features': features,
            'compatibility_profile': PROFILE,
            'compatibility': 'experimental_not_exporter_validated',
            'quality_errors': sorted(self.errors),
        }


def _hosts(key):
    return frozenset((key[1][0][0], key[1][1][0]))


class FlowTable:
    """Single-worker-owned LRU table. Monotonic clock controls idle/maximum age."""

    def __init__(self, idle_seconds=15.0, max_seconds=120.0, capacity=4096):
        if not 0 < idle_seconds <= max_seconds or capacity < 1:
            raise ValueError('Invalid flow limits')
        self.idle, self.maximum, self.capacity = idle_seconds, max_seconds, capacity
        self.flows = OrderedDict()
        # Pending impairments for flows whose packets have not been tabled yet,
        # e.g. a lost or rejected FIRST packet. Each lives for one idle period;
        # the dictionary is deduplicated and bounded like the flow table itself.
        self.taints = OrderedDict()  # (kind, identity, code) -> expiry clock

    def impair(self, code, clock, key=None, scope=None):
        """Mark flows that missed a packet; return the number of flows marked.

        ``key``: exact flow key (packet dropped after decoding).
        ``scope``: ``(protocol, host, host)`` of a rejected but readable packet;
        ``protocol`` ``None`` matches TCP and UDP flows between those hosts.
        Neither: unattributable; every currently active flow is marked.
        Attributed impairments also taint a flow created within one idle period,
        because the missed packet may have been that flow's first packet.
        """
        if code not in IMPAIRMENT_CODES:
            raise ValueError('Unknown impairment code')
        if key is not None:
            taint = ('key', key, code)
            match = lambda candidate: candidate == key
        elif scope is not None:
            protocol, hosts = scope[0], frozenset(scope[1:])
            taint = ('hosts', (protocol, hosts), code)
            match = lambda candidate: (protocol is None or candidate[0] == protocol) and _hosts(candidate) == hosts
        else:
            taint, match = None, lambda candidate: True
        marked = 0
        for candidate, flow in self.flows.items():
            if match(candidate):
                flow.errors.add(code)
                marked += 1
        if taint is not None:
            self.taints.pop(taint, None)
            self.taints[taint] = clock + self.idle
            while len(self.taints) > self.capacity:
                self.taints.popitem(last=False)
        return marked

    def _pending_impairments(self, key, clock):
        hosts = _hosts(key)
        identities = [('key', key), ('hosts', (None, hosts)), ('hosts', (key[0], hosts))]
        return {
            code
            for code in IMPAIRMENT_CODES
            for kind, identity in identities
            if self.taints.get((kind, identity, code), clock) > clock
        }

    def expire(self, clock):
        for taint, expiry in list(self.taints.items()):
            if expiry <= clock:
                del self.taints[taint]
        completed = []
        for key, flow in list(self.flows.items()):
            reason = (
                'maximum_duration'
                if clock - flow.created_clock >= self.maximum
                else 'idle_timeout'
                if clock - flow.last_clock >= self.idle
                else None
            )
            if reason:
                completed.append(self.flows.pop(key).finish(reason))
        return completed

    def add(self, packet, clock):
        completed = self.expire(clock)
        key = packet.key
        flow = self.flows.get(key)
        # Reused TCP tuple/new SYN is a new observed connection, not extra data.
        if (
            flow
            and packet.protocol == 'TCP'
            and packet.flags & 2
            and not packet.flags & 16
            and (flow.backward.n or flow.forward.total)
        ):
            completed.append(self.flows.pop(key).finish('new_syn'))
            flow = None
        if flow is None:
            if len(self.flows) >= self.capacity:
                completed.append(self.flows.popitem(last=False)[1].finish('capacity_eviction'))
            flow = Flow(packet, clock, clock, packet.timestamp_us)
            if self.taints:
                flow.errors.update(self._pending_impairments(key, clock))
            self.flows[key] = flow
        flow.add(packet, clock)
        self.flows.move_to_end(key)
        if packet.protocol == 'TCP' and (packet.flags & 4 or len(flow.fins) == 2):
            completed.append(self.flows.pop(key).finish('tcp_reset' if packet.flags & 4 else 'tcp_fin_both_directions'))
        return completed

    def flush(self, reason='monitoring_stopped'):
        results = [flow.finish(reason) for flow in self.flows.values()]
        self.flows.clear()
        self.taints.clear()
        return results
