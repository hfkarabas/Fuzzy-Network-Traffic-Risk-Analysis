# Git LFS dataset integration — completed local preparation

Selected exactly one artifact: `datasets/cic_ids2017_v1.parquet`, **276,625,347 bytes** (263.810489 MiB / 0.257627430 GiB). Expected additional unique LFS storage is exactly that size for the first uploaded version; a complete object download consumes the same byte count of owner bandwidth. No upload was performed.

## Selection and inventory

The source is the required datasets-loaded c01dsnap/CIC-IDS2017 revision 4e9edfa727f800b6f595bc2ee7420527156562b2. The four local Arrow streams were used without network acquisition. All 2,830,743 rows, 79 names/types, 15 labels, duplicates, source order and invalid measurements are preserved. The archive represents the parsed dataset, not original CSV text bytes.

inventory.csv/json lists 100 data/cache/temporary artifact entries with exact bytes, formats and redundancy roles. CSV snapshot aliases refer to source blobs and must not be counted as separate physical copies. CSV source blobs total884,645,759 bytes; Arrow shards total1,806,738,992 bytes. The cleaned330,985,606-byte table both loses invalid source values/types and is larger than the selected archive. Derived projections, manifests, samples and predictions add no necessary source information and remain ignored.

A bounded262,144-row compression pilot compared ZSTD9 numeric dictionary encoding with byte-stream split. Dictionary encoding was smaller (28,218,344 versus31,277,424 bytes) and was selected. This is the smallest tested complete Parquet representation, not proof of globally optimal compression. Only one full archive was produced; pilot/validation copies stay ignored.

## Verified integrity

Full record-by-record source/Parquet comparison verified schema including Arrow metadata, null masks, integer/string values and valid float bits, including signed zero/NaN/infinity semantics. All15 label counts exactly equal the original report. Nonfinite and negative values are retained in raw source rather than silently repaired. integrity.json contains exact per-feature counts and the SHA256 manifest.

SHA256: `010d70b93517a13293c5128bc1b27cf0b2fdadd9352b64b1ac441b36b4110bf8`.

## Pipeline compatibility and preservation

A fresh empty .tmp/lfs/offline_restore_validation destination was reconstructed solely from the source artifact and tracked source-file ranges. It performs no download and never overwrites a populated destination. All six derived v1 outputs match the originals in records, order and values. Cleaned, fuzzy-ready, split manifest and development sample are also byte-identical with the pinned installed stack; source-origin/session files differ only in Arrow string offset representation and Parquet serialization.

The reconstructed outputs retain 2,830,743 cleaned rows, 2,827,761 fuzzy-ready rows, all source/day/group/partition metadata and the11,720 development records. Existing evaluation paths and algorithms remain unchanged. The original HF acquisition is unchanged. Historical cache-byte validation still needs the optional original cache; the new portable verifier uses the source artifact SHA256 instead. No fuzzy model, web code, old report or original data was modified.

Preservation verified 176 exact historical artifact hashes and 315 prior tracked source/config/report/web files.

## Plan and quota gate

On2026-11-03 the authenticated repository-owner account showed GitHub Free and LFS storage/download usage of0 GB used /10 GB included. UI numbers are rounded. Documentation lists2 GB per-file and10 GiB included storage/download bandwidth. The276,625,347-byte object fits these limits with the displayed current usage. No quota, billing, payment or account setting was changed. Recheck before the user uploads because owner-level usage is shared and not reserved. Sources: [file-size limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage), [LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

## LFS configuration and Git representation

Git LFS3.7.1 is installed. git lfs install --local configured repository-local filters and the normal pre-push hook. Exactly `datasets/cic_ids2017_v1.parquet` has filter=lfs/diff=lfs/merge=lfs/-text. The ignore exception permits only that dataset artifact; data/, caches, other Parquet and temporary files remain ignored. No history rewrite or migration command was used.

The staged ordinary Git blob is **134 bytes**, containing only this canonical pointer:

```text
version https://git-lfs.github.com/spec/v1
oid sha256:010d70b93517a13293c5128bc1b27cf0b2fdadd9352b64b1ac441b36b4110bf8
size 276625347
```

The pointer passed git lfs pointer --check --strict. Its SHA256/size match both the worktree file and cached .git/lfs/objects content. No ordinary staged Git blob exceeds1 MiB and exactly one Parquet path is staged. index_verification.json records the Git pointer-blob ID separately from the LFS SHA256.

## Tests, commit and user upload

**173 Python tests passed; zero failures.** New tests cover exact source values/dtypes, NaN/null distinctions, infinities, signed zero, large int64, Unicode labels, batching, refusal to overwrite, pointer detection, ignore/LFS attributes, quota evidence and offline derivation. Original model/API tests also pass. Frontend code is unchanged; no frontend rebuild was necessary for this dataset task.

All required pre-commit checks passed. The completed work is committed locally only; the resulting hash is reported in the final response. The user can push through GitHub Desktop with LFS installed. Remote upload success cannot be tested without violating the instruction to leave upload to the user. No git push, git pull, git fetch, history rewrite or model/UI modification was performed. See docs/dataset_lfs.md for cloning, pointer detection and safe offline restoration commands.
