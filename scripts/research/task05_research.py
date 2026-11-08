"""One bounded eligible-cache join; systematic design/training feature audit."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import hashlib
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import duckdb
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.refinement import check_lineage,roles
from fuzzy_network_risk.evaluation import binary_metrics

R=ROOT/'reports/fuzzy/task05'; C=ROOT/'config/fuzzy/task05'; T=ROOT/'.tmp/task05'


def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def dump(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def main():
    for p in [R,C,T]: p.mkdir(parents=True,exist_ok=True)
    source=ROOT/'data/fuzzy_v2/internal_development.parquet'
    lineage=pd.read_parquet(source)
    exposure=pd.read_parquet(ROOT/'data/fuzzy_v2/exposure_manifest.parquet',columns=['source_row_id','observation_group_id','signature'])
    check_lineage(lineage,exposure.source_row_id,exposure.observation_group_id,exposure.signature)
    assert not lineage.capture_day.eq('Friday').any()
    columns=[f.name for f in pq.read_schema(ROOT/'data/processed/v1/cleaned.parquet') if str(f.type)=='double']
    con=duckdb.connect(); con.execute("SET memory_limit='1GB'"); con.execute('SET threads=2')
    metadata=lineage[['source_row_id','observation_group_id','signature','capture_day','source_file','bucket']]
    con.register('eligible',metadata)
    fields=','.join('c."'+c+'"' for c in columns+[LABEL])
    frame=con.execute(f"SELECT e.*,{fields} FROM eligible e JOIN read_parquet('data/processed/v1/cleaned.parquet') c USING(source_row_id) ORDER BY source_row_id").df()
    assert frame.source_row_id.equals(lineage.source_row_id) and frame[LABEL].equals(lineage[LABEL])
    frame.to_parquet(T/'research.parquet',index=False)
    panels={'design':frame.loc[frame.bucket=='design']}
    comparison=frame.loc[frame.bucket!='design']
    for fold in range(3): panels['training_fold'+str(fold)]=roles(comparison,fold)[0]
    results=[]
    for name,panel in panels.items():
        # All association screening excludes capture-day/IDs as inputs and uses
        # design/training labels only. Assessment labels are never screened.
        corr=panel[columns].corr(method='spearman')
        if name=='design': corr.to_csv(R/'design_correlations.csv')
        for column in columns:
            v=panel[column].to_numpy(dtype=float); finite=np.isfinite(v); valid=finite&(v>=0)
            others=[c for c in INPUTS if c!=column]
            day_auc={}
            for day,g in panel.loc[valid].groupby('capture_day'):
                y=(g[LABEL]!='BENIGN').to_numpy()
                if y.any() and not y.all():
                    day_auc[day]=binary_metrics(y,g[column].to_numpy(),float(g[column].median()))['roc_auc']
            stats=dict(zip(['min','p01','p25','median','p75','p95','p99','max'],map(float,np.quantile(v[valid],[0,.01,.25,.5,.75,.95,.99,1])))) if valid.any() else {k:None for k in ['min','p01','p25','median','p75','p95','p99','max']}
            results.append({'panel':name,'feature':column,'rows':len(panel),'missing_fraction':float(np.isnan(v).mean()),
                'infinite_fraction':float(np.isinf(v).mean()),'negative_fraction':float((v<0).mean()),
                'zero_fraction':float((v==0).mean()),'unique_values':int(panel[column].nunique()),**stats,
                'max_baseline_abs_spearman':float(corr.loc[column,others].abs().max()) if corr.loc[column,others].notna().any() else None,
                'day_auc':json.dumps(day_auc),'direction_consistent_on_three_mixed_days':bool(len(day_auc)>=3 and (all(a>.55 for a in day_auc.values()) or all(a<.45 for a in day_auc.values())))})
    pd.DataFrame(results).to_csv(R/'feature_audit.csv',index=False)
    panel_counts=frame.groupby(['bucket','capture_day',LABEL]).size().rename('rows').reset_index()
    panel_counts.to_csv(R/'partition_classes.csv',index=False)
    conflicts=frame.groupby(INPUTS,dropna=False)[LABEL].nunique()
    dump(R/'lineage.json',{'status':'PASS','eligible_population':297916,'direct_exposed_rows':703945,
        'excluded_exposed_or_linked':2529845,'sample_rows':len(frame),'design_rows':len(panels['design']),
        'comparison_rows':len(comparison),'original_groups':frame.observation_group_id.nunique(),
        'coarse_signature_groups':frame.signature.nunique(),'source_sha256':digest(source),
        'research_cache_sha256':digest(T/'research.parquet'),'numeric_features_audited':len(columns),
        'exposed_id_group_signature_contamination':0,'Friday_rows':0,
        'five_input_vectors_with_multiple_labels':int((conflicts>1).sum()),
        'near_duplicate_note':'TASK04 found 3169 adjacent-bin cross-role representative pairs. Exact signatures protected; boundary/host/session dependence remains.',
        'capture_days':frame.capture_day.value_counts().to_dict(),
        'independent_holdout':False,'scope':'New feature measurements on previously used eligible development population; comparison outcomes remain adaptive internal validation.'})
    print('Audited',len(columns),'numerical columns on design and training roles; cached',len(frame),'eligible rows.',flush=True)


if __name__=='__main__': main()
