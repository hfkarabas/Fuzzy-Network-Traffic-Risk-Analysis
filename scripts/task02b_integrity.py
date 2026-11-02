"""Protect TASK01 and TASK02 committed artifacts, caches and generated predictions."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/fuzzy/task02b/baseline_integrity.json'

def snapshot():
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','51cd1a420909f3f249fcbb22a9189d11ecf0a81d'],cwd=ROOT,text=True).splitlines()
    protected=[p for p in tracked if p.startswith(('config/fuzzy/','reports/','src/','scripts/','tests/'))]
    paths={ROOT/p for p in protected}
    paths.update((ROOT/'data').rglob('*.parquet'))
    # New v2 artifacts are outside the protected historical experiment.
    paths={p for p in paths if 'task02b' not in p.parts and 'fuzzy_v2' not in p.parts}
    paths.update(p for p in (ROOT/'.cache/huggingface').rglob('*') if p.is_file() and (p.suffix=='.arrow' or p.parent.name=='blobs'))
    result={}
    for p in sorted(paths):
        if p.is_file():
            with p.open('rb') as f: result[p.relative_to(ROOT).as_posix()]=hashlib.file_digest(f,'sha256').hexdigest()
    return result

if __name__=='__main__':
    actual=snapshot()
    if '--record' in sys.argv:
        BASE.parent.mkdir(parents=True,exist_ok=True)
        if BASE.exists(): raise ValueError('Baseline already recorded')
        BASE.write_text(json.dumps(actual,indent=2),encoding='utf-8')
        print(f'Recorded {len(actual)} historical artifacts')
    else:
        assert actual==json.loads(BASE.read_text(encoding='utf-8')),'Historical artifact changed'
        print(f'PASS: {len(actual)} historical artifacts unchanged')
