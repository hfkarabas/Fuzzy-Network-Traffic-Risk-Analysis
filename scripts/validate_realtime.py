"""Bounded HTTP/Vite replay integration. Never starts physical capture by default."""
from pathlib import Path
import argparse
import json
import socket
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import dev
from fuzzy_network_risk.webapp.service import WebService


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--write-frontend-fixture',action='store_true')
    parser.add_argument('--live-interface',help='Explicit authorized LOOPBACK interface only; optional actual local capture')
    args=parser.parse_args()
    assert all(dev.port_available(p) for p in [8000,5173]),'Ports occupied; no unrelated process will be stopped'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(path,body=None,token=None):
        headers={'Content-Type':'application/json'}
        if token: headers['X-Monitor-Token']=token
        req=urllib.request.Request('http://127.0.0.1:5173'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with opener.open(req,timeout=10) as response: return json.load(response)
    child=dev.Child('task07-local-app',[sys.executable,ROOT/'scripts/dev.py','run'],ROOT)
    try:
        dev.wait_ready([child],8000,dev.model_assets(ROOT)); dev.wait_ready([child],5173)
        status=call('/api/live/status'); assert status['state']=='stopped' and not status['running']
        token=status['control_token']; discovery=call('/api/live/interfaces')
        service=WebService()
        example=service.examples[0]
        offline=call('/api/analyze',{'features':example['features'],'policy':'Balanced'})
        assert offline['risk_score']==example['risk_score']
        call('/api/live/start',{'mode':'replay','authorized':True},token)
        deadline=time.monotonic()+10
        while True:
            status=call('/api/live/status')
            if not status['running']: break
            assert time.monotonic()<deadline,'Replay timeout'
            time.sleep(.1)
        assert status['counts']['packets']==6 and status['counts']['ok']==2
        comparisons=0
        for policy in ['Sensitive','Balanced','Conservative']:
            for row in call('/api/live/status?policy='+policy)['flows']:
                direct=service.analyze(row['features'],policy)
                assert row['analysis']==direct
                comparisons+=1
        assert comparisons==6
        if args.write_frontend_fixture:
            status['control_token']='test-only-token'
            status['session_id']='synthetic-replay'
            for row in status['flows']:
                row['id']='replay-'+row['protocol'].lower(); row['observed_at']=0
            (ROOT/'web/src/live-test-fixture.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        live={'status':'NOT RUN','reason':discovery['error']['message'] if discovery['error'] else 'No explicit authorized loopback interface requested'}
        if args.live_interface:
            selected=next((item for item in discovery['interfaces'] if item['id']==args.live_interface),None)
            assert selected and any(word in (selected['name']+' '+selected['description']+' '+selected['id']).lower() for word in ['loopback','localhost','lo0']), 'Only explicitly selected loopback capture is supported by this validator'
            call('/api/live/start',{'mode':'capture','interface':args.live_interface,'authorized':True},token)
            # Send only to an ephemeral socket bound to our own loopback device.
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as client:
                server.bind(('127.0.0.1',0)); server.settimeout(2); client.settimeout(2)
                for _ in range(3):
                    client.sendto(b'authorized-local-test',server.getsockname())
                    data,peer=server.recvfrom(128); server.sendto(data,peer); client.recvfrom(128); time.sleep(.05)
            time.sleep(.5)
            captured=call('/api/live/stop',{},token)
            assert captured['counts'].get('packets',0)>0 and captured['counts'].get('ok',0)>0
            live={'status':'PASS','interface':args.live_interface,'counts':captured['counts'],'scope':'Actual localhost UDP only; stop-finalized segments provisional'}
        call('/api/live/stop',{},token)
        assert call('/api/health')['model_id']==service.engine.model_id
        with opener.open('http://127.0.0.1:5173/src/LiveTraffic.tsx',timeout=3) as response:
            assert 'Canlı Trafik' in response.read().decode()
    finally:
        child.close()
    deadline=time.monotonic()+8
    while not all(dev.port_available(p) for p in [8000,5173]) and time.monotonic()<deadline: time.sleep(.1)
    assert all(dev.port_available(p) for p in [8000,5173]),'Owned application did not stop'
    report={'status':'PASS','transport':'actual localhost HTTP through Vite proxy and FastAPI',
        'source':'explicit synthetic serialized Scapy IPv4 packets; NOT captured traffic','packets':6,'flows':2,
        'direct_offline_live_policy_comparisons':comparisons,'offline_regression':'PASS',
        'no_automatic_capture':True,'owned_process_cleanup':'PASS','actual_capture':live,
        'frontend_source_served':True,'model_id':service.engine.model_id}
    target=ROOT/'reports/realtime/integration.json'; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
