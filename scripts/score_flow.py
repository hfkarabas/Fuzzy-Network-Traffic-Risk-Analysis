"""Score a single JSON mapping read from a file or stdin. No labels accepted."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import argparse
import json
from fuzzy_network_risk.engine import MamdaniRiskEngine

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',default='config/fuzzy/grouped_v1.json')
    parser.add_argument('--input',type=Path,help='JSON input file; stdin if omitted')
    args=parser.parse_args()
    record=json.loads(args.input.read_text(encoding='utf-8')) if args.input else json.load(sys.stdin)
    result=MamdaniRiskEngine.load(args.model).predict_one(record)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
