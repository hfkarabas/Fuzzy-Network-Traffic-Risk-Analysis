"""Reproducible phases: fit/calibrate -> frozen evaluation -> reports (no network)."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse
import hashlib
import json
import platform
import time
import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from fuzzy_network_risk.data import INPUTS,LABEL,SEED
from fuzzy_network_risk.calibration import fit_config
from fuzzy_network_risk.engine import MamdaniRiskEngine,LEVELS,config_digest
from fuzzy_network_risk.evaluation import binary_metrics,calibrate_alert

REPORT=ROOT/'reports/fuzzy'
CONFIG=ROOT/'config/fuzzy'
GENERATED=ROOT/'data/fuzzy_v1'

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def connect():
    c=duckdb.connect()
    c.execute("SET memory_limit='1GB'"); c.execute('SET threads=2')
    c.execute("SET temp_directory='data/interim/duckdb'")
    c.execute("CREATE VIEW full_data AS SELECT * FROM read_parquet('data/processed/v1/fuzzy_ready.parquet')")
    c.execute("CREATE VIEW sessions AS SELECT * FROM read_parquet('data/processed/v1/source_sessions.parquet')")
    c.execute("CREATE VIEW development AS SELECT * FROM read_parquet('data/samples/development_v1.parquet')")
    return c

def query(scenario,partition):
    if scenario=='grouped':
        return f"SELECT * FROM development WHERE partition='{partition}' ORDER BY source_row_id"
    if scenario=='day':
        return f"SELECT f.*,s.capture_day FROM full_data f JOIN sessions s USING(source_row_id) WHERE s.temporal_partition='{partition}' ORDER BY f.source_row_id"
    raise ValueError('Unknown scenario')

def score_frame(engine,frame):
    start=time.perf_counter()
    prediction=engine.predict_batch(frame[INPUTS],batch_size=2048)
    seconds=time.perf_counter()-start
    scores=frame[[LABEL,'source_row_id','observation_group_id']].copy()
    for k in ['risk_score','risk_level','status']: scores[k]=prediction[k]
    scores['alert']=scores.risk_score>=engine.config['alert_threshold']
    scores['active_rules']=(prediction['rule_strengths']>0).sum(axis=1)
    scores['meaningful_rules']=(prediction['rule_strengths']>=.1).sum(axis=1)
    strengths=prediction['rule_strengths']
    low=[j for j,r in enumerate(engine.config['rules']) if r['consequent']=='Low']
    high=[j for j,r in enumerate(engine.config['rules']) if r['consequent'] in ['High','Critical']]
    scores['conflicting_low_high']=(strengths[:,low].max(axis=1)>=.1)&(strengths[:,high].max(axis=1)>=.1)
    scores['outside_training_range']=prediction['out_of_training_range'].any(axis=1)
    valid=prediction['status']=='ok'
    rule_rows=[]
    for j,r in enumerate(engine.config['rules']):
        active=strengths[:,j]>=.1
        attack=(frame[LABEL]!='BENIGN').to_numpy()
        rule_rows.append({'rule_id':r['id'],'consequent':r['consequent'],'rows':len(frame),
                          'active_any':int((strengths[:,j]>0).sum()),'active_meaningful':int(active.sum()),
                          'mean_strength':float(strengths[:,j].mean()),
                          'dominant_rows_first_tie':int(((strengths.argmax(axis=1)==j)&valid).sum()),
                          'active_benign':int((active&~attack).sum()),'active_attack':int((active&attack).sum())})
    coverage={'rows':len(frame),'valid_scores':int(valid.sum()),'invalid_input':int((prediction['status']=='invalid_input').sum()),
              'no_rule_activation':int((prediction['status']=='no_rule_activation').sum()),
              'any_rule_fraction':float((scores.active_rules>0).mean()),
              'multiple_rule_fraction':float((scores.active_rules>1).mean()),
              'meaningful_rule_fraction':float((scores.meaningful_rules>0).mean()),
              'multiple_meaningful_rule_fraction':float((scores.meaningful_rules>1).mean()),
              'conflicting_low_high_fraction':float(scores.conflicting_low_high.mean()),
              'outside_training_range_fraction':float(scores.outside_training_range.mean())}
    return scores,pd.DataFrame(rule_rows),coverage,seconds

def fit():
    c=connect(); frozen={}; records={}
    for scenario in ['grouped','day']:
        training=c.execute(query(scenario,'train')).df()
        config=fit_config(training[INPUTS],scenario)
        engine=MamdaniRiskEngine(config)
        validation=c.execute(query(scenario,'validation')).df()
        val_result=engine.predict_batch(validation[INPUTS])
        valid=val_result['status']=='ok'
        threshold,choices=calibrate_alert((validation.loc[valid,LABEL]!='BENIGN').to_numpy(),val_result['risk_score'][valid])
        config['alert_threshold']=threshold
        config['calibration']={'state':'frozen_before_test','partition':'validation','rows':len(validation),
                               'candidates':[25.,35.,45.,55.,65.,75.],
                               'objective':'maximum row-weighted balanced accuracy; highest threshold wins ties',
                               'selected_threshold':threshold,'no_rules_or_memberships_tuned_on_validation':True}
        engine=MamdaniRiskEngine(config)
        engine.save(CONFIG/f'{scenario}_v1.json')
        frozen[scenario]=engine.model_id
        pd.DataFrame([{k:r[k] for k in ['threshold','precision','recall','f1','false_positive_rate','balanced_accuracy']} for r in choices]).to_csv(REPORT/f'{scenario}_calibration.csv',index=False)
        # A class-preserving deterministic training diagnostic; parameters were
        # fitted on ALL appropriate train inputs, never this diagnostic's labels.
        diagnostic=training.assign(_priority=pd.util.hash_pandas_object(training.source_row_id ^ SEED,index=False).to_numpy())
        diagnostic=diagnostic.sort_values('_priority').groupby(LABEL,sort=True).head(1000).drop(columns='_priority')
        _,rules,coverage,seconds=score_frame(engine,diagnostic)
        rules.to_csv(REPORT/f'{scenario}_training_rules.csv',index=False)
        records[scenario]={'training_rows':len(training),'training_label_counts':training[LABEL].value_counts().to_dict(),
                           'validation_rows':len(validation),'validation_label_counts':validation[LABEL].value_counts().to_dict(),
                           'training_diagnostic_rows':len(diagnostic),'training_coverage':coverage,
                           'model_sha256':engine.model_id,'validation_abstentions':int((~valid).sum())}
        print(f'Frozen {scenario}: train={len(training):,}, validation={len(validation):,}, threshold={threshold}',flush=True)
    write_json(CONFIG/'frozen_manifest.json',{'version':'fuzzy-v1','seed':SEED,'models':frozen,'phases':['training_memberships_and_fixed_rules','validation_threshold_only','freeze','test_once'],
                                            'rule_sha256':hashlib.sha256(json.dumps(config['rules'],sort_keys=True).encode()).hexdigest()})
    write_json(REPORT/'fit_records.json',records)

def summarize_predictions(pred,threshold):
    valid=pred.status=='ok'; data=pred.loc[valid]
    truth=(data[LABEL]!='BENIGN').to_numpy(); score=data.risk_score.to_numpy()
    row=binary_metrics(truth,score,threshold)
    weights=1/data.groupby('observation_group_id').source_row_id.transform('size').to_numpy()
    grouped=binary_metrics(truth,score,threshold,weights)
    by_class=[]
    for label,g in data.groupby(LABEL,sort=True):
        is_attack=label!='BENIGN'
        alerts=int(g.alert.sum())
        by_class.append({'label':label,'support':len(g),'alert_count':alerts,
                         'false_negatives':len(g)-alerts if is_attack else 0,
                         'attack_recall':alerts/len(g) if is_attack else None,
                         'benign_false_positive_rate':alerts/len(g) if not is_attack else None,
                         'median_score':float(g.risk_score.median())})
    distribution=[]
    for name,mask in [('Benign',data[LABEL]=='BENIGN'),('Attack',data[LABEL]!='BENIGN')]:
        s=data.loc[mask,'risk_score']
        distribution.append({'traffic':name,'rows':len(s),'mean':float(s.mean()),'std':float(s.std()),
                             **dict(zip(['min','p05','p25','median','p75','p95','max'],map(float,s.quantile([0,.05,.25,.5,.75,.95,1]))))})
    return {'row_weighted':row,'observation_group_weighted':grouped,'abstentions':int((~valid).sum()),
            'unique_groups':int(data.observation_group_id.nunique())},pd.DataFrame(by_class),pd.DataFrame(distribution)

def evaluate():
    c=connect()
    frozen=json.loads((CONFIG/'frozen_manifest.json').read_text())
    results={}; examples=[]
    for scenario in ['grouped','day']:
        engine=MamdaniRiskEngine.load(CONFIG/f'{scenario}_v1.json')
        assert engine.model_id==frozen['models'][scenario],'Configuration changed after freeze'
        timings=[]; all_coverage=[]; rule_tables=[]
        path=GENERATED/f'{scenario}_test_predictions.parquet'
        writer=None
        # Query result is streamed; only the five inputs and compact metadata
        # are resident per outer batch. No loops over individual flow inference.
        reader=c.sql(query(scenario,'test')).to_arrow_reader(batch_size=8192)
        for batch in reader:
            frame=batch.to_pandas()
            pred,rules,coverage,seconds=score_frame(engine,frame)
            timings.append((len(frame),seconds)); all_coverage.append(coverage); rule_tables.append(rules)
            arrow=pa.Table.from_pandas(pred,preserve_index=False)
            if writer is None: writer=pq.ParquetWriter(path,arrow.schema,compression='zstd')
            writer.write_table(arrow)
        writer.close()
        pred=pd.read_parquet(path)
        metrics,classes,distribution=summarize_predictions(pred,engine.config['alert_threshold'])
        classes.to_csv(REPORT/f'{scenario}_per_class.csv',index=False)
        distribution.to_csv(REPORT/f'{scenario}_score_distribution.csv',index=False)
        counts=pd.concat(rule_tables).groupby(['rule_id','consequent'],sort=True).agg(
            rows=('rows','sum'),active_any=('active_any','sum'),active_meaningful=('active_meaningful','sum'),
            dominant_rows_first_tie=('dominant_rows_first_tie','sum'),active_benign=('active_benign','sum'),active_attack=('active_attack','sum'))
        counts['mean_strength']=sum(t.set_index(['rule_id','consequent']).mean_strength*t.set_index(['rule_id','consequent']).rows for t in rule_tables)/len(pred)
        counts.to_csv(REPORT/f'{scenario}_test_rules.csv')
        coverage={'rows':len(pred),'valid_scores':int((pred.status=='ok').sum()),
                  'any_rule_fraction':float((pred.active_rules>0).mean()),'multiple_rule_fraction':float((pred.active_rules>1).mean()),
                  'meaningful_rule_fraction':float((pred.meaningful_rules>0).mean()),'multiple_meaningful_rule_fraction':float((pred.meaningful_rules>1).mean()),
                  'conflicting_low_high_fraction':float(pred.conflicting_low_high.mean()),
                  'outside_training_range_fraction':float(pred.outside_training_range.mean())}
        total_seconds=sum(t[1] for t in timings)
        metrics['coverage']=coverage
        metrics['performance']={'rows':len(pred),'inference_seconds':total_seconds,'rows_per_second':len(pred)/total_seconds,
                                'timed_scope':'input coercion, memberships, rules, aggregation, centroid and output arrays; excludes coverage diagnostics, disk IO and metric sorting',
                                'outer_batch':8192,'centroid_batch':2048,'output_grid':201}
        fit_record=json.loads((REPORT/'fit_records.json').read_text(encoding='utf-8'))[scenario]
        metrics['test_labels_absent_from_training']=sorted(set(pred[LABEL])-set(fit_record['training_label_counts']))
        # Frozen, deterministic examples. No rule updates are made after viewing.
        error=pred.assign(error_type=np.where((pred[LABEL]=='BENIGN')&pred.alert,'false_positive',
                                np.where((pred[LABEL]!='BENIGN')&~pred.alert,'false_negative','correct')))
        error['_priority']=pd.util.hash_pandas_object(error.source_row_id ^ SEED,index=False).to_numpy()
        chosen=error.loc[error.error_type!='correct'].sort_values('_priority').groupby('error_type',sort=True).head(5)
        for row in chosen.itertuples(index=False):
            record=c.execute('SELECT '+','.join('"'+col+'"' for col in INPUTS)+f' FROM full_data WHERE source_row_id={row.source_row_id}').df().iloc[0].to_dict()
            explanation=engine.predict_one(record)
            actual=pred.loc[pred.source_row_id==row.source_row_id,LABEL].iloc[0]
            examples.append({'scenario':scenario,'source_row_id':int(row.source_row_id),'actual_label':actual,
                             'error_type':row.error_type,'inputs':record,'prediction':explanation,
                             'possible_error_reason':'Benign and attack aggregate behavior overlaps; conservative baseline and concern rules can conflict. No attack identity or severity is observable from these five aggregates.'})
        # Conflicting full-observation groups in this evaluation partition.
        conflicts=pred.groupby('observation_group_id')[LABEL].nunique()
        conflicting_ids=conflicts[conflicts>1].index
        metrics['label_ambiguity']={'conflicting_groups_in_test':len(conflicting_ids),
                                  'rows_in_conflicting_groups':int(pred.observation_group_id.isin(conflicting_ids).sum()),
                                  'rows_beyond_first_group_observation':int(len(pred)-pred.observation_group_id.nunique())}
        # Separate metrics for ambiguity-free observations, without changing model.
        unambiguous=pred.loc[~pred.observation_group_id.isin(conflicting_ids)]
        metrics['unambiguous_rows_only']=binary_metrics((unambiguous[LABEL]!='BENIGN').to_numpy(),unambiguous.risk_score.to_numpy(),engine.config['alert_threshold'])
        levels=pred.groupby([LABEL,'risk_level']).size().rename('count').reset_index()
        levels.to_csv(REPORT/f'{scenario}_risk_levels.csv',index=False)
        results[scenario]=metrics
        print(scenario,json.dumps(metrics['row_weighted']),flush=True)
        assert engine.model_id==config_digest(engine.config)==frozen['models'][scenario]
    write_json(REPORT/'metrics.json',results)
    write_json(REPORT/'error_examples.json',examples)
    # Example is a real evaluated record; structured explanations contain translation keys.
    write_json(REPORT/'example_prediction.json',examples[0])
    write_json(REPORT/'execution.json',{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
                                      'seed':SEED,'no_test_driven_rule_updates':True,'models':frozen['models']})

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['fit','evaluate','report','all'])
    phase=parser.parse_args().phase
    for path in [REPORT,CONFIG,GENERATED]: path.mkdir(parents=True,exist_ok=True)
    if phase in ['fit','all']: fit()
    if phase in ['evaluate','all']: evaluate()
    if phase in ['report','all']:
        if phase=='all':
            from validate_fuzzy import main as validate
            validate()
        from fuzzy_reports import render
        render()

if __name__=='__main__': main()
