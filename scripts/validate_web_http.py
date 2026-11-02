"""Exercise a running loopback API and compare every example to direct inference."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
import json
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.policy import PolicyRiskModel

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--base',default='http://127.0.0.1:8000'); parser.add_argument('--output',default='reports/web/http_integration.json')
    args=parser.parse_args(); base=args.base.rstrip('/')
    if urlparse(base).hostname not in ['127.0.0.1','localhost','::1']: raise ValueError('This check only targets the local application')
    def get(path): return json.loads(urllib.request.urlopen(base+path).read())
    def post(body):
        req=urllib.request.Request(base+'/api/analyze',data=json.dumps(body,allow_nan=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as response: return json.loads(response.read())
    cfg=ROOT/'config/fuzzy/task02b'; engine=MamdaniRiskEngine.load(cfg/'selected_v2.json')
    policies=json.loads((cfg/'selected_policies.json').read_text())
    models={name:PolicyRiskModel(engine,policies,name) for name in policies['policies']}
    assert get('/api/health')['model_id']==engine.model_id
    examples=get('/api/examples')['examples']; timing=[]
    for example in examples:
        for policy,model in models.items():
            start=time.perf_counter(); actual=post({'features':example['features'],'policy':policy}); timing.append(time.perf_counter()-start)
            direct=model.predict_one(example['features'])
            for key in ['risk_score','risk_level','alert','membership_degrees','model_id']: assert actual[key]==direct[key]
            assert [(r['id'],r['strength'],r['consequent']) for r in actual['activated_rules']]==[(r['id'],r['strength'],r['consequent']) for r in direct['activated_rules']]
    contrast=next(e for e in examples if e['id']=='policy-contrast')
    one=post({'features':contrast['features'],'policy':'Balanced'}); two=post({'features':contrast['features'],'policy':'Conservative'})
    assert one['risk_score']==two['risk_score'] and one['alert']!=two['alert']
    try:
        post({'features':{}})
        raise AssertionError('Missing inputs were accepted')
    except urllib.error.HTTPError as error:
        payload=json.loads(error.read()); assert error.code==422 and payload['risk_score'] is None and payload['alert'] is None
    old=json.loads((ROOT/'reports/fuzzy/metrics.json').read_text())
    for item in get('/api/evaluation')['historical']: assert item['metrics']==old[item['id']]['row_weighted']
    html=urllib.request.urlopen(base+'/').read().decode()
    assets=re.findall(r'(?:src|href)="([^"]+)"',html)
    for asset in assets:
        assert asset.startswith('/'),'External runtime asset dependency'
        assert urllib.request.urlopen(base+asset).status==200
    assert urllib.request.urlopen(base+'/docs').status==200
    assert 'AnalyzeResponse' in get('/openapi.json')['components']['schemas']
    result={'status':'PASS','base_url':base,'real_examples_checked':len(examples),'policy_comparisons':len(timing),
            'all_scores_memberships_rules_match_direct_engine':True,'policy_switch_preserves_score_and_changes_alert':True,
            'missing_input_abstention_verified':True,'historical_metrics_match':True,'all_html_assets_local_and_served':True,
            'offline_openapi_documentation_verified':True,'mean_analyze_http_milliseconds':sum(timing)/len(timing)*1000,
            'model_id':engine.model_id,'example_score':one['risk_score']}
    (ROOT/args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
