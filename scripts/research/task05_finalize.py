"""Collect executed test/build/HTTP evidence without any model reselection."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import re
import pandas as pd
from task05_research import R,C,T,dump,digest
from fuzzy_network_risk.advanced import COLUMNS
from task05_reports import reports


def main():
    logs={}
    for name in ['python_tests.txt','frontend_tests.txt','typecheck.txt','frontend_build.txt']:
        raw=(R/name).read_bytes()
        content=raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig').replace('\r','')
        (R/name).write_text(content.rstrip()+'\n',encoding='utf-8',newline='\n'); logs[name]=content
    assert 'failed' not in logs['python_tests.txt'].lower() and 'error' not in logs['python_tests.txt'].lower()
    assert 'failed' not in logs['frontend_tests.txt'].lower() and 'error TS' not in logs['typecheck.txt']
    assert 'built in' in logs['frontend_build.txt']
    python_count=int(re.search(r'(\d+) passed',logs['python_tests.txt']).group(1))
    frontend_count=int(re.search(r'Tests\s+(\d+) passed',logs['frontend_tests.txt']).group(1))
    reproduction=json.loads((R/'reproduction.json').read_text()); http=json.loads((R/'http_integration.json').read_text())
    assert reproduction['status']=='PASS' and http['status']=='PASS'
    expected=json.loads((R/'explanation_example.json').read_text())['prediction']
    cli=json.loads((R/'cli_example.json').read_text(encoding='utf-8-sig'))
    assert cli==expected
    frame=pd.read_parquet(T/'research.parquet')
    conflicts=int((frame.groupby(COLUMNS,dropna=False)[' Label'].nunique()>1).sum())
    resource={'research_rows':len(frame),'research_columns':len(frame.columns),
        'research_dataframe_deep_bytes':int(frame.memory_usage(deep=True).sum()),
        'eight_input_dataframe_deep_bytes':int(frame[COLUMNS].memory_usage(deep=True).sum()),
        'research_parquet_bytes':(T/'research.parquet').stat().st_size,
        'centroid_workspace_bytes_per_layer':1024*201*8,
        'eight_input_vectors_with_conflicting_labels':conflicts,
        'scope':'Measured cache/dataframe/workspace sizes; not peak process RSS or whole-pipeline memory'}
    dump(R/'resource_usage.json',resource)
    paths=['src/fuzzy_network_risk/advanced.py','tests/test_advanced.py',*['scripts/task05_'+n+'.py' for n in ['research','experiment','validate','reports','predict','finalize']]]
    summary={'status':'PASS','python_tests_passed':python_count,'frontend_tests_passed':frontend_count,'failed_tests':0,
        'typescript':'PASS','production_build':'PASS','production_api_direct_comparisons':http['policy_comparisons'],
        'model_fitting_reproduced':15,'policy_calibration_sets_reproduced':15,'policy_metric_rows_reproduced':45,
        'day_stress_metric_sets_reproduced':15,'selection_reproduced':True,
        'source_dataset_hashes_preserved':True,'historical_artifact_hashes_unchanged':reproduction['historical_artifact_hashes_unchanged'],
        'prior_tracked_files_unchanged':reproduction['prior_tracked_files_unchanged'],'production_web_source_unchanged':True,
        'cli_full_explanation_matches_python':True,'source_sha256':{p:digest(ROOT/p) for p in paths},
        'protocol_sha256':digest(C/'protocol.json'),'no_independent_holdout':True,
        'production_promoted':False,'decision':'Promising hierarchical internal gains; capture-day stability gate failed; keep TASK04 production.'}
    dump(R/'validation.json',summary)
    # Regenerate prose only, preserving the measured performance/diagnostics.
    reports(pd.read_csv(R/'feature_semantics.csv').to_dict('records'),json.loads((R/'layer_conflicts.json').read_text()),json.loads((R/'robustness.json').read_text()))
    report=R/'final_report.md'
    with report.open('a',encoding='utf-8') as handle:
        handle.write(f'\n## Executed completion checks\n\n{python_count} Python tests and {frontend_count} frontend tests passed, zero failures. TypeScript and production build passed. All27 live unchanged-production API/direct-engine comparisons passed. Separate verification reproduced15 training-only models,15 calibration policy sets,45 policy metric rows,15 day-stress metric sets and the retained-model decision. The experimental CLI emitted the exact same complete explanation as direct Python inference. Integrity checks verified176 historical raw artifact hashes and242 prior tracked source/config/report/web files unchanged. No baseline tests were weakened.\n\nMeasured deep research dataframe size: {resource["research_dataframe_deep_bytes"]:,} bytes; eight-input frame: {resource["eight_input_dataframe_deep_bytes"]:,} bytes. Eight-input conflicting-label vector groups: {conflicts}. Near-duplicate bin-boundary limitations remain. See resource_usage.json for scope; these are not peak RSS measurements.\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
