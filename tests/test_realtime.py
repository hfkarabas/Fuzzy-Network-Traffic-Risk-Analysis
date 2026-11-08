"""Independent arithmetic references and opt-in lifecycle/security regressions."""
import math
import threading
import time
import pytest
from fastapi.testclient import TestClient
from fuzzy_network_risk.realtime.flows import (Packet, PacketRejected, FlowTable, Moments, QUEUE_LOSS,
                                               ENDPOINT_REJECTION, UNATTRIBUTED_ERROR)
from fuzzy_network_risk.realtime.capture import CaptureError, decode, reference_packets
from fuzzy_network_risk.realtime.monitor import Monitor
from fuzzy_network_risk.webapp.api import create_app
from fuzzy_network_risk.webapp.service import WebService


def packet(t=0, reverse=False, size=10, protocol='TCP', flags=16, sport=1234, hosts=('192.0.2.1', '192.0.2.2')):
    client, server = hosts
    return Packet(t, server if reverse else client, client if reverse else server,
                  443 if reverse else sport, sport if reverse else 443, protocol, size, flags)


def wait(predicate):
    deadline = time.monotonic()+5
    while not predicate() and time.monotonic()<deadline: time.sleep(.01)
    assert predicate()


@pytest.fixture(scope='module')
def service(): return WebService()


def test_bidirectional_reference_units_and_legacy_mean():
    table = FlowTable()
    packets = [packet(0, size=10), packet(100_000, True, 20), packet(200_000, True, 40), packet(300_000, size=0, flags=4)]
    rows = []
    for i, p in enumerate(packets): rows += table.add(p, i*.1)
    assert len(rows)==1 and not table.flows
    row = rows[0]; features = row['features']
    assert row['forward_packets']==row['backward_packets']==2
    assert row['forward_payload_bytes']==10 and row['backward_payload_bytes']==60
    assert features[' Flow Packets/s']==pytest.approx(4/.3)
    assert features[' Packet Length Mean']==(10+10+20+40+0)/5
    assert features[' Bwd Packet Length Std']==pytest.approx(math.sqrt(200))
    assert features[' Down/Up Ratio']==1 and row['duration_us']==300_000
    assert row['finalization']=='tcp_reset' and not row['provisional']


def test_udp_direction_and_integer_ratio():
    table = FlowTable()
    for i, reverse in enumerate([False,False,False,True,True]):
        assert not table.add(packet(i*100,reverse,protocol='UDP'),i*.1)
    row = table.flush()[0]
    assert row['forward_packets']==3 and row['backward_packets']==2
    assert row['features'][' Down/Up Ratio']==0
    assert row['features'][' Bwd Packet Length Std']==0


def test_fin_half_close_then_both_directions():
    table = FlowTable()
    assert not table.add(packet(flags=1),0)
    assert not table.add(packet(100,True),.1)
    rows=table.add(packet(200,True,flags=1),.2)
    assert len(rows)==1 and rows[0]['finalization']=='tcp_fin_both_directions'


def test_tcp_syn_retransmission_and_tuple_reuse():
    table=FlowTable()
    assert not table.add(packet(size=0,flags=2),0)
    assert not table.add(packet(100,size=0,flags=2),.1)
    assert not table.add(packet(200,True,size=0,flags=18),.2)
    rows=table.add(packet(300,size=0,flags=2),.3)
    assert rows[0]['finalization']=='new_syn'
    assert table.flush()[0]['forward_packets']==1


def test_idle_maximum_capacity_and_empty():
    table=FlowTable(idle_seconds=1,max_seconds=2,capacity=1)
    assert table.expire(10)==[] and table.flush()==[]
    table.add(packet(),0)
    rows=table.add(packet(100,sport=9999),.5)
    assert rows[0]['finalization']=='capacity_eviction' and rows[0]['provisional']
    assert table.expire(1)==[]
    assert table.expire(1.5)[0]['finalization']=='idle_timeout'
    table.add(packet(),3)
    table.add(packet(100),3.9); table.add(packet(200),4.8)
    assert table.expire(5)[0]['finalization']=='maximum_duration'


def test_no_fabricated_rate_and_out_of_order():
    table=FlowTable(); table.add(packet(100),0)
    row=table.flush()[0]
    assert row['features'][' Flow Packets/s'] is None
    assert 'zero_duration_rate_unavailable' in row['quality_errors']
    table.add(packet(200),0); table.add(packet(100,True),.1)
    assert 'out_of_order_timestamp' in table.flush()[0]['quality_errors']


@pytest.mark.parametrize('change',[{'payload_bytes':-1},{'sport':65536},{'timestamp_us':float('nan')},{'protocol':'ICMP'},{'src':'broken'},{'src':'::1'}])
def test_invalid_packet_metadata(change):
    values=packet().__dict__|change
    with pytest.raises(PacketRejected): Packet(**values)


def test_welford_sample_std():
    moments=Moments()
    for value in [0,100,200]: moments.add(value)
    assert moments.std==100 and moments.mean==100 and moments.total==300


def test_actual_scapy_bytes_decode_and_rejection():
    api=pytest.importorskip('scapy.all')
    packets=list(reference_packets())
    assert [decode(p).payload_bytes for p in packets]==[10,20,40,0,12,24]
    cases=[api.IP(bytes(api.IP()/api.ICMP())),api.IP(bytes(api.IP(flags='MF')/api.UDP())),
           api.IP(bytes(api.IP()/api.TCP())[:-1]),api.IPv6()/api.UDP(),api.Ether()/api.ARP()]
    for p in cases:
        with pytest.raises(PacketRejected): decode(p)
    udp=api.IP(bytes(api.IP()/api.UDP()/b'abc')); udp[api.UDP].len=7
    with pytest.raises(PacketRejected): decode(udp)


def test_rejections_carry_host_scope_only_when_header_is_readable():
    api=pytest.importorskip('scapy.all')
    fragment=api.IP(bytes(api.IP(src='192.0.2.1',dst='192.0.2.2',flags='MF')/api.TCP()))
    with pytest.raises(PacketRejected) as info: decode(fragment)
    assert info.value.code=='fragmented_ipv4' and info.value.scope==('TCP','192.0.2.1','192.0.2.2')
    truncated=api.IP(bytes(api.IP(src='192.0.2.3',dst='192.0.2.4')/api.UDP()/b'abc')[:-1])
    with pytest.raises(PacketRejected) as info: decode(truncated)
    assert info.value.scope==('UDP','192.0.2.3','192.0.2.4')
    with pytest.raises(PacketRejected) as info: decode(api.IPv6()/api.UDP())
    assert info.value.code=='unsupported_ipv6' and info.value.scope is None


class ManualSource:
    def __init__(self): self.done=threading.Event(); self.stopped=0
    def start(self,on_packet,on_error): self.accept,self.error=on_packet,on_error
    def stop(self): self.stopped+=1; self.done.set()


def test_monitor_no_autostart_singleton_stop_cleanup_and_adapter(service):
    source=ManualSource()
    monitor=Monitor(service,source_factory=lambda *_:source,interface_provider=lambda:[{'id':'safe'}])
    assert monitor.source is None and not monitor.snapshot()['running']
    monitor.start('capture','safe')
    try:
        with pytest.raises(CaptureError,match='zaten'): monitor.start('capture','safe')
        source.accept(packet()); source.accept(packet(100_000,True,flags=4))
        wait(lambda:monitor.snapshot()['counts'].get('ok')==1)
        snapshots=[monitor.snapshot(policy) for policy in ['Sensitive','Balanced','Conservative']]
        assert len({s['flows'][0]['analysis']['risk_score'] for s in snapshots})==1
        row=snapshots[0]['flows'][0]
        direct=service.analyze(row['features'],'Sensitive')
        assert row['analysis']==direct
        assert row['analysis']['membership_degrees'] and row['analysis']['activated_rules']
    finally: monitor.stop()
    assert not monitor.worker.is_alive() and source.stopped
    assert monitor.stop()['state']=='stopped'


def test_abstention_and_retention(service):
    source=ManualSource(); monitor=Monitor(service,lambda *_:source,lambda:[{'id':'safe'}],retention=2)
    monitor.start('capture','safe')
    for i in range(4): source.accept(packet(i*100,sport=1000+i,flags=4))
    source.done.set(); wait(lambda:not monitor.snapshot()['running'])
    snapshot=monitor.snapshot()
    assert snapshot['counts']['insufficient_data']==4 and len(snapshot['flows'])==2
    assert all(row['analysis'] is None for row in snapshot['flows'])


def test_queue_overflow_impairs_only_the_flow_that_lost_a_packet(service):
    # Deterministic: drive the worker's own steps without a racing thread.
    monitor=Monitor(service,queue_size=1)
    monitor.queue=__import__('queue').Queue(maxsize=1); monitor.table=FlowTable(); monitor.session='test'
    lossy=packet(); clean=packet(hosts=('198.51.100.1','198.51.100.2'))
    monitor.accept(lossy)                     # queued
    monitor.accept(packet(50,True))           # dropped: belongs to the lossy flow
    assert monitor.snapshot()['counts']['queue_dropped_packets']==1
    item,clock=monitor.queue.get_nowait()
    monitor._apply_losses(clock)
    monitor.table.add(item,clock)
    for row in monitor.table.add(packet(100,True,flags=4),clock+.1): monitor._publish(row)
    # A flow that lost nothing is still scored after the overflow.
    monitor.table.add(clean,clock+.2)
    for row in monitor.table.add(packet(100,True,flags=4,hosts=('198.51.100.1','198.51.100.2')),clock+.3): monitor._publish(row)
    flows=monitor.snapshot()['flows']
    assert flows[1]['analysis'] is None and flows[1]['quality_errors']==[QUEUE_LOSS]
    assert flows[0]['status']=='ok' and flows[0]['analysis']['status']=='ok' and flows[0]['quality_errors']==[]
    counts=monitor.snapshot()['counts']
    assert counts['impaired_flows']==1 and counts['ok']==1 and counts['insufficient_data']==1


def _session(service):
    source=ManualSource(); monitor=Monitor(service,lambda *_:source,lambda:[{'id':'safe'}])
    monitor.start('capture','safe')
    return source,monitor


def _finish(source,monitor):
    source.done.set(); wait(lambda:not monitor.snapshot()['running'])
    return {(f['source'],f['source_port']):f for f in monitor.snapshot(limit=200)['flows']}


def test_rejected_packet_impairs_only_flows_between_the_same_hosts(service):
    source,monitor=_session(service)
    other=('198.51.100.1','198.51.100.2')
    source.accept(packet()); source.accept(packet(t=10,hosts=other))
    source.error('fragmented_ipv4',False,('TCP','192.0.2.2','192.0.2.1'))
    source.accept(packet(100_000,True,flags=4)); source.accept(packet(100_010,True,flags=4,hosts=other))
    flows=_finish(source,monitor)
    impaired=flows[('192.0.2.1',1234)]; healthy=flows[('198.51.100.1',1234)]
    assert impaired['status']=='insufficient_data' and impaired['quality_errors']==[ENDPOINT_REJECTION]
    assert healthy['status']=='ok' and healthy['analysis']['risk_score'] is not None
    counts=monitor.snapshot()['counts']
    assert counts['rejected_packets']==1 and counts['impaired_flows']==1 and counts['ok']==1


def test_rejected_first_packet_taints_flow_created_within_idle_period(service):
    source,monitor=_session(service)
    source.error('truncated_transport',False,('TCP','192.0.2.1','192.0.2.2'))
    source.accept(packet()); source.accept(packet(100_000,True,flags=4))
    flows=_finish(source,monitor)
    assert flows[('192.0.2.1',1234)]['quality_errors']==[ENDPOINT_REJECTION]


def test_unattributable_error_impairs_active_flows_but_not_later_flows(service):
    source,monitor=_session(service)
    source.accept(packet(sport=1000))
    source.error('malformed_packet',False)
    source.accept(packet(100_000,True,flags=4,sport=1000))
    wait(lambda:monitor.snapshot()['counts'].get('finalized_flows')==1)
    # Later flows, including between the same hosts, are scored normally.
    source.accept(packet(200_000,sport=2000)); source.accept(packet(300_000,True,flags=4,sport=2000))
    flows=_finish(source,monitor)
    assert flows[('192.0.2.1',1000)]['quality_errors']==[UNATTRIBUTED_ERROR]
    assert flows[('192.0.2.1',2000)]['status']=='ok'


def test_filtered_traffic_rejections_never_impair_flows(service):
    source,monitor=_session(service)
    source.accept(packet())
    for code in ('unsupported_ipv6','unsupported_network','unsupported_protocol'): source.error(code,False)
    source.accept(packet(100_000,True,flags=4))
    flows=_finish(source,monitor)
    assert flows[('192.0.2.1',1234)]['status']=='ok'
    assert monitor.snapshot()['counts']['rejected_packets']==3
    assert 'impaired_flows' not in monitor.snapshot()['counts']


def test_flow_table_impairment_matching_expiry_and_bounds():
    table=FlowTable(idle_seconds=1,max_seconds=2,capacity=2)
    table.add(packet(),0); table.add(packet(hosts=('198.51.100.1','198.51.100.2')),0)
    assert table.impair(ENDPOINT_REJECTION,0,scope=('UDP','192.0.2.1','192.0.2.2'))==0   # protocol differs
    assert table.impair(ENDPOINT_REJECTION,0,scope=(None,'192.0.2.2','192.0.2.1'))==1    # any protocol, either order
    assert table.impair(QUEUE_LOSS,0,key=packet().key)==1
    assert table.impair(UNATTRIBUTED_ERROR,0)==2
    with pytest.raises(ValueError): table.impair('session_poisoned',0)
    rows={row['source']:row for row in table.flush()}
    # Single-packet flows also carry 'zero_duration_rate_unavailable'.
    assert {ENDPOINT_REJECTION,QUEUE_LOSS,UNATTRIBUTED_ERROR}<=set(rows['192.0.2.1']['quality_errors'])
    assert set(rows['198.51.100.1']['quality_errors'])&{ENDPOINT_REJECTION,QUEUE_LOSS}==set()
    assert UNATTRIBUTED_ERROR in rows['198.51.100.1']['quality_errors']
    # Pending (attributed) impairment expires after one idle period ...
    table.impair(QUEUE_LOSS,10,key=packet().key)
    table.add(packet(),11.5); assert QUEUE_LOSS not in table.flush()[0]['quality_errors']
    # ... applies within it, and the pending set stays bounded by capacity.
    for i in range(5): table.impair(QUEUE_LOSS,20,key=packet(sport=3000+i).key)
    assert len(table.taints)==2 and ('key',packet(sport=3000).key,QUEUE_LOSS) not in table.taints  # oldest evicted
    table.add(packet(sport=3004),20.5); assert QUEUE_LOSS in table.flush()[0]['quality_errors']
    assert not table.taints  # a new monitoring session starts without pending impairments


def test_worker_inference_exception_visible_and_cleanup(service,monkeypatch):
    source=ManualSource(); monitor=Monitor(service,lambda *_:source)
    monkeypatch.setattr(service,'analyze',lambda *_: (_ for _ in ()).throw(ValueError('test')))
    monitor.start('replay')
    source.accept(packet()); source.accept(packet(100,True,flags=4)); source.done.set()
    wait(lambda:not monitor.snapshot()['running'])
    assert monitor.snapshot()['counts']['inference_failed']==1
    assert any(e['code']=='inference_failed' for e in monitor.snapshot()['errors'])


def test_permission_failure_and_invalid_interface(service):
    class Denied(ManualSource):
        def start(self,*_): raise CaptureError('permission_denied','Denied')
    source=Denied(); monitor=Monitor(service,lambda *_:source,lambda:[{'id':'safe'}])
    with pytest.raises(CaptureError,match='geçerli'): monitor.start('capture','injected')
    with pytest.raises(CaptureError,match='Denied'): monitor.start('capture','safe')
    assert source.stopped and monitor.snapshot()['state']=='permission_denied'


def test_missing_optional_dependency_offline_still_works(service,monkeypatch):
    def unavailable(): raise CaptureError('capture_unavailable','Scapy missing')
    monkeypatch.setattr('fuzzy_network_risk.realtime.capture.scapy_api',unavailable)
    monitor=Monitor(service)
    assert not monitor.discovery()['available']
    with pytest.raises(CaptureError): monitor.start('replay')
    assert service.analyze(service.examples[0]['features'],'Balanced')['status']=='ok'


def test_api_replay_security_validation_and_shutdown():
    pytest.importorskip('scapy.all')
    app=create_app()
    with TestClient(app,client=('127.0.0.1',50000)) as client:
        status=client.get('/api/live/status').json(); assert status['state']=='stopped'
        token={'X-Monitor-Token':status['control_token']}
        body={'mode':'replay','authorized':True}
        assert client.post('/api/live/start',json=body).status_code==403
        assert client.post('/api/live/start',json=body,headers=token|{'Origin':'https://evil.example'}).status_code==403
        assert client.get('/api/live/status',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
        assert client.post('/api/live/start',json=body|{'authorized':False},headers=token).status_code==422
        assert client.get('/api/live/status?limit=201').status_code==422
        assert client.get('/api/live/status?policy=Unknown').status_code==422
        assert client.post('/api/live/start',json=body|{'interface':'fake'},headers=token).status_code==422
        assert client.post('/api/live/start',json=body,headers=token).status_code==200
        wait(lambda:not app.state.monitor.snapshot()['running'])
        snapshot=client.get('/api/live/status').json()
        assert snapshot['counts']['ok']==2 and {f['protocol'] for f in snapshot['flows']}=={'TCP','UDP'}
        assert all(f['observation_mode']=='replay' for f in snapshot['flows'])
        assert len(client.get('/api/live/flows').json()['flows'])==2
        assert client.get('/api/live/stats').json()['counts']['ok']==2
        assert client.get('/api/live/errors').status_code==200
        assert client.post('/api/live/stop',json={},headers=token).status_code==200
        assert client.get('/api/health').status_code==200
        # Start a session whose active worker must be stopped by ASGI lifespan.
        client.post('/api/live/start',json=body,headers=token)
    assert not app.state.monitor.worker.is_alive()
    with TestClient(create_app(),client=('192.0.2.1',50000)) as remote:
        assert remote.get('/api/live/status').status_code==403


def test_scapy_capture_socket_options_and_cleanup(monkeypatch):
    from fuzzy_network_risk.realtime.capture import ScapySource
    class Socket:
        closed=False
        def close(self): self.closed=True
    sock=Socket(); options={}
    def listen(**kwargs): options.update(kwargs); return sock
    class API:
        conf=type('Conf',(),{'L2listen':staticmethod(listen)})()
        @staticmethod
        def sniff(**kwargs):
            assert kwargs['store'] is False and kwargs['opened_socket'] is sock
            time.sleep(.01)
    monkeypatch.setattr('fuzzy_network_risk.realtime.capture.scapy_api',lambda:API)
    source=ScapySource('chosen-only'); source.start(lambda _:None,lambda *_:None); source.stop()
    assert options=={'iface':'chosen-only','promisc':False,'filter':'ip and (tcp or udp)'}
    assert sock.closed and source.done.is_set() and not source.thread.is_alive()


def test_capture_failure_is_visible_and_blocks_inference(service):
    source=ManualSource(); monitor=Monitor(service,lambda *_:source)
    monitor.start('replay')
    source.accept(packet()); source.accept(packet(100,True))
    source.error('capture_failed',True)
    wait(lambda:not monitor.snapshot()['running'])
    snapshot=monitor.snapshot()
    assert snapshot['state']=='capture_failed'
    assert snapshot['counts']['insufficient_data']==1
    assert snapshot['flows'][0]['analysis'] is None
    assert not monitor.table.flows


def test_scapy_closed_socket_failure_not_silently_healthy(monkeypatch):
    from fuzzy_network_risk.realtime.capture import ScapySource
    class Socket:
        closed=False
        def close(self): self.closed=True
    sock=Socket()
    class API:
        conf=type('Conf',(),{'L2listen':staticmethod(lambda **_:sock)})()
        @staticmethod
        def sniff(**_): sock.close()
    monkeypatch.setattr('fuzzy_network_risk.realtime.capture.scapy_api',lambda:API)
    errors=[]; source=ScapySource('selected'); source.start(lambda _:None,lambda *args:errors.append(args))
    assert source.done.wait(2)
    source.stop()
    assert errors==[('capture_failed',True)]


def test_capture_cleanup_failure_still_signals_completion(monkeypatch):
    from fuzzy_network_risk.realtime.capture import ScapySource
    class Socket:
        closed=False
        def close(self): raise OSError('test close failure')
    class API:
        conf=type('Conf',(),{'L2listen':staticmethod(lambda **_:Socket())})()
        @staticmethod
        def sniff(**_): raise OSError('test read failure')
    monkeypatch.setattr('fuzzy_network_risk.realtime.capture.scapy_api',lambda:API)
    errors=[]; source=ScapySource('selected'); source.start(lambda _:None,lambda *args:errors.append(args))
    assert source.done.wait(2)
    source.stop()
    assert errors==[('capture_failed',True),('cleanup_failed',True)]
