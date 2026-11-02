"""Unsupervised, training-only membership anchors; fixed interpretable rule base."""
import numpy as np
from .data import INPUTS, SEED
from .rules import default_rules

KEYS=['rate','volume','size','variation','balance']
TERMS=[['sparse','moderate','intensive'],['few','moderate','many'],['small','medium','large'],
       ['uniform','variable','highly_variable'],['forward','balanced','backward']]
UNITS=['packets/second','packets','bytes','bytes','dimensionless']

def fit_config(training_inputs,scenario):
    if set(training_inputs.columns)!=set(INPUTS):
        raise ValueError('Fit accepts behavior inputs only; training labels/metadata must be removed')
    features={}
    for key,column,terms,unit in zip(KEYS,INPUTS,TERMS,UNITS):
        x=training_inputs[column].to_numpy(dtype='float64')
        if len(x)==0 or not (np.isfinite(x)&(x>=0)).all():
            raise ValueError('Training inputs must be nonempty finite nonnegative measurements')
        transform='log1p' if key in ['rate','volume','variation'] else 'identity'
        positive=x[x>0]
        # Positive-subset anchors distinguish variation from the point mass at zero.
        anchor_population=positive if key=='variation' and len(positive)>=3 else x
        a,b,c=map(float,np.quantile(anchor_population,[.25,.60,.90]))
        basis='training_positive_p25_p60_p90' if key=='variation' and len(positive)>=3 else 'training_p25_p60_p90'
        if key=='balance':
            a,b,c=0.,1.,2.
            basis='domain_backward_forward_ratio_0_1_2'
        # Repeated quantiles are legitimate in discrete/zero-heavy data. Expand
        # deterministically by one physical count/byte or a positive relative step.
        delta=max(1.,abs(a)*.01)
        b=max(b,a+delta); c=max(c,b+delta)
        anchors_raw=[a,b,c]
        z=lambda v:float(np.log1p(v)) if transform=='log1p' else float(v)
        a,b,c=map(z,anchors_raw)
        upper=max(z(float(x.max())),c)
        features[key]={'column':column,'unit':unit,'transform':transform,'upper':upper,
                       'training_min':float(x.min()),'training_max':float(x.max()),
                       'anchor_basis':basis,'raw_anchors':anchors_raw,
                       'training_quantiles':dict(zip(['p01','p25','p50','p60','p75','p90','p95','p99'],
                                                     map(float,np.quantile(x,[.01,.25,.50,.60,.75,.90,.95,.99])))),
                       'zero_fraction':float((x==0).mean()),
                       'sets':{terms[0]:{'kind':'trapezoid','parameters':[0.,0.,a,b]},
                               terms[1]:{'kind':'triangle','parameters':[a,b,c]},
                               terms[2]:{'kind':'trapezoid','parameters':[b,c,upper,upper]}}}
    return {'version':'fuzzy-v1','scenario':scenario,'seed':SEED,'method':'mamdani-min-max-centroid',
            'fit_rows':len(training_inputs),'features':features,'rules':default_rules(),
            'output':{'grid_points':201,'sets':{
                'Low':{'kind':'trapezoid','parameters':[0.,0.,15.,35.]},
                'Medium':{'kind':'triangle','parameters':[20.,45.,65.]},
                'High':{'kind':'triangle','parameters':[50.,70.,85.]},
                'Critical':{'kind':'trapezoid','parameters':[75.,90.,100.,100.]}}},
            'risk_level_thresholds':[25.,50.,75.],'alert_threshold':50.,
            'calibration':{'state':'training_only_uncalibrated','candidates':[25.,35.,45.,55.,65.,75.]},
            'policies':{'invalid':'abstain','no_rule':'abstain','extreme':'saturate_transformed_domain_shoulders',
                        'risk_score':'behavioral_index_not_attack_probability','meaningful_activation':.1}}
