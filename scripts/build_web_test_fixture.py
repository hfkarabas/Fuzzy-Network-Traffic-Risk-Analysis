"""Capture real Python API-adapter responses for isolated React tests."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import json
from fuzzy_network_risk.webapp.service import WebService

if __name__=='__main__':
    service=WebService()
    fixture={'health':{'status':'ok'},'model':service.model,'policies':{'policies':service.policy_list()},
             'examples':{'examples':service.examples},'evaluation':service.evaluation,
             'analyses':{example['id']:{p:service.analyze(example['features'],p) for p in service.models} for example in service.examples}}
    (ROOT/'web/src/test-fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Captured real service responses for frontend fixtures.')
