"""Build a small curated catalog from eligible design records; no refitting/download."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import hashlib
import json
import numpy as np
import pandas as pd
from fuzzy_network_risk.data import INPUTS,LABEL
from fuzzy_network_risk.policy import PolicyRiskModel

def build():
    source=ROOT/'data/fuzzy_v2/internal_development.parquet'
    data=pd.read_parquet(source,filters=[('bucket','==','design')])
    model=PolicyRiskModel.load(ROOT/'config/fuzzy/task02b/selected_v2.json',ROOT/'config/fuzzy/task02b/selected_policies.json')
    policies=json.loads((ROOT/'config/fuzzy/task02b/selected_policies.json').read_text())
    predictions=model.predict_batch(data[INPUTS])
    data=data.copy(); data['score']=predictions['risk_score']; data['level']=predictions['risk_level']; data['alert']=predictions['alert']
    data['priority']=data.source_row_id.map(lambda v:hashlib.sha256(f'web-catalog-v1|{v}'.encode()).hexdigest())
    predicates=[('low','Düşük risk örneği',data.level=='Low'),('medium','Orta risk örneği',data.level=='Medium'),
                ('high','Yüksek risk örneği',data.level=='High'),('critical','Kritik risk örneği',data.level=='Critical'),
                ('benign','BENIGN etiketli akış',data[LABEL]=='BENIGN'),('attack','Saldırı etiketli akış',data[LABEL]!='BENIGN'),
                ('false-positive','Yanlış alarm örneği',(data[LABEL]=='BENIGN')&data.alert.astype(bool)),
                ('false-negative','Kaçırılan saldırı örneği',(data[LABEL]!='BENIGN')&~data.alert.astype(bool)),
                ('policy-contrast','Politika karşılaştırma örneği',(data.score>=model.threshold)&(data.score<policies['policies']['Conservative']['threshold']))]
    examples=[]; used=set(); unavailable=[]
    for key,title,mask in predicates:
        matching=data.loc[mask&~data.source_row_id.isin(used)].sort_values('priority')
        if matching.empty: unavailable.append(key); continue
        row=matching.iloc[0]; used.add(int(row.source_row_id)); values={c:float(row[c]) for c in INPUTS}
        prediction=model.predict_one(values)
        examples.append({'id':key,'title':title,'source_row_id':int(row.source_row_id),'source_day':row.capture_day,
                         'observation_group_id':str(row.observation_group_id),'signature':row.signature,
                         'dataset_label':row[LABEL],'features':values,'risk_score':prediction['risk_score'],
                         'risk_level':prediction['risk_level'],'alert':prediction['alert'],'reference_policy':'Balanced'})
    result={'version':'web-catalog-v1','model_id':model.engine.model_id,'source_artifact':'data/fuzzy_v2/internal_development.parquet',
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'TASK02B eligible design bucket only; curated illustrations, not performance estimates',
            'selection':'lowest SHA256(web-catalog-v1|source_row_id), unique rows within declared categories; policy contrast additionally bounded by Balanced/Conservative thresholds',
            'unavailable_categories':unavailable,'examples':examples}
    (ROOT/'web/catalog/examples.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Catalog: {len(examples)} real eligible examples; unavailable={unavailable}')

if __name__=='__main__': build()
