"""Hash source/cache data before processing and verify after; never modify source."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'reports/dataset/source_integrity.json'

def hashes():
    files = sorted(p for p in (ROOT/'.cache/huggingface').rglob('*')
                   if p.is_file() and (p.suffix == '.arrow' or p.parent.name == 'blobs'))
    result = []
    for path in files:
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if path.parent.name == 'blobs' and len(path.name) == 64 and digest != path.name:
            raise ValueError(f'Source blob SHA256 mismatch: {path}')
        result.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':digest})
    if not result:
        raise ValueError('No source files to verify')
    return result

if __name__ == '__main__':
    current = hashes()
    if '--record' in sys.argv:
        if MANIFEST.exists():
            raise ValueError('Existing integrity baseline must not be overwritten')
        MANIFEST.write_text(json.dumps(current,indent=2),encoding='utf-8')
        print(f'Recorded {len(current)} source/cache files')
    else:
        assert current == json.loads(MANIFEST.read_text(encoding='utf-8')), 'Source/cache data changed'
        print(f'PASS: {len(current)} source/cache files unchanged; SHA256 source blob names verified')
