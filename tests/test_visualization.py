"""Read-only output diagnostics must exactly preserve frozen predictions."""
import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from fuzzy_network_risk.webapp.api import create_app
from fuzzy_network_risk.membership import centroid
from json_compare import assert_json_close

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def client():
    with TestClient(create_app()) as c: yield c


def test_output_curves_aggregate_centroid_and_unchanged_predictions(client):
    service=client.app.state.service
    replay=json.loads((ROOT/'web/src/live-test-fixture.json').read_text(encoding='utf-8'))
    vectors=[example['features'] for example in service.examples]+[row['features'] for row in replay['flows']]
    for vector in vectors:
        before=service.analyze(vector,'Balanced')
        responses=[client.post('/api/visualization/output',json={'features':vector,'policy':policy}) for policy in service.models]
        assert all(response.status_code==200 for response in responses)
        output=responses[0].json()
        assert all(response.json()==output for response in responses)
        assert output['model_id']==service.engine.model_id
        assert output['centroid']==before['risk_score']
        np.testing.assert_array_equal(output['grid'],service.engine.grid)
        for i,curve in enumerate(output['curves']):
            np.testing.assert_array_equal(curve['degrees'],service.engine.output_sets[i])
        aggregate=np.zeros(len(service.engine.grid))
        for rule in before['activated_rules']:
            index=['Low','Medium','High','Critical'].index(rule['consequent'])
            aggregate=np.maximum(aggregate,np.minimum(rule['strength'],service.engine.output_sets[index]))
        np.testing.assert_array_equal(output['aggregate'],aggregate)
        assert float(centroid(output['grid'],output['aggregate']))==output['centroid']
        assert service.analyze(vector,'Balanced')==before


def test_invalid_and_no_rule_outputs_have_no_plot(client):
    service=client.app.state.service; vector=dict(service.examples[0]['features'])
    vector[service.engine.columns[0]]=None
    response=client.post('/api/visualization/output',json={'features':vector})
    assert response.status_code==200
    assert response.json()=={'status':'invalid_input','model_id':service.engine.model_id,'centroid':None,'grid':[],'curves':[],'aggregate':[]}
    from fuzzy_network_risk.engine import MamdaniRiskEngine
    config=json.loads(json.dumps(service.engine.config)); config['rules']=[]
    empty=MamdaniRiskEngine(config).output_visualization(service.examples[0]['features'])
    assert empty['status']=='no_rule_activation' and empty['centroid'] is None and empty['aggregate']==[]


def test_labels_invalid_numbers_and_missing_features_rejected(client):
    vector=dict(client.app.state.service.examples[0]['features'])
    assert client.post('/api/visualization/output',json={'features':vector|{' Label':'BENIGN'}}).status_code==422
    assert client.post('/api/visualization/output',json={'features':{}}).status_code==422
    key=next(iter(vector))
    assert client.post('/api/visualization/output',json={'features':vector|{key:-1}}).status_code==422
    for token in ['NaN','Infinity','-Infinity']:
        body=json.dumps({'features':vector}).replace(str(vector[key]),token,1)
        assert client.post('/api/visualization/output',content=body,headers={'Content-Type':'application/json'}).status_code==422


def test_new_plot_fixture_is_actual_output_and_old_references_unchanged(client):
    # Fixtures were captured on another platform: compare floats with a tight
    # tolerance, everything else (levels, alerts, rules, keys) exactly.
    output=json.loads((ROOT/'web/src/visualization-test-fixture.json').read_text(encoding='utf-8'))
    historical=json.loads((ROOT/'web/src/test-fixture.json').read_text(encoding='utf-8'))
    live=json.loads((ROOT/'web/src/live-test-fixture.json').read_text(encoding='utf-8'))
    engine=client.app.state.service.engine
    assert_json_close(engine.output_visualization(historical['analyses']['policy-contrast']['Balanced']['input_values']),output['historical'])
    for policies in historical['analyses'].values():
        for policy,reference in policies.items():
            actual=client.post('/api/analyze',json={'features':reference['input_values'],'policy':policy})
            assert actual.status_code==200
            assert_json_close(actual.json(),reference)
    for row in live['flows']:
        assert_json_close(engine.output_visualization(row['features']),output[row['protocol'].lower()])
        assert_json_close(client.app.state.service.analyze(row['features'],'Balanced'),row['analysis'])
    for protocol in ('tcp','udp'):
        for policy,reference in output['liveAnalyses'][protocol].items():
            assert_json_close(client.app.state.service.analyze(reference['input_values'],policy),reference)
