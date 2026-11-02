"""Full-data profiling and batched preparation. Run from repository root."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from acquire import acquire
import json
import time
from collections import Counter
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb
import yaml
from fuzzy_network_risk.data import clean, validate_schema, observation_ids, partitions, sample_development, INPUTS, LABEL

REPORT = ROOT / 'reports/dataset'
OUT = ROOT / 'data/processed/v1'

def save(name, obj):
    (REPORT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')

def main():
    start = time.time()
    cfg = yaml.safe_load((ROOT / 'config/dataset.yaml').read_text())
    if cfg['inputs'] != INPUTS:
        raise ValueError('Configuration and validated input schema differ')
    ds = acquire()
    provenance = json.loads((REPORT / 'provenance.json').read_text(encoding='utf-8'))
    if provenance['revision'] != cfg['source_revision']:
        raise ValueError('Source revision changed; use DATASET_REVISION from config before preparing v1')
    if list(ds) != ['train']:
        raise ValueError('Review new source splits before processing')
    source = ds['train']
    table = source.data.table
    validate_schema(table.column_names)
    from inspect_candidates import inspect
    inspect(table)
    n = len(table)
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=2")
    con.execute("SET temp_directory='data/interim/duckdb'")
    con.register('raw', table)
    classes = con.execute('SELECT " Label" AS Label, count(*) AS count FROM raw GROUP BY " Label" ORDER BY count DESC').df()
    classes['percent'] = classes['count'] / n * 100
    classes.to_csv(REPORT / 'classes.csv', index=False)
    print(classes.to_string(index=False), flush=True)
    profiles = []
    invalid_rows = np.zeros(n, dtype=bool)
    negative_rows = np.zeros(n, dtype=bool)
    missing_rows = np.zeros(n, dtype=bool)
    inf_rows = np.zeros(n, dtype=bool)
    comparison = []
    benign = np.asarray(table[LABEL].to_pylist()) == 'BENIGN'
    for c in table.column_names:
        if c == LABEL:
            continue
        a = table[c].to_numpy(zero_copy_only=False).astype('float64', copy=False)
        missing = np.isnan(a)
        inf = np.isinf(a)
        neg = np.isfinite(a) & (a < 0)
        missing_rows |= missing
        inf_rows |= inf
        negative_rows |= neg
        invalid_rows |= missing | inf | neg
        finite = a[np.isfinite(a)]
        qs = np.quantile(finite, [.01, .05, .25, .5, .75, .95, .99])
        values, counts = np.unique(finite, return_counts=True)
        row = dict(feature=c, dtype=str(table[c].type), count=len(finite), minimum=float(finite.min()),
                   maximum=float(finite.max()), mean=float(finite.mean()), std=float(finite.std(ddof=1)),
                   missing=int(missing.sum()), positive_inf=int(np.isposinf(a).sum()), negative_inf=int(np.isneginf(a).sum()),
                   negative=int(neg.sum()), zero=int((a == 0).sum()), unique_finite=len(values),
                   dominant_percent=float(counts.max() / n * 100),
                   **dict(zip(['p01','p05','p25','median','p75','p95','p99'], map(float, qs))))
        for field in ['missing', 'negative', 'zero']:
            row[field + '_percent'] = row[field] / n * 100
        row['infinite_percent'] = inf.sum() / n * 100
        row['outside_p01_p99'] = int(((finite < qs[0]) | (finite > qs[-1])).sum())
        row['outside_p01_p99_percent'] = row['outside_p01_p99'] / n * 100
        profiles.append(row)
        if c in INPUTS:
            for name, mask in [('Benign', benign), ('Attack', ~benign)]:
                x = a[mask & np.isfinite(a) & (a >= 0)]
                comparison.append(dict(feature=c, traffic=name, count=len(x), median=float(np.median(x)),
                                       p95=float(np.quantile(x, .95)), mean=float(x.mean())))
        print('Profiled:', c, flush=True)
    profile = pd.DataFrame(profiles)
    profile.to_csv(REPORT / 'numeric_profile.csv', index=False)
    pd.DataFrame(comparison).to_csv(REPORT / 'benign_attack_comparison.csv', index=False)
    numeric = [c for c in table.column_names if c != LABEL]
    quote = lambda c: '"' + c.replace('"', '""') + '"'
    def duplicates(columns):
        fields = ','.join(map(quote, columns))
        return con.execute(f'SELECT coalesce(sum(k-1),0),count(*),coalesce(sum(k),0) FROM (SELECT count(*) k FROM raw GROUP BY {fields} HAVING count(*)>1)').fetchone()
    exact = duplicates(table.column_names)
    observations = duplicates(numeric)
    fields = ','.join(map(quote, numeric))
    contradictory = con.execute(f'SELECT count(*),coalesce(sum(k),0) FROM (SELECT count(*) k FROM raw GROUP BY {fields} HAVING count(DISTINCT " Label")>1)').fetchone()
    quality = dict(rows=n, columns=len(table.column_names), missing_rows=int(missing_rows.sum()), infinite_rows=int(inf_rows.sum()),
                   negative_rows=int(negative_rows.sum()), any_unavailable_rows=int(invalid_rows.sum()),
                   exact_duplicates_excess=int(exact[0]), exact_duplicate_groups=int(exact[1]), exact_duplicate_member_rows=int(exact[2]),
                   observation_duplicates_excess=int(observations[0]), observation_duplicate_groups=int(observations[1]),
                   contradictory_observation_groups=int(contradictory[0]), contradictory_observation_rows=int(contradictory[1]),
                   duplicate_column_names=len(table.column_names)-len(set(table.column_names)),
                   constants=profile.loc[profile.unique_finite == 1, 'feature'].tolist(),
                   near_constants=profile.loc[(profile.dominant_percent >= 99) & (profile.unique_finite > 1), 'feature'].tolist(),
                   non_numeric_numeric_cells=0,
                   non_numeric_note='Arrow source schema is entirely numeric except Label; source loader successfully parsed every row.')
    save('quality.json', quality)
    print('Quality:', quality, flush=True)
    # Pilot before full output; source labels must survive every transformation.
    pilot = table.slice(0, min(1000, n)).to_pandas()
    pilot_clean, _ = clean(pilot)
    assert pilot_clean[LABEL].equals(pilot[LABEL])
    assert all(str(pilot_clean[c].dtype) == 'float64' for c in numeric)
    totals = Counter()
    writers = {}
    retained = eligible = 0
    # Keep only small per-class candidate reservoirs during streaming. Sampling
    # priorities are fixed row hashes, avoiding dependence on batch boundaries.
    reservoirs = []
    partition_counts = Counter()
    for offset in range(0, n, cfg['batch_size']):
        raw = table.slice(offset, cfg['batch_size']).to_pandas()
        cleaned, counts = clean(raw)
        totals.update(counts)
        cleaned['source_row_id'] = np.arange(offset, offset + len(raw), dtype='int64')
        ids = observation_ids(cleaned.drop(columns='source_row_id'))
        cleaned['observation_group_id'] = ids
        cleaned['partition'] = partitions(ids, cfg['seed'])
        cleaned['fuzzy_eligible'] = cleaned[INPUTS].notna().all(axis=1) & cleaned[LABEL].notna()
        # Duplicate rows are intentionally retained and always grouped across splits.
        fuzzy = cleaned.loc[cleaned.fuzzy_eligible, INPUTS + [LABEL, 'source_row_id', 'observation_group_id', 'partition']].copy()
        for key, frame in [('cleaned', cleaned), ('fuzzy_ready', fuzzy)]:
            arrow = pa.Table.from_pandas(frame, preserve_index=False)
            if key not in writers:
                writers[key] = pq.ParquetWriter(OUT / (key + '.parquet'), arrow.schema, compression='zstd')
            writers[key].write_table(arrow)
        retained += len(cleaned)
        eligible += len(fuzzy)
        partition_counts.update(fuzzy.partition)
        # Deterministic uniform pseudo-random priority per source row, independent
        # of feature values and labels. Reservoir cap per label/partition.
        fuzzy['_priority'] = pd.util.hash_pandas_object(fuzzy.source_row_id ^ cfg['seed'], index=False).to_numpy()
        reservoirs.append(fuzzy)
        candidates = pd.concat(reservoirs, ignore_index=True)
        candidates = candidates.sort_values('_priority').groupby([LABEL, 'partition'], sort=False).head(cfg['development_per_class'])
        reservoirs = [candidates]
        print(f'Processed {retained:,}/{n:,}', flush=True)
    for writer in writers.values():
        writer.close()
    candidates = reservoirs[0]
    dev = sample_development(candidates, cfg['development_per_class'], cfg['seed'])
    dev.to_parquet(ROOT / 'data/samples/development_v1.parquet', index=False)
    dev.groupby([LABEL, 'partition']).size().rename('count').to_csv(REPORT / 'development_classes.csv')
    # Full manifests are compact, stored separately from the 78 original features.
    con.execute("COPY (SELECT source_row_id, observation_group_id, partition, fuzzy_eligible FROM read_parquet('data/processed/v1/cleaned.parquet')) TO 'data/processed/v1/split_manifest.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
    crossings = con.execute("SELECT count(*) FROM (SELECT observation_group_id FROM read_parquet('data/processed/v1/cleaned.parquet') GROUP BY observation_group_id HAVING count(DISTINCT partition)>1)").fetchone()[0]
    # Correlations on all eligible observations, compact five-column materialization.
    selected = pq.read_table(OUT / 'fuzzy_ready.parquet', columns=INPUTS).to_pandas()
    selected.corr(method='spearman').to_csv(REPORT / 'candidate_spearman.csv')
    selected.corr(method='pearson').to_csv(REPORT / 'candidate_pearson.csv')
    validation = dict(source_rows=n, cleaned_rows=retained, excluded_cleaned_rows=n-retained,
                      fuzzy_rows=eligible, excluded_fuzzy_rows=n-eligible, development_rows=len(dev),
                      transformation_cells=dict(totals), partition_counts=dict(partition_counts),
                      groups_crossing_partitions=int(crossings), seed=cfg['seed'],
                      elapsed_seconds=round(time.time()-start, 2),
                      output_bytes={p.name:p.stat().st_size for p in OUT.glob('*.parquet')})
    assert retained == n and crossings == 0
    assert pq.read_metadata(OUT / 'cleaned.parquet').num_rows == n
    assert pq.read_metadata(OUT / 'fuzzy_ready.parquet').num_rows == eligible
    assert np.isfinite(selected.to_numpy()).all()
    save('preprocessing.json', validation)
    print(validation, flush=True)
    from recover_sessions import recover
    recover(table)
    from report import render_reports
    render_reports(table, profile, classes, quality, validation, dev)

if __name__ == '__main__':
    main()
