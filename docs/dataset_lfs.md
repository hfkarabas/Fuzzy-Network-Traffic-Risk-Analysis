# CIC-IDS2017 Git LFS distribution

The repository distributes one immutable, complete **parsed source table**:
`datasets/cic_ids2017_v1.parquet`. Its manifest is
`config/dataset_archive_v1.json`. It contains all 2,830,743 source records, all
79 original column names (including spaces), original int64/float64/string types,
all 15 labels, original row order and duplicates. Invalid measurements are preserved,
not cleaned or imputed. It is a lossless representation of the table acquired by
`datasets.load_dataset("c01dsnap/CIC-IDS2017")` at revision
`4e9edfa727f800b6f595bc2ee7420527156562b2`.

It is not an exact copy of CSV text formatting or original packet captures. The
unchanged upstream acquisition script remains available for that provenance route.
Do not replace this artifact in place for a different dataset revision; use a new
version and manifest. A new LFS file version can consume its full size again.

## Clone with Git LFS

Install Git LFS from its official distribution or GitHub Desktop's supported setup.
With Git LFS installed, a normal clone downloads LFS objects automatically:

```powershell
git lfs install
git clone https://github.com/hfkarabas/Fuzzy-Network-Traffic-Risk-Analysis.git
cd Fuzzy-Network-Traffic-Risk-Analysis
git lfs ls-files
```

GitHub Desktop cloning is also supported. A GitHub ZIP download is not guaranteed
to contain LFS objects; prefer an LFS-aware clone. If smudging was skipped or quota
was exhausted, the `.parquet` path may contain a small pointer instead of data.
The verifier detects this and stops; it never downloads silently.

Use the existing project Python setup, then verify the downloaded artifact:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt
.\.venv\Scripts\python.exe scripts/data/verify_dataset_archive.py
```

An already installed compatible Python and `.venv` can be used. Versions used for
export are recorded in the manifest; dependencies remain pinned in the project.

## Reproduce local datasets without Hugging Face downloads

On a fresh checkout with an absent or empty `data` directory:

```powershell
.\.venv\Scripts\python.exe scripts/data/restore_dataset_archive.py
```

The command verifies the entire source object's SHA256, then uses the original
cleaning, observation hashing, seed and development sampling functions. It creates:

- `data/processed/v1/cleaned.parquet`: 2,830,743 rows / 83 columns.
- `data/processed/v1/fuzzy_ready.parquet`: 2,827,761 rows / 9 columns.
- `data/processed/v1/split_manifest.parquet`: 2,830,743 rows / 4 columns.
- `data/processed/v1/source_sessions.parquet`: 2,830,743 rows / 7 columns.
- `data/samples/development_v1.parquet`: 11,720 rows / 9 columns.
- `data/interim/source_origins.parquet`: 2,830,743 rows / 3 columns.

Capture-day/source-file ranges are in the small tracked manifest, so original CSV
copies are unnecessary for reconstruction. Cross-day observation groups receive
the same quarantine policy. Labels remain evaluation metadata, never model inputs.

**Existing data is never overwritten.** For an existing populated checkout, use an
empty alternate destination to inspect a reconstruction:

```powershell
.\.venv\Scripts\python.exe scripts/data/restore_dataset_archive.py --destination .tmp/my-offline-data
```

The complete reconstruction was validated against untouched original v1 outputs.
Cleaned, fuzzy-ready, split manifest and development sample files were byte-identical
with the installed pinned stack. Source-origin/session records were value-identical;
Arrow string versus large-string offsets and Parquet encoding/layout differ. Do not
assume regenerated file bytes remain identical across software versions.

Existing evaluation scripts retain their usual `data/...` paths. TASK02B's eligible
research cache can then be regenerated using its existing preparation script:

```powershell
New-Item -ItemType Directory -Force data/fuzzy_v2 | Out-Null
.\.venv\Scripts\python.exe scripts/research/task02b_prepare.py
```

Run research preparation only when the local cache is absent, as the original
research scripts write their own generated outputs. Registered experiment code/data
hashes must match before evaluation; validation folds remain exposed development
evidence. Historical HF cache-byte integrity checks still require the original
optional HF cache and are not substitutes for the portable archive verifier.
This integration does not refit models, change evaluation metrics or alter the UI.

## Selected storage and exclusions

The object is **276,625,347 bytes** (263.810489 MiB / 0.257627430 GiB), encoded as
Parquet with ZSTD level 9. A bounded 262,144-row pilot compared dictionary encoding
against byte-stream split; dictionary was smaller and was used for the full export.
This is the smallest tested complete representation, not a claim of a global
compression optimum. The cleaned 330,985,606-byte output is both larger and lacks
the original invalid values/types, so it is not an adequate canonical source.

`reports/lfs/inventory.csv` and `.json` give every inventoried data/cache/research
file's exact bytes, format and redundancy role. The eight original CSV source blobs
total 884,645,759 bytes; their snapshot symlinks are aliases, not additional physical
copies. Four parsed Arrow shards total 1,806,738,992 bytes. These and all derived
Parquet/sample/prediction/curve/temp copies remain ignored and are not LFS objects.
Local verification copies are temporary, not selected for upload.

`.gitattributes` tracks only the exact canonical path through LFS. `.gitignore`
permits only that dataset file and continues to ignore other Parquet/cache/data
files. No historical large-blob migration or history rewrite is performed.

## Plan, quota and upload

On 2026-11-03, the repository owner's authenticated billing overview showed GitHub
Free and, for LFS, `0 GB used / 10 GB included` for both storage and download usage.
That display is rounded, not a precise remaining-byte balance or reservation.
Current documentation lists a 2 GB per-file limit for Free and includes 10 GiB each
of storage and download bandwidth. The selected object fits these limits. No billing,
payment, access or budget setting was modified.

Every complete LFS download uses approximately 0.258 GiB of the owner's bandwidth;
later object versions add storage. Recheck owner-level usage before uploading or
sharing broadly. Sources: [GitHub file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage),
[LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

Only a local commit is made by this task. The user uploads it through GitHub Desktop.
The repository-local LFS filters and pre-push hook are installed. Do not bypass the
hook: it uploads the object associated with the committed pointer. All local object
and pointer checks must pass first. No push, pull or fetch command was executed.

## Maintainer verification

The following checks are offline:

```powershell
.\.venv\Scripts\python.exe scripts/data/verify_dataset_archive.py
git check-attr filter diff merge text -- datasets/cic_ids2017_v1.parquet
git lfs ls-files -l
git lfs fsck --objects --pointers
```

`scripts/data/build_dataset_archive.py` is an export/verification tool for maintainers
with the original datasets-loaded Arrow cache; it never downloads and never replaces
an existing archive. The tracked manifest is exclusive-create. Ordinary clones do
not need to run it. Synthetic pytest coverage includes NaN/null distinctions,
infinities, signed zero, 64-bit integers, Unicode labels, refusal to overwrite,
pointer detection and offline reconstruction.
