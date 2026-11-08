"""Small-column diagnostics used to choose the input schema before final export."""
import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
from acquire import acquire, ROOT
import pandas as pd
import numpy as np
import json

def inspect(table=None):
    if table is None:
        table = acquire()['train'].data.table
    columns = [' Flow Duration',' Flow Packets/s',' Packet Length Mean',' Bwd Packet Length Std',
               ' SYN Flag Count',' Total Fwd Packets',' Down/Up Ratio',' Flow IAT Mean','Active Mean',' PSH Flag Count']
    frame = table.select(columns).to_pandas().astype('float64')
    frame = frame.where(np.isfinite(frame) & (frame >= 0))
    corr = frame.corr(method='spearman')
    corr.to_csv(ROOT / 'reports/dataset/expanded_candidate_spearman.csv')
    print(corr.to_string(), flush=True)
    pairs = [(' Fwd Header Length',' Fwd Header Length.1'),(' Total Fwd Packets','Subflow Fwd Packets'),
             ('Total Length of Fwd Packets',' Subflow Fwd Bytes'),(' Total Backward Packets',' Subflow Bwd Packets'),
             (' Total Length of Bwd Packets',' Subflow Bwd Bytes'),(' Fwd Packet Length Mean',' Avg Fwd Segment Size'),
             (' Bwd Packet Length Mean',' Avg Bwd Segment Size')]
    results = []
    for a,b in pairs:
        x,y = table[a].to_numpy(), table[b].to_numpy()
        equal = (x == y) | (np.isnan(x) & np.isnan(y))
        results.append({'left':a,'right':b,'equal_rows':int(equal.sum()),'total_rows':len(x),'exact_alias':bool(equal.all())})
    (ROOT / 'reports/dataset/redundancy.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

if __name__ == '__main__':
    inspect()
