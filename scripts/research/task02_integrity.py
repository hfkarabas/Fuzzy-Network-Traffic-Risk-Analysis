"""Record and verify byte integrity of TASK 01 outputs and original cached data."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'reports/fuzzy/task01_integrity.json'

def snapshot():
    files=list((ROOT/'data/processed/v1').glob('*.parquet'))+list((ROOT/'data/samples').glob('*.parquet'))
    files+=list((ROOT/'reports/dataset').glob('*'))
    files+=[p for p in (ROOT/'.cache/huggingface').rglob('*') if p.is_file() and (p.suffix=='.arrow' or p.parent.name=='blobs')]
    result={}
    for path in sorted(files):
        if path.is_file():
            with path.open('rb') as handle:
                result[path.relative_to(ROOT).as_posix()]=hashlib.file_digest(handle,'sha256').hexdigest()
    return result

if __name__=='__main__':
    current=snapshot()
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    if '--record' in sys.argv:
        if MANIFEST.exists():
            raise ValueError('Refusing to replace baseline')
        MANIFEST.write_text(json.dumps(current,indent=2),encoding='utf-8')
        print(f'Recorded {len(current)} TASK 01 files')
    else:
        assert current==json.loads(MANIFEST.read_text(encoding='utf-8')),'TASK 01 artifact changed'
        print(f'PASS: {len(current)} TASK 01 source/output/report files unchanged')
