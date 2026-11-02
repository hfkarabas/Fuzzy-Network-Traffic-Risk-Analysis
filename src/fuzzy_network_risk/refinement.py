"""TASK02B group-aware internal development utilities, independent of old tests."""
from copy import deepcopy
import hashlib
import numpy as np
import pandas as pd
from .data import INPUTS,LABEL
from .calibration import fit_config
from .evaluation import binary_metrics

SEED=20261104
POLICIES={'Sensitive':.10,'Balanced':.05,'Conservative':.01}

def signature(values):
    x=np.asarray(values,dtype=float)
    if x.shape[-1]!=5 or not (np.isfinite(x)&(x>=0)).all():
        raise ValueError('Signature requires five valid inputs')
    bins=np.floor(np.log1p(x[...,:4])/.1+.5).astype('int64')
    ratio=x[...,4]
    if not (ratio==np.floor(ratio)).all(): raise ValueError('Source ratio must be integral')
    flat=np.column_stack([bins.reshape(-1,4),ratio.reshape(-1).astype('int64')])
    return np.array([':'.join(map(str,row)) for row in flat])

def assignment(group,seed=SEED):
    digest=hashlib.sha256((str(group)+'|'+str(seed)).encode()).hexdigest()
    number=int(digest[:12],16)
    return 'design' if number%5==0 else str((number//5)%3)

def roles(frame,fold):
    if fold not in [0,1,2]: raise ValueError('Unknown fold')
    return (frame.loc[frame.bucket==str((fold+2)%3)],frame.loc[frame.bucket==str((fold+1)%3)],frame.loc[frame.bucket==str(fold)])

def check_lineage(frame,exposed_ids,exposed_groups,exposed_signatures):
    if frame.source_row_id.isin(exposed_ids).any() or frame.observation_group_id.isin(exposed_groups).any() or frame.signature.isin(exposed_signatures).any():
        raise ValueError('Exposed evidence contaminated development')
    if frame.groupby('signature').bucket.nunique().max()>1:
        raise ValueError('Signature crossed partitions')
    if frame.groupby('observation_group_id').bucket.nunique().max()>1:
        raise ValueError('Original observation group crossed partitions')
    return True

def group_weights(frame):
    return 1/frame.groupby('signature').source_row_id.transform('size').to_numpy()

def threshold_curve(y,scores,weights):
    """Exact tied-score tradeoff, including a no-alert operating point at 100."""
    y=np.asarray(y,dtype=bool); s=np.asarray(scores,dtype=float); w=np.asarray(weights,dtype=float)
    if not len(y) or not np.isfinite(s).all() or y.all() or not y.any():
        raise ValueError('Calibration requires finite scores and both traffic types')
    order=np.argsort(-s,kind='stable'); s=s[order]; y=y[order]; w=w[order]
    ends=np.r_[np.flatnonzero(s[1:]!=s[:-1]),len(s)-1]
    tp=np.cumsum(w*y)[ends]; fp=np.cumsum(w*~y)[ends]
    p=w[y].sum(); n=w[~y].sum()
    curve=pd.DataFrame({'threshold':s[ends],'tp':tp,'fp':fp,'fn':p-tp,'tn':n-fp,
                        'recall':tp/p,'fpr':fp/n,'precision':tp/(tp+fp)})
    noalert=pd.DataFrame([dict(threshold=100.,tp=0.,fp=0.,fn=p,tn=n,recall=0.,fpr=0.,precision=0.)])
    # Production centroids have maximum below 100; if a future score is exactly
    # 100 the row at threshold 100 must reflect its actual alerts.
    if s.max()<100: curve=pd.concat([noalert,curve],ignore_index=True)
    return curve

def select_policies(y,scores,weights):
    curve=threshold_curve(y,scores,weights)
    result={}
    for name,cap in POLICIES.items():
        feasible=curve.loc[curve.fpr<=cap+1e-12].sort_values(['recall','fpr','threshold'],ascending=[False,True,False])
        if feasible.empty:
            result[name]={'threshold':100.,'calibration_feasible':False,'fpr_cap':cap}
        else:
            best=feasible.iloc[0]
            result[name]={'threshold':float(best.threshold),'fpr_cap':cap,'calibration_feasible':True,
                          'calibration_fpr':float(best.fpr),'calibration_recall':float(best.recall),
                          'nontrivial_recall_feasible':bool(best.recall>0)}
    return result,curve

def membership_candidate(training,name):
    if name=='A_refit': return fit_config(training[INPUTS],f'task02b-{name}')
    if name not in ['B_membership','C_rules']: raise ValueError('Unknown candidate')
    # BENIGN reference is chosen on training labels only; no target enters engine.
    benign=training.loc[training[LABEL]=='BENIGN',INPUTS]
    if len(benign)<30: raise ValueError('Insufficient benign reference training rows')
    config=fit_config(benign,f'task02b-{name}')
    config['version']='fuzzy-v2-'+name
    config['fit_rows']=len(training)
    config['reference_rows']=len(benign)
    for key,f in config['features'].items():
        c=f['column']; raw=training[c].to_numpy()
        if key!='balance':
            reference=benign[c].to_numpy()
            if key=='variation' and (reference>0).sum()>=3: reference=reference[reference>0]
            anchors=list(map(float,np.quantile(reference,[.25,.75,.95])))
            # Domain constraints: small/medium packet sets must include ordinary
            # 64-byte frames; few packets includes request/response transactions.
            if key=='size': anchors=[max(16.,anchors[0]),max(64.,anchors[1]),max(256.,anchors[2])]
            if key=='volume': anchors=[max(2.,anchors[0]),max(4.,anchors[1]),max(16.,anchors[2])]
            delta=max(1.,anchors[0]*.01)
            anchors[1]=max(anchors[1],anchors[0]+delta); anchors[2]=max(anchors[2],anchors[1]+delta)
            f['raw_anchors']=anchors
            a,b,c=[float(np.log1p(v)) if f['transform']=='log1p' else v for v in anchors]
            upper=max(c,float(np.log1p(raw.max())) if f['transform']=='log1p' else float(raw.max()))
            terms=list(f['sets'])
            f['sets']={terms[0]:{'kind':'trapezoid','parameters':[0.,0.,a,b]},terms[1]:{'kind':'triangle','parameters':[a,b,c]},
                       terms[2]:{'kind':'trapezoid','parameters':[b,c,upper,upper]}}
            f['upper']=upper; f['anchor_basis']='training_benign_p25_p75_p95_with_declared_domain_floors'
        f['training_min']=float(raw.min()); f['training_max']=float(raw.max())
    if name=='C_rules':
        config['rules']=refined_rules()
    return config

def refined_rules():
    """Fixed after design-only diagnostics and before any comparison fold results."""
    from .rules import rule
    return [
        rule('V201',[('rate','sparse'),('volume','few')],'Low','Sparse small exchanges carry weak load evidence; low-volume attacks remain possible.'),
        rule('V202',[('rate','sparse'),('volume','moderate')],'Low','Modest low-rate exchanges do not justify alerts from volume alone.'),
        rule('V203',[('rate','sparse'),('volume','many')],'Low','Long low-rate transfers require corroborating concern patterns, not an unconditional Medium output.'),
        rule('V204',[('rate','moderate'),('volume','few')],'Low','Routine short transactions form a conservative baseline.'),
        rule('V205',[('rate','moderate'),('volume','moderate')],'Low','Ordinary rate and volume are weak attack evidence.'),
        rule('V206',[('rate','moderate'),('volume','many')],'Medium','Sustained volume warrants context but is not definitive.'),
        rule('V207',[('rate','intensive'),('volume','few')],'Low','A few-packet rate spike can be denominator inflation; require corroboration.'),
        rule('V208',[('rate','intensive'),('volume','moderate')],'Medium','Nontrivial volume and intensity merit investigation.'),
        rule('V209',[('rate','intensive'),('volume','many')],'High','Joint high volume and rate support load concern.'),
        rule('V210',[('rate','intensive'),('volume','many'),('size','small'),('balance','forward')],'Critical','A sustained high-rate small-packet imbalance is more specific than a few-packet burst.'),
        rule('V211',[('rate','intensive'),('volume','moderate'),('size','small'),('balance','forward')],'High','Repeated high-rate small forward-dominated packets provide joint concern.'),
        rule('V212',[('volume','many'),('size','small'),('balance','forward')],'High','Many small forward-dominated packets warrant context beyond rate.'),
        rule('V213',[('volume','many'),('size','large'),('variation','highly_variable')],'High','High-volume large varied responses can indicate resource pressure; legitimate transfers overlap.'),
        rule('V214',[('rate','sparse'),('size','large'),('variation','highly_variable')],'Medium','Large response variability at low rates remains ambiguous.'),
        rule('V215',[('rate','moderate'),('volume','many'),('size','large'),('variation','highly_variable')],'High','Require corroborating packet volume before elevating large varied responses.'),
        rule('V216',[('rate','moderate'),('size','medium'),('balance','balanced')],'Low','Balanced ordinary-size traffic supports a benign counter-hypothesis.'),
        rule('V217',[('rate','sparse'),('size','medium'),('balance','balanced')],'Low','Low-intensity balanced transactions support weak concern.'),
        rule('V218',[('rate','intensive'),('size','large'),('balance','backward')],'Medium','A rapid backward-heavy payload transfer can be an ordinary download.'),
    ]

def choose_candidate(summary,improvement_lower):
    """Pre-registered rule: no objective changes after seeing validation results."""
    base=summary['A_refit']
    eligible=[k for k,v in summary.items() if k not in ['A_refit','A_frozen'] and v['fpr']<=.075 and
              v['balanced_accuracy']-base['balanced_accuracy']>=.02 and improvement_lower.get(k,-np.inf)>0]
    return max(eligible,key=lambda k:(summary[k]['balanced_accuracy'],k)) if eligible else 'A_frozen'
