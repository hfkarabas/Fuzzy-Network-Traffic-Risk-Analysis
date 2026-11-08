"""Run a frozen experimental architecture locally; never changes production."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import argparse
import json
from fuzzy_network_risk.advanced import AdvancedRiskEngine
from fuzzy_network_risk.policy import PolicyRiskModel


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True,help='Frozen TASK05 experimental config JSON')
    parser.add_argument('--input',required=True,help='JSON containing only the eight source feature values')
    parser.add_argument('--policy-key',required=True,help='e.g. C_hierarchy_0; must match the frozen model')
    parser.add_argument('--policy',choices=['Sensitive','Balanced','Conservative'],default='Balanced')
    args=parser.parse_args()
    engine=AdvancedRiskEngine.load(args.model)
    expected=ROOT/'config/fuzzy/task05'/f'{args.policy_key.rsplit("_",1)[0]}_fold{args.policy_key.rsplit("_",1)[1]}.json'
    if engine.model_id!=AdvancedRiskEngine.load(expected).model_id: raise ValueError('Policy-key/model mismatch')
    policies=json.loads((ROOT/'config/fuzzy/task05/fold_policies.json').read_text())[args.policy_key]
    wrapper=PolicyRiskModel(engine,{'model_id':engine.model_id,'policies':policies},args.policy)
    result=wrapper.predict_one(json.loads(Path(args.input).read_text(encoding='utf-8')))
    print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
