"""The scoring CLI must reproduce the deployed web decision, not legacy thresholds."""
import io
import json
from pathlib import Path
import pytest
import score_flow
from fuzzy_network_risk.webapp.service import WebService
from json_compare import assert_json_close

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {e['id']: e for e in json.loads((ROOT / 'web/catalog/examples.json').read_text(encoding='utf-8'))['examples']}


def run(argv, payload):
    stdout, stderr = io.StringIO(), io.StringIO()
    code = score_flow.main(argv, io.StringIO(json.dumps(payload)), stdout, stderr)
    return code, (json.loads(stdout.getvalue()) if stdout.getvalue() else None), stderr.getvalue()


@pytest.fixture(scope='module')
def service():
    return WebService()


def test_default_matches_deployed_balanced_policy(service):
    features = CATALOG['medium']['features']        # score ~37.8: between 25 and 51.8
    code, result, _ = run([], features)
    assert code == score_flow.EXIT_OK
    assert result['alert_policy']['name'] == 'Balanced'
    assert result['alert_policy']['threshold'] == service.models['Balanced'].threshold
    assert result['alert'] is False                 # legacy embedded threshold 25 would alert
    expected = service.models['Balanced'].predict_one(features)
    assert_json_close(result, expected)


@pytest.mark.parametrize('policy,alert', [('Sensitive', True), ('Balanced', True), ('Conservative', False)])
def test_policy_changes_only_the_alert_decision(policy, alert):
    features = CATALOG['policy-contrast']['features']   # score ~53.3
    code, result, _ = run(['--policy', policy], features)
    assert code == score_flow.EXIT_OK
    assert result['alert'] is alert and result['alert_policy']['name'] == policy
    assert result['risk_score'] == pytest.approx(CATALOG['policy-contrast']['risk_score'], rel=1e-12)


def test_embedded_threshold_is_explicit_opt_in():
    code, result, _ = run(['--embedded-threshold'], CATALOG['medium']['features'])
    assert code == score_flow.EXIT_OK and result['alert'] is True
    assert result['alert_policy'] == {'name': 'embedded', 'threshold': 25.0, 'historical_metadata_only': True}
    with pytest.raises(SystemExit):
        score_flow.parse_args(['--embedded-threshold', '--policy', 'Balanced'])


def test_batch_input_and_abstention_exit_code():
    features = CATALOG['low']['features']
    invalid = dict(features, **{' Flow Packets/s': -1})
    code, results, _ = run([], [features, invalid])
    assert code == score_flow.EXIT_ABSTAINED
    assert [r['status'] for r in results] == ['ok', 'invalid_input']
    assert results[1]['risk_score'] is None and results[1]['alert'] is None


@pytest.mark.parametrize('payload,message', [
    ({**CATALOG['low']['features'], ' Label': 'BENIGN'}, 'approved input columns'),
    ([], 'non-empty array'),
    ('text', 'JSON object'),
])
def test_schema_errors_exit_2_without_output(payload, message):
    code, result, error = run([], payload)
    assert code == score_flow.EXIT_ERROR and result is None and message in error


def test_invalid_json_and_mismatched_policy_file(tmp_path):
    stdout, stderr = io.StringIO(), io.StringIO()
    assert score_flow.main([], io.StringIO('{broken'), stdout, stderr) == score_flow.EXIT_ERROR
    assert 'not valid JSON' in stderr.getvalue()
    # The historical day model has no policy calibrated for it.
    code, _, error = run(['--model', str(ROOT / 'config/fuzzy/day_v1.json')], CATALOG['low']['features'])
    assert code == score_flow.EXIT_ERROR and 'mismatch' in error


def test_tampered_deployed_configuration_is_refused(monkeypatch, tmp_path):
    tampered = tmp_path / 'selected_v4.json'
    tampered.write_text(score_flow.DEFAULT_MODEL.read_text(encoding='utf-8') + ' ', encoding='utf-8')
    monkeypatch.setattr(score_flow, 'DEFAULT_MODEL', tampered)
    code, _, error = run(['--model', str(tampered)], CATALOG['low']['features'])
    assert code == score_flow.EXIT_ERROR and 'hash mismatch' in error


def test_input_file_relative_to_working_directory(tmp_path, monkeypatch):
    (tmp_path / 'flow.json').write_text(json.dumps(CATALOG['critical']['features']), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    code, result, _ = run(['--input', 'flow.json', '--compact'], None)
    assert code == score_flow.EXIT_OK and result['risk_level'] == 'Critical'


def test_script_runs_from_any_directory(tmp_path):
    import subprocess
    import sys
    completed = subprocess.run([sys.executable, str(ROOT / 'scripts/score_flow.py'), '--compact'],
                               input=json.dumps(CATALOG['low']['features']), capture_output=True,
                               text=True, cwd=tmp_path, timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['alert_policy']['name'] == 'Balanced'
