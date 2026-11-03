"""Lazy optional Scapy backend; no sockets or privileged imports at app startup."""
import sys
import threading
from .flows import Packet, PacketRejected


class CaptureError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def scapy_api():
    try:
        from scapy import all as api
        return api
    except ImportError as exc:
        raise CaptureError('capture_unavailable', 'Scapy eksik. Yerel .venv içine requirements-live.txt kurun; çevrimdışı analiz kullanılabilir.') from exc


def interfaces():
    api = scapy_api()
    if sys.platform == 'win32' and not api.conf.use_pcap:
        raise CaptureError('capture_unavailable', 'Npcap kullanılamıyor. Npcap kurulumu ve yakalama izinlerini kontrol edin; çevrimdışı analiz kullanılabilir.')
    api.conf.ifaces.reload()
    return [{'id': str(i.network_name), 'name': str(i.name), 'description': str(i.description)}
            for i in api.conf.ifaces.values() if i.network_name]


def decode(raw):
    """Read outer IPv4 only. Reject fragments, truncation, tunnels and bad lengths.

    Retain scalar transport-payload LENGTH only, never contents. IPv6 is explicitly
    unsupported by this version (the legacy reference has different IPv6 behavior).
    """
    from scapy.layers.inet import IP, TCP, UDP
    from scapy.layers.inet6 import IPv6
    try:
        network = raw if isinstance(raw, (IP, IPv6)) else raw.payload
        if isinstance(network, IPv6):
            raise PacketRejected('unsupported_ipv6')
        if not isinstance(network, IP):
            raise PacketRejected('unsupported_network')
        if network.frag or int(network.flags) & 1:
            raise PacketRejected('fragmented_ipv4')
        transport = network.payload
        if not isinstance(transport, (TCP, UDP)):
            raise PacketRejected('unsupported_protocol')
        # Production capture has parsed wire headers; synthetic tests serialize first.
        ihl = int(network.ihl) * 4
        total = int(network.len)
        if ihl < 20 or total < ihl or len(bytes(network)) < total:
            raise PacketRejected('truncated_or_malformed_packet')
        if isinstance(transport, TCP):
            header = int(transport.dataofs) * 4
            length = total - ihl - header
            if header < 20 or length < 0:
                raise PacketRejected('malformed_tcp')
            protocol, flags = 'TCP', int(transport.flags)
        else:
            length = int(transport.len) - 8
            if length < 0 or int(transport.len) != total - ihl:
                raise PacketRejected('malformed_udp')
            protocol, flags = 'UDP', 0
        # Check transport bytes, excluding link padding, without saving them.
        if len(bytes(transport)) < (header if protocol == 'TCP' else 8) + length:
            raise PacketRejected('truncated_transport')
        return Packet(int(raw.time * 1_000_000), network.src, network.dst,
                      int(transport.sport), int(transport.dport), protocol, length, flags)
    except PacketRejected:
        raise
    except (AttributeError, TypeError, ValueError, OverflowError, IndexError) as exc:
        raise PacketRejected('malformed_packet') from exc


class ScapySource:
    def __init__(self, interface):
        self.interface = interface
        self.stop_event = threading.Event()
        self.done = threading.Event()
        self.thread = None
        self.socket = None

    def start(self, on_packet, on_error):
        api = scapy_api()
        try:
            # Open synchronously: permission/driver failures are API errors, not a
            # false successful session. No promiscuous mode or arbitrary BPF input.
            self.socket = api.conf.L2listen(iface=self.interface, promisc=False, filter='ip and (tcp or udp)')
        except Exception as exc:
            denied = isinstance(exc, PermissionError) or any(word in str(exc).lower() for word in ('permission', 'denied', 'not permitted', 'access is denied'))
            raise CaptureError('permission_denied' if denied else 'capture_unavailable',
                               'Yakalama izni reddedildi.' if denied else 'Yakalama soketi açılamadı; Npcap/libpcap ve arayüzü kontrol edin.') from exc

        def run():
            try:
                def receive(raw):
                    try: on_packet(decode(raw))
                    except PacketRejected as exc: on_error(str(exc), False)
                while not self.stop_event.is_set():
                    api.sniff(opened_socket=self.socket, store=False, timeout=.25, prn=receive)
                    # Scapy may log and swallow a dead socket exception. Do not
                    # leave a busy loop masquerading as healthy monitoring.
                    if getattr(self.socket, 'closed', False) and not self.stop_event.is_set():
                        raise CaptureError('capture_failed', 'Capture socket closed')
            except Exception:
                if not self.stop_event.is_set(): on_error('capture_failed', True)
            finally:
                try: self.socket.close()
                except Exception: on_error('cleanup_failed', True)
                finally: self.done.set()
        self.thread = threading.Thread(target=run, name='local-packet-capture', daemon=True)
        try: self.thread.start()
        except BaseException:
            self.socket.close()
            self.done.set()
            raise

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                try: self.socket.close()
                except Exception as exc: raise CaptureError('cleanup_failed', 'Yakalama soketi kapatılamadı; uygulamayı durdurun.') from exc
                self.thread.join(timeout=3)
            if self.thread.is_alive(): raise CaptureError('cleanup_failed', 'Yakalama iş parçacığı kapanmadı; uygulamayı durdurun.')


def reference_packets():
    """Deterministic SYN/data/response/reset plus UDP. TEST traffic, never sent."""
    api = scapy_api()
    specifications = [
        (0, 'TCP', False, 10, 'S'), (100_000, 'TCP', True, 20, 'A'),
        (200_000, 'TCP', True, 40, 'A'), (300_000, 'TCP', False, 0, 'R'),
        (400_000, 'UDP', False, 12, ''), (500_000, 'UDP', True, 24, ''),
    ]
    for delta, protocol, reverse, size, flags in specifications:
        src, dst = ('192.0.2.2', '192.0.2.1') if reverse else ('192.0.2.1', '192.0.2.2')
        sport, dport = (443, 45000) if reverse else (45000, 443)
        transport = api.TCP(sport=sport, dport=dport, flags=flags) if protocol == 'TCP' else api.UDP(sport=sport, dport=dport)
        raw = api.IP(bytes(api.IP(src=src, dst=dst)/transport/(b'x'*size)))
        raw.time = (1_700_000_000_000_000 + delta) / 1_000_000
        yield raw


class ReplaySource:
    """Explicit fixed synthetic replay, never discovered/presented as an interface."""
    def __init__(self):
        self.stop_event, self.done = threading.Event(), threading.Event()
        self.thread = None

    def start(self, on_packet, on_error):
        scapy_api()  # Report a missing optional dependency before starting.
        def run():
            try:
                for raw in reference_packets():
                    if self.stop_event.wait(.05): break
                    on_packet(decode(raw))
            except Exception: on_error('replay_failed', True)
            finally: self.done.set()
        self.thread = threading.Thread(target=run, name='explicit-synthetic-replay', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=3)
