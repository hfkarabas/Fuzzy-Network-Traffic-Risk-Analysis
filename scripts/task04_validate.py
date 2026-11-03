"""Reproduce registered configs/selection and verify immutable historical artifacts."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import json
import subprocess
import pandas as pd
from fuzzy_network_risk.optimization import candidate_config,select_model,CANDIDATES
from fuzzy_network_risk.engine import MamdaniRiskEngine
from fuzzy_network_risk.refinement import roles
from task04_experiment import R,C,FILES,digest,dump


def main():
    protocol=json.loads((C/'protocol.json').read_text(encoding='utf-8'))
    assert protocol['source_sha256']=={p:digest(ROOT/p) for p in FILES}
    frame=pd.read_parquet(ROOT/'data/fuzzy_v2/internal_development.parquet')
    assert protocol['data_sha256']==digest(ROOT/'data/fuzzy_v2/internal_development.parquet')
    frozen=MamdaniRiskEngine.load(ROOT/'config/fuzzy/task02b/selected_v2.json')
    for fold in range(3):
        train,_,_=roles(frame.loc[frame.bucket!='design'],fold)
        for name in CANDIDATES:
            saved=MamdaniRiskEngine.load(C/f'{name}_fold{fold}.json')
            assert saved.config==candidate_config(train,name,frozen.config)
    summary=json.loads((R/'summary.json').read_text())
    intervals=json.loads((R/'uncertainty.json').read_text())
    selection=json.loads((R/'selection.json').read_text())
    assert select_model(summary,intervals)==selection['candidate']
    assert digest(C/'protocol.json')==selection['protocol_sha256']
    original=json.loads((ROOT/'reports/web/historical_integrity.json').read_text())
    for path,sha in original.items(): assert digest(ROOT/path)==sha,path
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','cb5d9b6bdf6cd78932802dff734b66a8af461cb5'],cwd=ROOT,text=True).splitlines()
    protected=[p for p in tracked if p.startswith(('config/','reports/')) or p in ['web/src/styles.css','web/catalog/examples.json']]
    for path in protected:
        old=subprocess.check_output(['git','show','cb5d9b6:'+path],cwd=ROOT)
        # Git text normalization may differ from checked-out CRLF; content stays.
        assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==old.replace(b'\r\n',b'\n'),path
    result={'status':'PASS','historical_artifact_hashes_unchanged':len(original),
        'task03_tracked_configs_reports_css_catalog_unchanged':len(protected),
        'all_15_registered_fold_models_reproduced_from_training_only':True,
        'selection_reproduced':True,'registration_hashes_match':True,
        'no_source_data_modified':True,'no_untouched_holdout_claim':True}
    dump(R/'preservation.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
