"""Acquire the mandated source, keeping all caches inside the repository."""
import os
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
os.environ['HF_HOME'] = str(ROOT / '.cache' / 'huggingface')
os.environ['HF_DATASETS_CACHE'] = str(ROOT / '.cache' / 'huggingface' / 'datasets')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_XET'] = '1'

def acquire():
    from datasets import load_dataset
    from huggingface_hub import HfApi
    if os.environ.get('DATASET_REVISION'):
        ds = load_dataset("c01dsnap/CIC-IDS2017", revision=os.environ['DATASET_REVISION'])
    else:
        ds = load_dataset("c01dsnap/CIC-IDS2017")
    print(ds, flush=True)
    path = ROOT / 'reports/dataset/provenance.json'
    if os.environ.get('HF_HUB_OFFLINE') == '1':
        previous = json.loads(path.read_text(encoding='utf-8'))
        revision = previous['revision']
        for name, part in ds.items():
            if previous['splits'][name]['fingerprint'] != part._fingerprint:
                raise ValueError('Offline source differs from recorded acquisition')
    else:
        revision = HfApi().dataset_info('c01dsnap/CIC-IDS2017', revision=os.environ.get('DATASET_REVISION')).sha
    provenance = {
        'dataset_id': 'c01dsnap/CIC-IDS2017',
        'revision': revision,
        'cache_root': os.environ['HF_HOME'],
        'splits': {name: {'rows': len(part), 'columns': part.column_names,
                         'features': part.features.to_dict(),
                         'fingerprint': part._fingerprint,
                         'cache_files': part.cache_files,
                         'download_size': part.info.download_size,
                         'dataset_size': part.info.dataset_size,
                         'download_checksums': part.info.download_checksums}
                   for name, part in ds.items()},
    }
    (ROOT / 'reports/dataset/provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    return ds

if __name__ == '__main__':
    acquire()
