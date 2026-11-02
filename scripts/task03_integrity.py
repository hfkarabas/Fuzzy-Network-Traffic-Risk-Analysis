"""Protect all historical TASK01/02/02B artifacts against accidental web changes."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'reports/web/historical_integrity.json'

def snapshot():
    names=subprocess.check_output(['git','ls-tree','-r','--name-only','c30d352bca3fb53410352b543ac342aa23777b86'],cwd=ROOT,text=True).splitlines()
    paths={ROOT/name for name in names if name.startswith(('config/','reports/','src/','tests/','scripts/'))}
    paths.update((ROOT/'data').rglob('*.parquet'))
    paths.update(p for p in (ROOT/'.cache/huggingface').rglob('*') if p.is_file() and (p.suffix=='.arrow' or p.parent.name=='blobs'))
    values={}
    for path in sorted(paths):
        with path.open('rb') as f: values[path.relative_to(ROOT).as_posix()]=hashlib.file_digest(f,'sha256').hexdigest()
    return values

if __name__=='__main__':
    current=snapshot()
    if '--record' in sys.argv:
        if MANIFEST.exists(): raise ValueError('Do not replace historical integrity baseline')
        MANIFEST.write_text(json.dumps(current,indent=2),encoding='utf-8')
        print(f'Recorded {len(current)} historical files')
    else:
        assert current==json.loads(MANIFEST.read_text()),'Historical artifact changed'
        print(f'PASS: {len(current)} historical artifacts unchanged')
