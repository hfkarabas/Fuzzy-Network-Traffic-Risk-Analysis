"""Offline stage verification: exact pointer, attributes and cached LFS object."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import subprocess
from fuzzy_network_risk.dataset_archive import sha256,lfs_pointer


def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)


def main():
    m=json.loads((ROOT/'config/dataset_archive_v1.json').read_text(encoding='utf-8'))
    q=json.loads((ROOT/'reports/lfs/quota_check.json').read_text())
    assert q['file_size_and_current_capacity_compatible'] and q['selected_object_bytes']==m['bytes']
    assert m['bytes']<q['per_file_limit_conservative_bytes']
    pointer=git('show',':'+m['artifact'])
    temporary=ROOT/'.tmp/lfs/index_pointer.txt'; temporary.write_bytes(pointer)
    assert lfs_pointer(temporary,m['bytes'],m['sha256'])
    assert int(git('cat-file','-s',':'+m['artifact']))==len(pointer)<1024
    subprocess.run(['git','lfs','pointer','--check','--strict','--file',str(temporary)],cwd=ROOT,check=True)
    attrs=git('check-attr','--cached','filter','diff','merge','text','--',m['artifact']).decode()
    assert 'filter: lfs' in attrs and 'diff: lfs' in attrs and 'merge: lfs' in attrs and 'text: unset' in attrs
    dataset_paths=git('diff','--cached','--name-only','--','*.parquet').decode().splitlines()
    assert dataset_paths==[m['artifact']]
    oid=m['sha256']; cached=ROOT/'.git/lfs/objects'/oid[:2]/oid[2:4]/oid
    assert cached.stat().st_size==m['bytes'] and sha256(cached)==oid
    assert sha256(ROOT/m['artifact'])==oid
    ordinary=[]
    for name in git('diff','--cached','--name-only','--diff-filter=ACMR').decode().splitlines():
        size=int(git('cat-file','-s',':'+name))
        assert size<1024*1024,'Unexpected ordinary large Git blob: '+name
        ordinary.append({'path':name,'git_blob_bytes':size})
    result={'status':'PASS','selected_path':m['artifact'],'pointer_bytes':len(pointer),'pointer_text':pointer.decode('ascii'),
        'git_blob_oid':git('rev-parse',':'+m['artifact']).decode().strip(),'lfs_sha256_oid':oid,
        'cached_lfs_object_bytes':m['bytes'],'cached_object_and_worktree_sha256_match':True,
        'only_one_dataset_staged':True,'large_ordinary_git_blobs':0,'cached_attributes':attrs.splitlines(),
        'remote_operation_executed':False,'ordinary_git_files_checked':len(ordinary)}
    (ROOT/'reports/lfs/index_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='staged_ordinary_blobs'},indent=2))


if __name__=='__main__': main()
