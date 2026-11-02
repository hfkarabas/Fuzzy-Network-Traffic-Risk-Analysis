# Dataset profile

Source: https://huggingface.co/datasets/c01dsnap/CIC-IDS2017 . The required
`ds = load_dataset("c01dsnap/CIC-IDS2017")` call was executed successfully.
Revision: `4e9edfa727f800b6f595bc2ee7420527156562b2`. Split fingerprint: `f36ca5b47149ef8d`.
Verified source: **2,830,743 rows, 79 columns, one train split**.
There is no supplied evaluation split. 78 numerical features and one string target,
`" Label"`; leading spaces are part of actual column names and are preserved.
No numeric strings remain in the successfully parsed Arrow numerical fields.
No genuinely categorical input exists; ports and flags have categorical/discrete semantics despite numeric types.

Cache: `C:\Fuzzy-Network-Traffic-Risk-Analysis\.cache\huggingface`. Download size reported by datasets:
884,645,759 bytes; Arrow dataset size:
1,795,719,069 bytes. See provenance.json for original
download URLs, cache file paths, source schema, revision, and fingerprint.
No redundant raw export was created. Raw source files and cached Arrow data are never edited.
Hugging Face's repository license tag is `other`; verify original CIC usage and attribution conditions before redistribution.

## Class distribution

| Label | count | percent |
| --- | --- | --- |
| BENIGN | 2273097 | 80.30036637024273 |
| DoS Hulk | 231073 | 8.162980531966342 |
| PortScan | 158930 | 5.614427024989553 |
| DDoS | 128027 | 4.522734843820156 |
| DoS GoldenEye | 10293 | 0.3636147824087174 |
| FTP-Patator | 7938 | 0.28042107672791206 |
| SSH-Patator | 5897 | 0.20831986513788078 |
| DoS slowloris | 5796 | 0.20475189729339613 |
| DoS Slowhttptest | 5499 | 0.19425995224575313 |
| Bot | 1966 | 0.0694517305173942 |
| Web Attack � Brute Force | 1507 | 0.053236906352855065 |
| Web Attack � XSS | 652 | 0.023032822124791973 |
| Infiltration | 36 | 0.0012717509148658145 |
| Web Attack � Sql Injection | 21 | 0.0007418547003383918 |
| Heartbleed | 11 | 0.00038859055732010995 |

Labels support Benign/Attack analysis (`BENIGN` versus every other category),
multiclass attack analysis, and descriptive families (DoS/DDoS, brute force,
web attacks, reconnaissance, botnet, infiltration, Heartbleed).
Family grouping is a future explicit mapping, not a replacement target.
Some web-attack labels contain the Unicode replacement character U+FFFD in the
loaded source; these strings are preserved verbatim rather than guessed or merged.
The labels are traffic categories, not calibrated risk levels.

## Numerical profiling

numeric_profile.csv contains exact finite-value count, min, max, mean, sample
standard deviation, median, p01/p05/p25/p75/p95/p99, missing/infinite/zero percentages,
negative counts, Arrow-null versus nonnull IEEE NaN counts, unique counts and dominant-value frequency for every numerical
column. Quantiles use NumPy linear interpolation on ALL finite original values;
negative values remain in baseline statistics. Infinite/NaN values are excluded
only from descriptive finite statistics. benign_attack_comparison.csv compares
valid nonnegative candidate measurements between benign and attack traffic.
Percentile-tail counts are descriptive, not evidence of corruption.

Rows with missing measurements: 1,358 (0.0480%).
Rows with infinity: 2,867 (0.1013%).
Rows with a finite negative measurement: 1,444,427 (51.0264%).
Rows with any unavailable measurement under the cleaning policy:
1,445,413 (51.0613%).

## Exact schema

| Exact column (JSON string) | Arrow type |
| --- | --- |
| " Destination Port" | int64 |
| " Flow Duration" | int64 |
| " Total Fwd Packets" | int64 |
| " Total Backward Packets" | int64 |
| "Total Length of Fwd Packets" | int64 |
| " Total Length of Bwd Packets" | int64 |
| " Fwd Packet Length Max" | int64 |
| " Fwd Packet Length Min" | int64 |
| " Fwd Packet Length Mean" | double |
| " Fwd Packet Length Std" | double |
| "Bwd Packet Length Max" | int64 |
| " Bwd Packet Length Min" | int64 |
| " Bwd Packet Length Mean" | double |
| " Bwd Packet Length Std" | double |
| "Flow Bytes/s" | double |
| " Flow Packets/s" | double |
| " Flow IAT Mean" | double |
| " Flow IAT Std" | double |
| " Flow IAT Max" | int64 |
| " Flow IAT Min" | int64 |
| "Fwd IAT Total" | int64 |
| " Fwd IAT Mean" | double |
| " Fwd IAT Std" | double |
| " Fwd IAT Max" | int64 |
| " Fwd IAT Min" | int64 |
| "Bwd IAT Total" | int64 |
| " Bwd IAT Mean" | double |
| " Bwd IAT Std" | double |
| " Bwd IAT Max" | int64 |
| " Bwd IAT Min" | int64 |
| "Fwd PSH Flags" | int64 |
| " Bwd PSH Flags" | int64 |
| " Fwd URG Flags" | int64 |
| " Bwd URG Flags" | int64 |
| " Fwd Header Length" | int64 |
| " Bwd Header Length" | int64 |
| "Fwd Packets/s" | double |
| " Bwd Packets/s" | double |
| " Min Packet Length" | int64 |
| " Max Packet Length" | int64 |
| " Packet Length Mean" | double |
| " Packet Length Std" | double |
| " Packet Length Variance" | double |
| "FIN Flag Count" | int64 |
| " SYN Flag Count" | int64 |
| " RST Flag Count" | int64 |
| " PSH Flag Count" | int64 |
| " ACK Flag Count" | int64 |
| " URG Flag Count" | int64 |
| " CWE Flag Count" | int64 |
| " ECE Flag Count" | int64 |
| " Down/Up Ratio" | int64 |
| " Average Packet Size" | double |
| " Avg Fwd Segment Size" | double |
| " Avg Bwd Segment Size" | double |
| " Fwd Header Length.1" | int64 |
| "Fwd Avg Bytes/Bulk" | int64 |
| " Fwd Avg Packets/Bulk" | int64 |
| " Fwd Avg Bulk Rate" | int64 |
| " Bwd Avg Bytes/Bulk" | int64 |
| " Bwd Avg Packets/Bulk" | int64 |
| "Bwd Avg Bulk Rate" | int64 |
| "Subflow Fwd Packets" | int64 |
| " Subflow Fwd Bytes" | int64 |
| " Subflow Bwd Packets" | int64 |
| " Subflow Bwd Bytes" | int64 |
| "Init_Win_bytes_forward" | int64 |
| " Init_Win_bytes_backward" | int64 |
| " act_data_pkt_fwd" | int64 |
| " min_seg_size_forward" | int64 |
| "Active Mean" | double |
| " Active Std" | double |
| " Active Max" | int64 |
| " Active Min" | int64 |
| "Idle Mean" | double |
| " Idle Std" | double |
| " Idle Max" | int64 |
| " Idle Min" | int64 |
| " Label" | string |

## Limitations

No timestamp, source IP, destination IP, flow identifier, or original day/file
identifier is supplied as a feature. Port is available. Coarse capture-day/file provenance was recovered from the eight
original downloaded CSVs. Every numerical value and label was matched exactly
against all 2,830,743 rows of the datasets-loaded table.
See source_files.csv, session_recovery.json and the local source_sessions.parquet
manifest. No alternative data source was acquired. Original row order is alphabetical
by file, NOT chronological. Fine-grained timestamps, hosts and flow sessions remain unavailable.
Physical units are inferred from
CICFlowMeter naming conventions rather than a unit-annotated source schema.
Outliers and zeros can describe real network behavior. This is a laboratory
benchmark, not a measurement of operational traffic prevalence.
