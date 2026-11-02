"""Generate English reports and a focused set of static figures from measurements."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fuzzy_network_risk.data import INPUTS, LABEL

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports/dataset'
F = ROOT / 'reports/figures'

def md(frame):
    # Keep exact source names visible (including leading whitespace).
    headers = list(frame.columns)
    rows = ['| ' + ' | '.join(map(str, headers)) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |']
    for row in frame.itertuples(index=False, name=None):
        rows.append('| ' + ' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in row) + ' |')
    return '\n'.join(rows)

def render_reports(table, profile, classes, quality, validation, dev):
    F.mkdir(parents=True, exist_ok=True)
    p = json.loads((R / 'provenance.json').read_text(encoding='utf-8'))
    n = len(table)
    pct = lambda x: f'{x:,} ({x/n*100:.4f}%)'
    inventory = pd.DataFrame([{'Exact column (JSON string)':json.dumps(c), 'Arrow type':str(table[c].type)} for c in table.column_names])
    inventory.to_csv(R / 'schema.csv', index=False)
    profile['arrow_null_count'] = [table[c].null_count for c in profile.feature]
    profile['ieee_nan_nonnull_count'] = profile['missing'] - profile['arrow_null_count']
    profile['outside_p01_p99_percent'] = profile['outside_p01_p99'] / n * 100
    profile.to_csv(R/'numeric_profile.csv',index=False)
    sessions = json.loads((R / 'session_recovery.json').read_text(encoding='utf-8')) if (R / 'session_recovery.json').exists() else None
    session_note = ''
    if sessions:
        session_note = f'''Coarse capture-day/file provenance was recovered from the eight
original downloaded CSVs. Every numerical value and label was matched exactly
against all {sessions['rows_verified']:,} rows of the datasets-loaded table.
See source_files.csv, session_recovery.json and the local source_sessions.parquet
manifest. No alternative data source was acquired. Original row order is alphabetical
by file, NOT chronological. Fine-grained timestamps, hosts and flow sessions remain unavailable.'''
    text = f'''# Dataset profile

Source: https://huggingface.co/datasets/c01dsnap/CIC-IDS2017 . The required
`ds = load_dataset("c01dsnap/CIC-IDS2017")` call was executed successfully.
Revision: `{p['revision']}`. Split fingerprint: `{p['splits']['train']['fingerprint']}`.
Verified source: **{n:,} rows, {len(table.column_names)} columns, one train split**.
There is no supplied evaluation split. 78 numerical features and one string target,
`" Label"`; leading spaces are part of actual column names and are preserved.
No numeric strings remain in the successfully parsed Arrow numerical fields.
No genuinely categorical input exists; ports and flags have categorical/discrete semantics despite numeric types.

Cache: `{p['cache_root']}`. Download size reported by datasets:
{p['splits']['train']['download_size']:,} bytes; Arrow dataset size:
{p['splits']['train']['dataset_size']:,} bytes. See provenance.json for original
download URLs, cache file paths, source schema, revision, and fingerprint.
No redundant raw export was created. Raw source files and cached Arrow data are never edited.
Hugging Face's repository license tag is `other`; verify original CIC usage and attribution conditions before redistribution.

## Class distribution

{md(classes)}

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

Rows with missing measurements: {pct(quality['missing_rows'])}.
Rows with infinity: {pct(quality['infinite_rows'])}.
Rows with a finite negative measurement: {pct(quality['negative_rows'])}.
Rows with any unavailable measurement under the cleaning policy:
{pct(quality['any_unavailable_rows'])}.

## Exact schema

{md(inventory)}

## Limitations

No timestamp, source IP, destination IP, flow identifier, or original day/file
identifier is supplied as a feature. Port is available. {session_note}
Physical units are inferred from
CICFlowMeter naming conventions rather than a unit-annotated source schema.
Outliers and zeros can describe real network behavior. This is a laboratory
benchmark, not a measurement of operational traffic prevalence.
'''
    (R / 'dataset_profile.md').write_text(text, encoding='utf-8')
    issues = profile.loc[(profile.missing + profile.positive_inf + profile.negative) > 0,
                         ['feature','missing','positive_inf','negative_inf','negative','minimum','maximum']].copy()
    issues.feature = issues.feature.map(json.dumps)
    (R / 'data_quality_and_leakage.md').write_text(f'''# Data quality and leakage

## Confirmed baseline findings

All counts describe the full {n:,}-row source, not a sample. Row percentages
use the full source denominator; cell categories overlap.

{md(issues)}

NaN/missing rows: {pct(quality['missing_rows'])}; infinite rows:
{pct(quality['infinite_rows'])}; negative-measurement rows:
{pct(quality['negative_rows'])}. Infinity and NaN are mathematically unavailable.
Negative durations, rates, packet/header lengths and segment sizes are physically
implausible under the stated measurement interpretation. Negative initial TCP
windows (notably -1) can be unavailable/sentinel codes, not attack evidence.
All negative numerical values are conservatively nulled in derived outputs,
with no row deletion. Zero durations are retained; derived infinite rates are
nulled, without dividing by zero or reconstructing rates. Large finite rates,
long durations, extreme packet counts and heavy tails are retained. No winsorizing.
Finite values above p99 or below p01 are explicitly counted in numeric_profile.csv;
they are NOT classified as invalid. Other protocol-specific plausibility limits
cannot be reliably determined without protocol and capture metadata.

Exact duplicate source rows beyond the first: **{pct(quality['exact_duplicates_excess'])}**;
{quality['exact_duplicate_groups']:,} repeated groups, involving
{quality['exact_duplicate_member_rows']:,} rows. These counts use exact SQL grouping
over all 79 source columns, with nulls/NaNs grouped consistently by DuckDB.
Identical numerical observations ignoring the label: {quality['observation_duplicates_excess']:,}
excess rows in {quality['observation_duplicate_groups']:,} groups.
Contradictory labels for otherwise identical numerical observations:
{quality['contradictory_observation_groups']:,} groups involving
{quality['contradictory_observation_rows']:,} rows. Without flow identifiers these
may be repeated distinct flows; neither deduplication nor label relabeling is justified.
Duplicates are retained, flagged through group IDs, and never separated across partitions.

Duplicate literal column names: {quality['duplicate_column_names']}.
Constant columns: {', '.join('`'+x+'`' for x in quality['constants'])}.
Near-constant means >=99% identical finite values among all source rows:
{', '.join('`'+x+'`' for x in quality['near_constants'])}.
Very low variance is also visible in std and unique_finite in numeric_profile.csv.
`" Fwd Header Length.1"` is a semantically duplicated header feature; pair checks
in redundancy.json distinguish exact equal columns from highly correlated ones.

## Confirmed risks and controls

The target `" Label"` is explicitly excluded from INPUTS, tested and schema validated.
Ports may identify scenario services and are omitted from the initial input set.
No IP/time/session columns are supplied as source features; capture-day/file
origins are recovered separately, with exact full-row verification. Duplication makes ordinary row-random
splits optimistic. Cleaned observations are grouped ignoring labels using stable
64-bit hashes over all original cleaned numerical features. Identical observations
necessarily share hashes. Hash collisions can only conservatively merge distinct
groups, not split identical observations. Source exact counts do not rely on hashes.
Cleaning may merge records differing only in invalid measurements; this further
conservatively groups them. No fitting, imputation, normalization, or clipping is
performed. Labels are preserved verbatim. Duplicate-weighted metrics should be
reported alongside unique-observation-group metrics during evaluation.

## Suspected or unresolved risks

Within-day session/scenario confounding, almost-identical flows, collection artifacts and
possible shared hosts remain unresolved. Recovered file/day metadata supports a
coarse temporal stress test but does not restore fine-grained session independence.
There is no brute-force near-duplicate
search. Correlated duration/rate/length statistics can reflect genuine behavior;
correlation alone is not evidence of leakage. Fwd/subflow and segment-size aliases
are redundant measures, not inherently leaked targets. Per-class candidate
distributions are descriptive and do not prove operational generalization.

## Evaluation recommendation

Use the saved deterministic 70/15/15 observation-group partition as a provisional
development split. Realized sizes vary; rare classes may be absent from a partition.
Tune membership functions and rule weights only on train; choose model decisions
with validation and reserve test. Full-data exploratory summaries have been viewed:
the test set is not a fully blind external holdout. In addition, use the recovered
day manifest for a stricter temporal stress test: Monday/Tuesday/Wednesday train,
Thursday validation, Friday test. Entire groups occurring in multiple nominal
partitions are quarantined, preventing exact overlap without moving future records
into train. See temporal_partitions.csv and temporal_classes.csv for actual sizes
and class coverage. Attack classes differ across days; this tests novel scenarios
and cannot support ordinary stratified multiclass comparisons. Membership fitting
must respect whichever manifest is chosen. Prefer a separately sourced,
host/session-aware external evaluation when authorized data becomes available.
Do not claim leakage-free or independent evaluation from the current metadata.
No severity truth exists; traffic detection agreement and expert-reviewed risk
explanations are different evaluation objectives.
''', encoding='utf-8')
    explanations = [
        (' Flow Packets/s','packets/second','Bidirectional packet intensity','Sparse / Moderate / Intensive',
         'Intensive flows may indicate flooding; tiny durations make this rate unstable and benign bursts overlap.'),
        (' Total Fwd Packets','packets','Forward-direction packet volume','Few / Moderate / Many',
         'Separates tiny bursts from sustained packet volume; legitimate long transfers can also have many packets.'),
        (' Packet Length Mean','bytes','Average packet length within the flow','Small / Medium / Large',
         'Small packets with high intensity suggest control/request floods; large packets can be normal transfer traffic.'),
        (' Bwd Packet Length Std','bytes','Variation in responder-direction packet sizes','Uniform / Variable / Highly variable',
         'Describes response behavior beyond mean size; zero may mean constant sizes or too few/no response packets.'),
        (' Down/Up Ratio','dimensionless','Exported backward-to-forward packet ratio','Forward dominated / Balanced / Backward dominated',
         'Provides directional context with little correlation to packet size; integer quantization loses detail and zero can represent few or no response packets.')]
    rows = []
    for rank, (c, unit, meaning, terms, weakness) in enumerate(explanations,1):
        x = profile.set_index('feature').loc[c]
        rows.append({'rank':rank,'exact_column':json.dumps(c),'unit':unit,'min':x.minimum,'p01':x.p01,'median':x['median'],
                     'p95':x.p95,'p99':x.p99,'max':x.maximum,'zero_percent':x.zero_percent,
                     'missing_percent':x.missing_percent,'infinite_percent':x.infinite_percent})
    selected_stats = pd.DataFrame(rows)
    selected_stats.to_csv(R / 'selected_features.csv',index=False)
    notes = '\n\n'.join(f'{i}. **`{json.dumps(c)}`** — {meaning}; {unit}. Linguistic candidates: {terms}. {weakness}'
                        for i,(c,unit,meaning,terms,weakness) in enumerate(explanations,1))
    (R / 'fuzzy_feature_selection.md').write_text(f'''# Fuzzy input feature selection

## Ranked initial candidates

Recommended initial set: the five behavior measurements below, covering intensity,
volume, size, response variation and directional balance. Ratio is integer-valued
and needs careful overlapping terms. Source names are JSON
quoted to make leading whitespace explicit. Ranking reflects interpretability,
security relevance, completeness, numerical behavior and redundancy, not classifier training.

{notes}

{md(selected_stats)}

All statistics above describe finite original measurements before negative-value
nulling. The saved fuzzy-ready observations have finite nonnegative values only.
Missingness and infinite rates motivate an explicit abstention/unavailable-input
policy rather than arbitrary median substitution. Every selected input is a
behavior measurement, not an identifier or label. No label is passed to inference.
benign_attack_comparison.csv supplies full-data medians/p95/means by binary traffic
group: overlap is expected and no single variable is treated as a standalone detector.

## Redundancy and alternatives

candidate_spearman.csv and candidate_pearson.csv quantify the five proposed inputs
on all eligible observations. Inspect absolute rank correlations especially above
0.85 before adding rules; correlation is a distribution-dependent indicator, not
evidence of leakage. Full-data expanded_candidate_spearman.csv showed duration
versus packet rate at -0.9804, and IAT mean versus packet rate at -0.9967: duration
and IAT were excluded from the initial set to avoid redundant timing inputs.
Packet length mean and backward-size variation correlate around 0.73 but distinguish
size from within-flow diversity. Forward volume versus response variation is about
0.72; directional ratio adds a relatively independent aspect. Redundancy remains
moderate, so compare removing response variation in TASK 02 if rule complexity grows.

Alternatives (see the same exact full-data numeric profile and redundancy.json):
`" Flow IAT Mean"` or `" Flow Duration"` (microseconds) can replace intensity;
avoid adding them alongside rate given their near-perfect rank association.
`" SYN Flag Count"` provides optional absent/present context but is mostly binary
and must not be interpreted as a rate or handshake-failure counter.
`" PSH Flag Count"` is additional
discrete context rather than a strong graded fuzzy variable. `"Active Mean"`
(microseconds) describes active periods but is zero-heavy and tied to lifetime.

Rejected from the initial set: target label (direct leakage); destination port
(service/scenario shortcut risk and categorical semantics); constant bulk/flag
columns (no information); near-constant URG/CWE-style flags (rare context only);
duplicate forward header length, subflow totals and average-segment-size aliases
(redundancy); initial windows (sentinels, host/TCP-stack effects); header/minimum
segment sizes (negative artifacts); Flow Bytes/s together with packet rate and
mean length (substantial algebraic redundancy and invalid rates).
These original features remain in the cleaned dataset for future review.

## Preliminary membership recommendations

Use train-only valid-value distributions to propose overlapping triangular or
trapezoidal sets. Consider log1p coordinates for volume/intensity and response
variation, with physical units displayed in explanations. Explicit zero membership
is appropriate for response variation; zero does not automatically mean suspicious.
Use shoulders to cover the full finite nonnegative domain rather than clipping
extreme attacks. Compare train p25/p50/p75/p95 as starting anchors; the full-data
percentiles above are exploratory, NOT finalized boundaries. Do not fit from test.
For the directional ratio, anchor terms around forward domination, approximate
balance and backward domination after checking train-only integer frequencies.
No membership functions or inference engine are implemented in this task.

## Preliminary rule concepts

- IF packet intensity is intensive AND packet size is small AND direction is
  forward dominated, THEN elevated risk is plausible; validate against legitimate bursts.
- IF forward volume is many AND intensity is intensive, THEN sustained-load concern rises.
- IF intensity is sparse AND packet size is medium AND response variation is
  variable, THEN lower risk may be plausible, without assuming every sparse flow is benign.
- IF response variation is uniform AND packets are small AND intensity is intensive,
  THEN investigate repeated requests; zero responses alone must not trigger high risk.

These are hypotheses for interpretable rules, not calibrated severity assignments.
Sparse port scans, application attacks and low-volume infiltration may remain
undetectable using five aggregate features. TASK 02 must test those weaknesses and
decide whether optional TCP flag context improves explanations. Feature engineering must
remain compact; no conventional ML model was trained.
''', encoding='utf-8')
    transforms = pd.DataFrame([{'feature':json.dumps(k), 'nulled_cells':v} for k,v in validation['transformation_cells'].items() if v])
    (R / 'preprocessing_report.md').write_text(f'''# Preprocessing report (v1)

Baseline profiling preceded cleaning. A 1,000-row pilot checked label preservation
and numeric dtype consistency before processing the full source in 65,536-row batches.
No GPU or fitted estimator is used. Original source files remain unchanged in the
Hugging Face cache; integrity hashes are checked separately by validate_outputs.py.

## Cleaning rules and accounting

1. Parse expected numerical fields; malformed/non-numeric values become null.
2. Replace NaN, positive/negative infinity and negative numerical measurements with null.
   This includes negative unknown window sentinels. No imputation or clipping.
3. Preserve all labels verbatim, all original features, zeros and large finite values.
4. Retain duplicates; identify observations ignoring labels and assign group partitions.
5. Add source row ID, observation group ID, partition and fuzzy eligibility metadata.
6. Export fuzzy-ready rows only when all five inputs and the label are available.

Cleaned rows: **{validation['cleaned_rows']:,}**; excluded cleaned rows:
**{validation['excluded_cleaned_rows']:,}**. Fuzzy-ready rows:
**{validation['fuzzy_rows']:,}**; unavailable-input rows excluded from fuzzy-ready:
**{validation['excluded_fuzzy_rows']:,}**. Exclusions are not claims of corrupted flows.
Invalid measurements outside the input set do not make a row fuzzy-ineligible.
Numerical features are uniformly float64; labels remain strings, source IDs int64,
group IDs uint64, eligibility boolean. Per-feature null counts (overlapping cells):

{md(transforms)}

## Outputs (local, ignored by Git)

- `data/processed/v1/cleaned.parquet`: all source rows and original columns plus metadata.
- `data/processed/v1/fuzzy_ready.parquet`: five inputs plus label and row/group/partition metadata.
- `data/processed/v1/split_manifest.parquet`: every source row and its eligibility/group partition.
- `data/samples/development_v1.parquet`: {validation['development_rows']:,} eligible observations.
- `data/processed/v1/source_sessions.parquet`: recovered CSV filename/day and coarse
  temporal partitions, joined by source_row_id. Entire cross-day-partition duplicate
  groups are quarantined from this alternative evaluation protocol.

Full eligible partition sizes: {validation['partition_counts']}.
Groups crossing partitions: **{validation['groups_crossing_partitions']}**.
Hash grouping is conservative, not a guarantee of independent sessions.

## Sampling and reproducibility

Seed: {validation['seed']}. Version v1, fixed source revision in provenance.json,
locked dependencies in requirements.txt. Source order defines stable source_row_id.
Observation-group hash mixing assigns approximately 70/15/15 train/validation/test.
The development reservoir chooses the lowest deterministic pseudorandom row-ID
hashes within each label and partition, capped at 700/150/150 (1,000 per class).
All eligible members of rare strata below those caps are retained. Full source
class proportions are retained in cleaned output; the development set deliberately
overrepresents rare categories and is NOT distribution-preserving. See
development_classes.csv for actual label/partition counts. Sampling within saved
partitions cannot introduce duplicate leakage across them. Duplicates can consume
multiple sample positions; report group-weighted metrics as well as row metrics.

## Validation

Full pipeline assertions verified row accounting, Parquet footer counts, finite
nonnegative fuzzy inputs and zero group crossings. Unit tests use synthetic data
without network/download dependencies; validation.json and test_results.txt record
actual additional checks and pytest output. requirements.txt pins the executed
environment. Full observed processing elapsed time: {validation['elapsed_seconds']} seconds.
Output byte counts: {validation['output_bytes']}.
Rerunning overwrites only versioned generated outputs, not the HF cache/source.
''', encoding='utf-8')
    if sessions:
        with (R/'preprocessing_report.md').open('a',encoding='utf-8') as handle:
            handle.write('\n## Verified source provenance and temporal stress test\n\n')
            handle.write(session_note+'\n\n'+md(pd.DataFrame(sessions['counts']))+'\n\n')
            handle.write('Temporal eligibility counts use the same five-input policy. Quarantine applies only to this alternative manifest; no rows are deleted from cleaned or fuzzy-ready data. All nonquarantined observation groups remain in one temporal partition.\n')
    # Focused figures. Development distributions are explicitly labeled as stratified.
    fig, ax = plt.subplots(figsize=(10,6))
    ax.barh(classes.Label.iloc[::-1], classes['count'].iloc[::-1])
    ax.set_xscale('log'); ax.set_xlabel('Source rows (log scale)'); ax.set_title('Full source class distribution')
    fig.tight_layout(); fig.savefig(F/'class_distribution.png',dpi=150); plt.close(fig)
    q = profile.loc[(profile.missing + profile.positive_inf + profile.negative_inf) > 0].set_index('feature')
    fig, ax = plt.subplots(figsize=(9,4))
    q[['missing','positive_inf','negative_inf']].plot.barh(ax=ax)
    ax.set_xlabel('Cells (categories can overlap across rows)'); ax.set_title('Missing and infinite source measurements')
    fig.tight_layout(); fig.savefig(F/'invalid_values.png',dpi=150); plt.close(fig)
    fig, axes = plt.subplots(2,3,figsize=(13,7))
    for ax,c in zip(axes.flat,INPUTS):
        for name, mask in [('Benign',dev[LABEL]=='BENIGN'),('Attack',dev[LABEL]!='BENIGN')]:
            ax.hist(np.log1p(dev.loc[mask,c]),bins=45,alpha=.5,density=True,label=name)
        ax.set_title(c.strip()); ax.set_xlabel('log1p(value)'); ax.set_ylabel('Density')
    axes.flat[0].legend(); axes.flat[-1].axis('off')
    fig.suptitle('Stratified development sample: selected features by traffic group')
    fig.tight_layout(); fig.savefig(F/'selected_distributions.png',dpi=150); plt.close(fig)
    corr = pd.read_csv(R/'candidate_spearman.csv',index_col=0)
    fig, ax = plt.subplots(figsize=(8,7)); im=ax.imshow(corr,vmin=-1,vmax=1,cmap='coolwarm')
    ax.set_xticks(range(len(corr)),[c.strip() for c in corr],rotation=45,ha='right')
    ax.set_yticks(range(len(corr)),[c.strip() for c in corr])
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j,i,f'{corr.iloc[i,j]:.2f}',ha='center',va='center')
    fig.colorbar(im,ax=ax); ax.set_title('Full eligible observations: Spearman correlation')
    fig.tight_layout(); fig.savefig(F/'candidate_correlation.png',dpi=150); plt.close(fig)
