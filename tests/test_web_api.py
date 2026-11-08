from pathlib import Path
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from fuzzy_network_risk.data import INPUTS
from fuzzy_network_risk.membership import membership
from fuzzy_network_risk.webapp.api import create_app

@pytest.fixture(scope='module')
def client():
    with TestClient(create_app()) as c: yield c

@pytest.fixture
def request_body(client):
    example=next(e for e in client.get('/api/examples').json()['examples'] if e['id']=='policy-contrast')
    return {'features':dict(example['features']),'policy':'Balanced'}

def test_health_and_single_shared_model(client):
    response=client.get('/api/health'); assert response.status_code==200
    assert response.json()['model_loaded'] and response.json()['local_only']
    service=client.app.state.service
    assert all(m.engine is service.engine for m in service.models.values())

def test_model_and_authoritative_policies(client):
    model=client.get('/api/model').json(); assert len(model['features'])==5 and model['rule_count']==22
    assert model['dataset']['records']==2830743 and model['risk_category_cuts']==[25.,50.,75.]
    policies=client.get('/api/policies').json()
    assert policies['default']=='Balanced'
    for p in policies['policies']:
        assert p['threshold']==client.app.state.service.models[p['id']].threshold

def test_valid_inference_matches_direct_python(client,request_body):
    response=client.post('/api/analyze',json=request_body); assert response.status_code==200
    result=response.json(); direct=client.app.state.service.models['Balanced'].predict_one(request_body['features'])
    for key in ['status','risk_score','risk_level','alert','membership_degrees','model_id']: assert result[key]==direct[key]
    assert result['explanation'].startswith(f"{result['risk_level']} risk: ") and result['activated_rules']
    assert not any(key.endswith('_tr') for key in result)
    for api_rule,direct_rule in zip(result['activated_rules'],direct['activated_rules']):
        for key in ['id','strength','consequent','reason_key']: assert api_rule[key]==direct_rule[key]
        assert api_rule['text'].startswith('IF ') and ' THEN risk is ' in api_rule['text']
        assert api_rule['conditions'] in api_rule['text']

def test_policy_switch_only_alert_not_score(client,request_body):
    values={}
    for policy in ['Sensitive','Balanced','Conservative']:
        values[policy]=client.post('/api/analyze',json={**request_body,'policy':policy}).json()
    assert len({p['risk_score'] for p in values.values()})==1
    assert len({p['risk_level'] for p in values.values()})==1
    assert values['Balanced']['alert'] is True and values['Conservative']['alert'] is False
    assert values['Sensitive']['membership_degrees']==values['Conservative']['membership_degrees']

@pytest.mark.parametrize('invalid',[-1,'12','bad',True])
def test_strict_input_rejection(client,request_body,invalid):
    request_body['features'][INPUTS[0]]=invalid
    response=client.post('/api/analyze',json=request_body)
    assert response.status_code==422 and response.json()['risk_score'] is None and response.json()['alert'] is None
    assert response.json()['validation_errors']

@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity'])
def test_nonfinite_input_abstains_without_json_failure(client,request_body,token):
    body=json.dumps(request_body).replace(str(request_body['features'][INPUTS[0]]),token,1)
    response=client.post('/api/analyze',content=body,headers={'Content-Type':'application/json'})
    assert response.status_code==422 and response.json()['status']=='invalid_input'
    assert response.json()['risk_score'] is None

def test_missing_and_null_input(client,request_body):
    request_body['features'][INPUTS[0]]=None
    response=client.post('/api/analyze',json=request_body)
    assert response.status_code==200 and response.json()['status']=='invalid_input' and response.json()['alert'] is None
    del request_body['features'][INPUTS[0]]
    response=client.post('/api/analyze',json=request_body)
    assert response.status_code==422 and response.json()['risk_level'] is None

def test_labels_and_extra_keys_never_enter_engine(client,request_body):
    request_body['features'][' Label']='BENIGN'
    assert client.post('/api/analyze',json=request_body).status_code==422
    del request_body['features'][' Label']; request_body['dataset_label']='Attack'
    assert client.post('/api/analyze',json=request_body).status_code==422

def test_unknown_policy_and_malformed_json(client,request_body):
    assert client.post('/api/analyze',json={**request_body,'policy':'Unknown'}).status_code==422
    response=client.post('/api/analyze',content='{broken',headers={'Content-Type':'application/json'})
    assert response.status_code==422 and 'Traceback' not in response.text

def test_zero_and_extreme_finite_inputs(client):
    for value in [0,1e308]:
        response=client.post('/api/analyze',json={'features':{c:value for c in INPUTS},'policy':'Balanced'})
        assert response.status_code==200 and 0<=response.json()['risk_score']<=100
        assert all(0<=p<=1 for p in response.json()['input_positions'].values())

def test_curves_match_python_frozen_memberships(client):
    service=client.app.state.service
    for f in client.get('/api/model').json()['features']:
        spec=service.engine.config['features'][f['key']]
        x=np.asarray(f['chart']['values']); z=np.log1p(x) if spec['transform']=='log1p' else x
        for curve in f['chart']['curves']:
            np.testing.assert_allclose(curve['degrees'],membership(z,spec['sets'][curve['term']]),atol=1e-12)
        assert np.all(np.diff(f['chart']['positions'])>=0)

def test_catalog_integrity_and_actual_predictions(client):
    examples=client.get('/api/examples').json()
    assert len(examples['examples'])==9 and not examples['unavailable_categories']
    assert examples['curated_not_representative']
    assert len({e['source_row_id'] for e in examples['examples']})==9
    for e in examples['examples']:
        assert e['source_day']!='Friday' and set(e['features'])==set(INPUTS)
        actual=client.post('/api/analyze',json={'features':e['features'],'policy':'Balanced'}).json()
        assert actual['risk_score']==e['risk_score'] and actual['risk_level']==e['risk_level'] and actual['alert']==e['alert']
    fp=next(e for e in examples['examples'] if e['id']=='false-positive')
    fn=next(e for e in examples['examples'] if e['id']=='false-negative')
    assert fp['dataset_label']=='BENIGN' and fp['alert']
    assert fn['dataset_label']!='BENIGN' and not fn['alert']

def test_evaluation_values_match_recorded_sources(client):
    root=Path(__file__).resolve().parents[1]
    old=json.loads((root/'reports/fuzzy/metrics.json').read_text())
    evaluation=client.get('/api/evaluation').json()
    for row in evaluation['historical']: assert row['metrics']==old[row['id']]['row_weighted']
    balanced=next(row for row in evaluation['internal'] if row['id']=='Balanced')
    assert balanced['metrics']['false_positive_rate']==0.04910164828843657
    assert balanced['pooled_row_fpr']==0.1570775556066294
    assert not evaluation['independent_holdout']

def test_openapi_and_offline_docs(client):
    schema=client.get('/openapi.json').json()
    assert '/api/analyze' in schema['paths'] and 'dataset_label' not in json.dumps(schema['components']['schemas']['AnalyzeRequest'])
    docs=client.get('/docs'); assert docs.status_code==200 and 'cdn.' not in docs.text and '<script src="http' not in docs.text

def test_host_restriction(client):
    assert client.get('/api/health',headers={'Host':'outside.example'}).status_code==400

def test_unexpected_errors_do_not_expose_stack_traces(monkeypatch):
    with TestClient(create_app(),raise_server_exceptions=False) as c:
        def fail(*args,**kwargs): raise RuntimeError('private internal path must not be exposed')
        monkeypatch.setattr(c.app.state.service,'analyze',fail)
        example=c.get('/api/examples').json()['examples'][0]
        response=c.post('/api/analyze',json={'features':example['features'],'policy':'Balanced'})
        assert response.status_code==500 and 'private internal path' not in response.text and 'Traceback' not in response.text


def test_api_content_is_english_only(client,request_body):
    # Guards the English-only interface: no Turkish-specific letters in any served text.
    turkish=set('çğıöşüÇĞİÖŞÜ')
    payloads=[client.get(path).json() for path in ['/api/model','/api/policies','/api/examples','/api/evaluation']]
    payloads+=[client.post('/api/analyze',json={**request_body,'policy':p}).json() for p in ['Sensitive','Balanced','Conservative']]
    payloads.append(client.post('/api/analyze',json={'features':{}}).json())
    payloads.append(client.get('/docs').text)
    text=json.dumps(payloads,ensure_ascii=False)
    assert not turkish&set(text), sorted(turkish&set(text))
