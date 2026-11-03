"""One opt-in session, bounded metadata queue, serial flow/inference worker."""
from collections import Counter, deque
from copy import deepcopy
import queue
import secrets
import threading
import time
from . import capture
from .flows import FlowTable, PROFILE

POLICIES = ('Sensitive', 'Balanced', 'Conservative')


class Monitor:
    def __init__(self, service, source_factory=None, interface_provider=None, *, capacity=4096, retention=200, queue_size=4096):
        self.service = service
        self.source_factory = source_factory or (lambda mode, interface: capture.ReplaySource() if mode == 'replay' else capture.ScapySource(interface))
        self.interface_provider = interface_provider or capture.interfaces
        self.capacity, self.retention, self.queue_size = capacity, retention, queue_size
        self.control = threading.Lock()
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.source = self.worker = None
        self.stop_event = threading.Event()
        self.state, self.mode, self.interface = 'stopped', None, None
        self.rows, self.errors = deque(maxlen=retention), deque(maxlen=20)
        self.counts = Counter()
        self.risks = {policy: Counter() for policy in POLICIES}
        self.active = 0
        self.session = None

    def discovery(self):
        try: return {'available': True, 'interfaces': self.interface_provider(), 'error': None}
        except capture.CaptureError as exc: return {'available': False, 'interfaces': [], 'error': {'code': exc.code, 'message': str(exc)}}
        except Exception: return {'available': False, 'interfaces': [], 'error': {'code': 'capture_unavailable', 'message': 'Arayüzler okunamadı; yakalama sürücüsünü kontrol edin.'}}

    def error(self, code, fatal=False):
        with self.lock:
            self.counts['inference_errors' if code == 'inference_failed' else 'rejected_packets' if not fatal else 'capture_errors'] += 1
            if code not in ('unsupported_ipv6', 'unsupported_network', 'unsupported_protocol', 'inference_failed'):
                self.counts['quality_events'] += 1
            self.errors.append({'code': code, 'time': time.time(), 'fatal': fatal})
            if fatal:
                self.state = 'cleanup_failed' if code == 'cleanup_failed' else 'capture_failed'
                self.stop_event.set()

    def start(self, mode, interface=None):
        with self.control:
            source_thread = getattr(self.source, 'thread', None)
            if (self.worker and self.worker.is_alive()) or (source_thread and source_thread.is_alive()):
                raise capture.CaptureError('already_running', 'İzleme zaten açık. Önce durdurun.')
            if mode not in ('capture', 'replay'):
                raise capture.CaptureError('invalid_mode', 'Geçersiz izleme modu.')
            if mode == 'capture':
                available = self.discovery()
                if not available['available']:
                    error = available['error']
                    with self.lock:
                        self.state = error['code']
                        self.errors.append({**error, 'time': time.time(), 'fatal': True})
                    raise capture.CaptureError(error['code'], error['message'])
                if interface not in {item['id'] for item in available['interfaces']}:
                    raise capture.CaptureError('invalid_interface', 'Listeden geçerli bir arayüz seçin.')
            elif interface is not None:
                raise capture.CaptureError('invalid_interface', 'Replay modu ağ arayüzü kullanmaz.')
            self.queue = queue.Queue(maxsize=self.queue_size)
            self.table = FlowTable(capacity=self.capacity)
            self.stop_event = threading.Event()
            with self.lock:
                self.rows.clear(); self.errors.clear(); self.counts.clear()
                self.risks = {policy: Counter() for policy in POLICIES}
                self.state, self.mode, self.interface = 'starting', mode, interface
                self.session, self.active = secrets.token_hex(8), 0
            self.source = self.source_factory(mode, interface)
            try:
                self.source.start(self.accept, self.error)
                with self.lock:
                    if not self.stop_event.is_set(): self.state = 'waiting_for_flows'
                self.worker = threading.Thread(target=self._run, name='flow-risk-worker', daemon=True)
                self.worker.start()
            except Exception as exc:
                self.stop_event.set()
                self.source.stop()
                with self.lock:
                    self.state = exc.code if isinstance(exc, capture.CaptureError) else 'capture_failed'
                    self.errors.append({'code': self.state, 'message': str(exc) if isinstance(exc, capture.CaptureError) else 'İzleme başlatılamadı.', 'time': time.time(), 'fatal': True})
                if isinstance(exc, capture.CaptureError): raise
                raise capture.CaptureError('capture_failed', 'İzleme başlatılamadı.') from exc
            return self.snapshot()

    def accept(self, packet):
        if self.stop_event.is_set(): return
        try: self.queue.put_nowait((packet, time.monotonic()))
        except queue.Full:
            with self.lock:
                self.counts['queue_dropped_packets'] += 1
                if not any(e['code'] == 'queue_overflow' for e in self.errors):
                    self.errors.append({'code': 'queue_overflow', 'time': time.time(), 'fatal': False})

    def _publish(self, row):
        with self.lock:
            self.state = 'analyzing' if not self.stop_event.is_set() else self.state
            if self.counts['queue_dropped_packets']:
                row['quality_errors'].append('session_capture_queue_loss')
            if self.counts['quality_events']:
                row['quality_errors'].append('session_unusable_packet_or_capture_error')
        predictions = {}
        try:
            if not row['quality_errors']:
                predictions = {policy: self.service.analyze(row['features'], policy) for policy in POLICIES}
            status = 'insufficient_data' if row['quality_errors'] else 'ok' if all(p['status'] == 'ok' for p in predictions.values()) else 'inference_failed'
        except Exception:
            status = 'inference_failed'
            self.error('inference_failed')
        with self.lock:
            self.counts['finalized_flows'] += 1
            self.counts[status] += 1
            row.update(id=f'{self.session}-{self.counts["finalized_flows"]}', observed_at=time.time(), status=status,
                       predictions=predictions, observation_mode=self.mode)
            self.rows.appendleft(row)
            if status == 'ok':
                for policy, prediction in predictions.items():
                    self.risks[policy][prediction['risk_level']] += 1
                    self.risks[policy]['alerts'] += int(prediction['alert'])
            elif status == 'inference_failed':
                self.errors.append({'code': 'inference_failed', 'time': time.time(), 'fatal': False})

    def _run(self):
        try:
            while True:
                try:
                    packet, clock = self.queue.get(timeout=.2)
                    with self.lock: self.counts['packets'] += 1
                    for row in self.table.add(packet, clock): self._publish(row)
                except queue.Empty:
                    for row in self.table.expire(time.monotonic()): self._publish(row)
                with self.lock: self.active = len(self.table.flows)
                if (self.stop_event.is_set() or self.source.done.is_set()) and self.queue.empty(): break
            reason = 'replay_completed' if self.mode == 'replay' and not self.stop_event.is_set() else 'monitoring_stopped'
            for row in self.table.flush(reason): self._publish(row)
        except Exception:
            self.error('flow_worker_failed', True)
        finally:
            try: self.source.stop()
            except Exception: self.error('cleanup_failed', True)
            self.table.flows.clear()
            with self.lock:
                self.active = 0
                if self.state not in ('capture_failed', 'cleanup_failed'): self.state = 'stopped'

    def stop(self):
        with self.control:
            self.stop_event.set()
            if self.source:
                try: self.source.stop()
                except capture.CaptureError:
                    self.error('cleanup_failed', True)
                    raise
            if self.worker:
                self.worker.join(timeout=8)
                if self.worker.is_alive():
                    raise capture.CaptureError('cleanup_failed', 'Analiz iş parçacığı kapanmadı; uygulamayı durdurun.')
            with self.lock:
                if self.state not in ('capture_failed', 'cleanup_failed'): self.state = 'stopped'
            return self.snapshot()

    def snapshot(self, policy='Balanced', limit=50):
        if policy not in POLICIES: raise ValueError('Unknown policy')
        with self.lock:
            rows = []
            for original in list(self.rows)[:limit]:
                row = {key: value for key, value in original.items() if key != 'predictions'}
                row['analysis'] = original['predictions'].get(policy)
                row['policy_comparison'] = {p: {'risk_score': v['risk_score'], 'risk_level': v['risk_level'], 'alert': v['alert'], 'threshold': self.service.models[p].threshold}
                                            for p, v in original['predictions'].items()}
                rows.append(row)
            return deepcopy({'state': self.state, 'running': bool(self.worker and self.worker.is_alive()),
                'session_id': self.session, 'mode': self.mode, 'interface': self.interface,
                'active_flows': self.active, 'counts': dict(self.counts), 'risk_distribution': dict(self.risks[policy]),
                'policy': policy, 'flows': rows, 'errors': list(self.errors), 'control_token': self.token,
                'compatibility_profile': PROFILE, 'retention_limit': self.retention, 'active_limit': self.capacity,
                'notice': 'Tamamlanan gözlemlenmiş akışlar; deneysel CIC uyumu. Puan saldırı olasılığı değildir. Paket kaybı/offload ve eksik başlangıç sonuçları etkiler.'})
