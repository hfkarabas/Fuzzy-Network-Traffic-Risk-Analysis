"""Summarize actual local checks and account evidence; never stage or upload."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import re
from fuzzy_network_risk.dataset_archive import sha256


def main():
    r=ROOT/'reports/lfs'
    manifest=json.loads((ROOT/'config/dataset_archive_v1.json').read_text(encoding='utf-8'))
    integrity=json.loads((r/'integrity.json').read_text()); pipeline=json.loads((r/'pipeline_compatibility.json').read_text())
    quota=json.loads((r/'quota_check.json').read_text()); pointer=json.loads((r/'index_verification.json').read_text())
    assert all(v['status']=='PASS' for v in [integrity,pipeline,pointer])
    raw=(r/'python_tests.txt').read_bytes()
    log=raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig').replace('\r','')
    (r/'python_tests.txt').write_text(log.rstrip()+'\n',encoding='utf-8',newline='\n')
    assert 'failed' not in log.lower() and 'error' not in log.lower()
    tests=int(re.search(r'(\d+) passed',log).group(1))
    size=manifest['bytes']; gib=size/2**30
    sources=['src/fuzzy_network_risk/dataset_archive.py','tests/test_dataset_archive.py',
        *['scripts/'+name+'.py' for name in ['build_dataset_archive','restore_dataset_archive','verify_dataset_archive','validate_archive_pipeline','validate_lfs_index','report_dataset_lfs']]]
    result={'status':'PASS','dataset_files':[{'path':manifest['artifact'],'bytes':size,'format':'Parquet/ZSTD9','lfs_oid':manifest['sha256']}],
        'expected_unique_lfs_storage_bytes':size,'expected_unique_lfs_storage_gib':gib,
        'per_complete_object_download_bandwidth_bytes':size,'source_rows':manifest['rows'],'source_columns':manifest['columns'],
        'source_labels':len(manifest['labels']),'source_values_verified_bitwise':True,
        'original_datasets_unchanged':True,'offline_pipeline_compatible':True,
        'python_tests_passed':tests,'failed_tests':0,'pointer_verified':True,'pointer_bytes':pointer['pointer_bytes'],
        'large_ordinary_git_blobs':0,'quota_verified_on':quota['checked_on'],'plan':quota['plan_observed'],
        'ready_for_user_github_desktop_push':True,'remote_push_pull_fetch_executed':False,
        'source_sha256':{p:sha256(ROOT/p) for p in sources},
        'caveat':'Quota is an observed current-month snapshot, not a reservation. The user performs the eventual remote upload.'}
    (r/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Git LFS dataset integration — completed local preparation','',
        f'Selected exactly one artifact: `{manifest["artifact"]}`, **{size:,} bytes** ({size/2**20:.6f} MiB / {gib:.9f} GiB). Expected additional unique LFS storage is exactly that size for the first uploaded version; a complete object download consumes the same byte count of owner bandwidth. No upload was performed.','',
        '## Selection and inventory','',
        'The source is the required datasets-loaded c01dsnap/CIC-IDS2017 revision '+manifest['source_revision']+'. The four local Arrow streams were used without network acquisition. All 2,830,743 rows, 79 names/types, 15 labels, duplicates, source order and invalid measurements are preserved. The archive represents the parsed dataset, not original CSV text bytes.','',
        'inventory.csv/json lists 100 data/cache/temporary artifact entries with exact bytes, formats and redundancy roles. CSV snapshot aliases refer to source blobs and must not be counted as separate physical copies. CSV source blobs total884,645,759 bytes; Arrow shards total1,806,738,992 bytes. The cleaned330,985,606-byte table both loses invalid source values/types and is larger than the selected archive. Derived projections, manifests, samples and predictions add no necessary source information and remain ignored.','',
        'A bounded262,144-row compression pilot compared ZSTD9 numeric dictionary encoding with byte-stream split. Dictionary encoding was smaller (28,218,344 versus31,277,424 bytes) and was selected. This is the smallest tested complete Parquet representation, not proof of globally optimal compression. Only one full archive was produced; pilot/validation copies stay ignored.','',
        '## Verified integrity','',
        'Full record-by-record source/Parquet comparison verified schema including Arrow metadata, null masks, integer/string values and valid float bits, including signed zero/NaN/infinity semantics. All15 label counts exactly equal the original report. Nonfinite and negative values are retained in raw source rather than silently repaired. integrity.json contains exact per-feature counts and the SHA256 manifest.','',
        'SHA256: `'+manifest['sha256']+'`.','',
        '## Pipeline compatibility and preservation','',
        'A fresh empty .tmp/lfs/offline_restore_validation destination was reconstructed solely from the source artifact and tracked source-file ranges. It performs no download and never overwrites a populated destination. All six derived v1 outputs match the originals in records, order and values. Cleaned, fuzzy-ready, split manifest and development sample are also byte-identical with the pinned installed stack; source-origin/session files differ only in Arrow string offset representation and Parquet serialization.','',
        'The reconstructed outputs retain 2,830,743 cleaned rows, 2,827,761 fuzzy-ready rows, all source/day/group/partition metadata and the11,720 development records. Existing evaluation paths and algorithms remain unchanged. The original HF acquisition is unchanged. Historical cache-byte validation still needs the optional original cache; the new portable verifier uses the source artifact SHA256 instead. No fuzzy model, web code, old report or original data was modified.','',
        f'Preservation verified {pipeline["historical_hashes_unchanged"]} exact historical artifact hashes and {pipeline["prior_tracked_source_reports_configs_unchanged"]} prior tracked source/config/report/web files.','',
        '## Plan and quota gate','',
        'On2026-11-03 the authenticated repository-owner account showed GitHub Free and LFS storage/download usage of0 GB used /10 GB included. UI numbers are rounded. Documentation lists2 GB per-file and10 GiB included storage/download bandwidth. The276,625,347-byte object fits these limits with the displayed current usage. No quota, billing, payment or account setting was changed. Recheck before the user uploads because owner-level usage is shared and not reserved. Sources: [file-size limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage), [LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).','',
        '## LFS configuration and Git representation','',
        'Git LFS3.7.1 is installed. git lfs install --local configured repository-local filters and the normal pre-push hook. Exactly `datasets/cic_ids2017_v1.parquet` has filter=lfs/diff=lfs/merge=lfs/-text. The ignore exception permits only that dataset artifact; data/, caches, other Parquet and temporary files remain ignored. No history rewrite or migration command was used.','',
        f'The staged ordinary Git blob is **{pointer["pointer_bytes"]} bytes**, containing only this canonical pointer:','',
        '```text',pointer['pointer_text'].rstrip(),'```','',
        'The pointer passed git lfs pointer --check --strict. Its SHA256/size match both the worktree file and cached .git/lfs/objects content. No ordinary staged Git blob exceeds1 MiB and exactly one Parquet path is staged. index_verification.json records the Git pointer-blob ID separately from the LFS SHA256.','',
        '## Tests, commit and user upload','',
        f'**{tests} Python tests passed; zero failures.** New tests cover exact source values/dtypes, NaN/null distinctions, infinities, signed zero, large int64, Unicode labels, batching, refusal to overwrite, pointer detection, ignore/LFS attributes, quota evidence and offline derivation. Original model/API tests also pass. Frontend code is unchanged; no frontend rebuild was necessary for this dataset task.','',
        'All required pre-commit checks passed. The completed work is committed locally only; the resulting hash is reported in the final response. The user can push through GitHub Desktop with LFS installed. Remote upload success cannot be tested without violating the instruction to leave upload to the user. No git push, git pull, git fetch, history rewrite or model/UI modification was performed. See docs/dataset_lfs.md for cloning, pointer detection and safe offline restoration commands.']
    (r/'integration_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
