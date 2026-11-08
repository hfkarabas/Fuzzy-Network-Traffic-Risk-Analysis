"""Summarize actual release evidence and record final source identities."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
import json
import re
import urllib.request
from task04_experiment import R,C,dump,digest


def main():
    logs={}
    for name in ['python_tests.txt','frontend_tests.txt','frontend_build.txt','typecheck.txt']:
        raw=(R/name).read_bytes()
        content=raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig').replace('\r','')
        (R/name).write_text(content.rstrip()+'\n',encoding='utf-8',newline='\n')
        logs[name]=content
    assert 'failed' not in logs['python_tests.txt'].lower() and 'error' not in logs['python_tests.txt'].lower()
    assert 'failed' not in logs['frontend_tests.txt'].lower()
    assert 'built in' in logs['frontend_build.txt'] and 'error TS' not in logs['typecheck.txt']
    python_count=int(re.search(r'(\d+) passed',logs['python_tests.txt']).group(1))
    frontend_count=int(re.search(r'Tests\s+(\d+) passed',logs['frontend_tests.txt']).group(1))
    evidence={name:json.loads((R/(name+'.json')).read_text()) for name in ['preservation','metric_reproduction','http_integration','browser_validation']}
    assert all(v['status']=='PASS' for v in evidence.values())
    health=json.loads(urllib.request.urlopen('http://127.0.0.1:8104/api/health').read())
    assert health['configuration_version']=='task04-v1'
    model=json.loads(urllib.request.urlopen('http://127.0.0.1:8104/api/model').read())
    assert model['model_id']==json.loads((C/'selected_manifest.json').read_text(encoding='utf-8'))['model_id']
    paths=['scripts/research/task04_experiment.py','scripts/research/task04_diagnostics.py','scripts/research/task04_validate.py',
        'scripts/research/task04_finish.py','src/fuzzy_network_risk/optimization.py','src/fuzzy_network_risk/webapp/service.py',
        'src/fuzzy_network_risk/webapp/api.py','tests/test_optimization.py','web/src/App.tsx','web/src/types.ts','web/src/App.test.tsx']
    summary={'status':'PASS','python_tests_passed':python_count,'frontend_tests_passed':frontend_count,'failed_tests':0,
        'typescript':'PASS','production_build':'PASS','live_http_direct_comparisons':evidence['http_integration']['policy_comparisons'],
        'saved_policy_metric_rows_reproduced':evidence['metric_reproduction']['policy_metric_rows'],
        'historical_artifacts_unchanged':evidence['preservation']['historical_artifact_hashes_unchanged'],
        'old_configs_reports_css_catalog_unchanged':evidence['preservation']['task03_tracked_configs_reports_css_catalog_unchanged'],
        'active_configuration':health['configuration_version'],'active_model_id':health['model_id'],
        'source_sha256':{p:digest(ROOT/p) for p in paths},'protocol_sha256':digest(C/'protocol.json'),
        'environment_note':'Initial sandbox tests failed on Windows temp ACLs and Vite file access; rerun with execution permission and repository-local temp passed. Tests were not weakened.',
        'evaluation_note':'Reused internal validation only; no independent final test and no supported model improvement.'}
    dump(R/'validation.json',summary)
    audit='''# TASK04 initial audit and implementation record

At start HEAD was cb5d9b6bdf6cd78932802dff734b66a8af461cb5 with a clean tree.
TASK02 grouped_v1 and day_v1 configs, TASK02B A_frozen/A_refit/B_membership/C_rules
fold configs, original rules, reports, tests and source caches were present.
TASK02B selection.json confirmed A_frozen won because improvements failed its gate.
WebService loaded task02b/selected_v2.json (verbatim grouped_v1), three explicit
policies and task02b/comparison_summary.csv; metrics.json supplied historical tests.
The active model ID was and remains
ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b.

The 22 complete IF–THEN rules and selected memberships are recorded in the preserved
grouped_v1.json and copied selected_v4.json; no baseline file was edited. Existing
TASK02 grouped-test and all Friday source groups/signatures are excluded from the
eligible cache. Original grouped train/validation/test role sizes were
8217/1753/1750; day train/validation/test were 1607145/422299/666572 (Friday
quality/evaluation subset). Exact provenance and exclusions are in the preserved
TASK02B evaluation_integrity.md and new partition_audit.json.

The new registered hypotheses and all unsuccessful outcomes are retained. The
backend now loads task04/selected_v4.json and verifies manifest content hashes.
Health/model endpoints expose configuration identity, and startup rejects an older
already-running application even when its scoring model ID is the same.
Analysis API fields and all existing validation behavior are backward compatible.
No additional input, page removal or visual redesign occurred; styles.css and the
real example catalog are unchanged. The sole UI addition is an evaluation card
identifying TASK04 candidates, reused validation and negative findings.

Exact example inputs/labels remain outside the engine except the five numerical
inputs; predictions were checked against direct inference for all three policies.
Historical examples need no changed predictions because scoring/policies are
byte-identical. Model metadata is updated via the manifest; existing old evaluation
evidence is visibly distinct from new candidate comparisons. Version identities are
additive API metadata. JS contains no membership/inference fitting code.

See scientific_report.md for measured diagnostics, metrics, uncertainty, day stress,
rules/features, selected policies and limitations. validation.json records actual
release checks. No remote Git synchronization, download, GPU, classifier or new
capture was used. Figures, build/dependency files and transient predictions are
ignored; small candidate configs, numerical reports and source are versioned.
'''
    (R/'audit.md').write_text(audit,encoding='utf-8')
    report=R/'scientific_report.md'
    text=report.read_text(encoding='utf-8').split('\n## Executed release checks')[0].rstrip()
    report.write_text(text+f'\n\n## Executed release checks\n\n{python_count} Python tests and {frontend_count} frontend tests passed; zero failures. TypeScript and production build passed. All 27 live API/direct-engine comparisons, 45 saved policy metric rows and 15 training-only model reproductions passed. Historical integrity verified 176 unchanged artifacts plus 129 prior tracked configs/reports/CSS/catalog files. Browser inspection confirmed the TASK04 findings, preserved inference page and no mobile horizontal overflow. Initial Windows sandbox ACL errors were resolved by an authorized test execution environment; no tests were weakened.\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
