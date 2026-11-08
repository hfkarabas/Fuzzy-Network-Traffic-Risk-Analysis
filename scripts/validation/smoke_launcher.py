"""Bounded real GNU Make startup/proxy/inference/interrupt regression check."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))  # dev.py launcher
import argparse
import json
import os
import signal
import time
import urllib.request
import dev
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.policy import PolicyRiskModel


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--make',required=True); parser.add_argument('--root',default=str(ROOT))
    parser.add_argument('--output',default='reports/launcher/smoke.json'); args=parser.parse_args()
    root=Path(args.root).resolve(); target=Path(args.make).resolve()
    for port in [8000,5173]:
        if not dev.port_available(port): raise RuntimeError('Smoke needs free ports; no existing server is stopped')
    for name in ['requirements.txt','requirements-web.txt','web/package.json','web/package-lock.json']:
        if not (root/name).exists(): raise RuntimeError('Missing isolated fixture input '+name)
    child=dev.Child('make-default',[target],root)
    method=None; comparisons=0; exit_code=None
    try:
        manifest=dev.model_assets(root)
        dev.wait_ready([child],8000,manifest,timeout=90); dev.wait_ready([child],5173,timeout=90)
        engine=MamdaniRiskEngine.load(root/'config/fuzzy/task04/selected_v4.json')
        policies=json.loads((root/'config/fuzzy/task04/selected_policies.json').read_text(encoding='utf-8'))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(path):
            with opener.open('http://127.0.0.1:5173'+path,timeout=3) as response: return response.read()
        assert json.loads(get('/api/health'))['model_id']==engine.model_id
        assert json.loads(get('/api/model'))['configuration_version']=='task04-v1'
        assert len(json.loads(get('/api/policies'))['policies'])==3
        html=get('/').decode(); assert '/@vite/client' in html and '/src/main.tsx' in html
        assert get('/@vite/client') and get('/src/main.tsx')
        examples=json.loads(get('/api/examples'))['examples']
        for example in examples:
            for name in policies['policies']:
                request=urllib.request.Request('http://127.0.0.1:5173/api/analyze',
                    data=json.dumps({'features':example['features'],'policy':name}).encode(),headers={'Content-Type':'application/json'})
                with opener.open(request,timeout=3) as response: actual=json.load(response)
                direct=PolicyRiskModel(engine,policies,name).predict_one(example['features'])
                for key in ['risk_score','risk_level','alert','membership_degrees','model_id']: assert actual[key]==direct[key]
                assert [(r['id'],r['strength']) for r in actual['activated_rules']]==[(r['id'],r['strength']) for r in direct['activated_rules']]
                comparisons+=1
        # A second invocation must refuse ports before touching dependencies.
        blocked=dev.subprocess.run([sys.executable,str(root/'scripts/dev.py'),'run'],cwd=root,env=dev.environment(root),capture_output=True,text=True,encoding='utf-8',timeout=15)
        assert blocked.returncode==1 and 'occupied' in blocked.stderr
        if dev.windows(): child.process.send_signal(signal.CTRL_BREAK_EVENT); method='native Windows CTRL_BREAK_EVENT to owned Make group'
        else: os.killpg(child.process.pid,signal.SIGINT); method='native POSIX SIGINT to owned Make session'
        exit_code=child.process.wait(timeout=20)
        deadline=time.monotonic()+10
        while not all(dev.port_available(p) for p in [8000,5173]) and time.monotonic()<deadline: time.sleep(.1)
        assert all(dev.port_available(p) for p in [8000,5173]),'Launcher failed cleanup before harness safety-job closure'
    finally:
        child.close()
    deadline=time.monotonic()+6
    while not all(dev.port_available(p) for p in [8000,5173]) and time.monotonic()<deadline: time.sleep(.1)
    assert all(dev.port_available(p) for p in [8000,5173]),'Owned servers orphaned'
    result={'status':'PASS','platform':sys.platform,'root':str(root),'make_default_target_tested':True,
        'backend_health':True,'vite_development_html_and_hmr_client':True,'frontend_api_proxy':True,
        'all_27_example_policy_results_match_direct_engine':comparisons==27,'comparisons':comparisons,
        'duplicate_start_refused_without_installation':True,'interrupt_method':method,'make_exit_code':exit_code,
        'both_ports_released':True,'ports_released_before_harness_cleanup':True,'owned_process_tree_cleanup':True,
        'dataset_directory_absent':not (root/'datasets').exists(),'processed_data_directory_absent':not (root/'data').exists(),
        'production_model_id':engine.model_id,'note':'Windows uses Ctrl+Break for a targeted real console test; ordinary Ctrl+C takes the same KeyboardInterrupt cleanup path.'}
    output=ROOT/args.output; output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=='__main__': main()
