"""Capture real Python responses as fixtures for isolated React tests.

Writes all three frontend fixtures from the deployed model, in process:

- web/src/test-fixture.json: model, policies, examples, evaluation and every
  example analysed under every policy (WebService);
- web/src/live-test-fixture.json: a finished synthetic packet replay session
  (Monitor + ReplaySource; requires the optional Scapy dependency);
- web/src/visualization-test-fixture.json: output-membership/centroid data for
  the policy-contrast example and both replay flows, plus their analyses.

No network access, capture device or running server is needed.
"""
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from fuzzy_network_risk.realtime.monitor import Monitor  # noqa: E402
from fuzzy_network_risk.webapp.service import WebService  # noqa: E402

WEB = ROOT / 'web/src'


def write(name, value, compact=False):
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':')) if compact else \
        json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    (WEB / name).write_text(text, encoding='utf-8')


def replay_session(service):
    monitor = Monitor(service)
    monitor.start('replay')
    deadline = time.monotonic() + 15
    while monitor.snapshot()['running']:
        if time.monotonic() > deadline:
            monitor.stop()
            raise RuntimeError('Synthetic replay did not finish')
        time.sleep(.05)
    status = monitor.snapshot()
    if status['counts'].get('ok') != 2:
        raise RuntimeError(f'Unexpected replay result: {status["counts"]}')
    # Stable, explicitly synthetic identifiers for deterministic fixtures.
    status['control_token'] = 'test-only-token'
    status['session_id'] = 'synthetic-replay'
    for row in status['flows']:
        row['id'] = 'replay-' + row['protocol'].lower()
        row['observed_at'] = 0
    status['errors'] = [dict(error, time=0) for error in status['errors']]
    return status


def main():
    service = WebService()
    examples = {example['id']: example for example in service.examples}
    write('test-fixture.json', {
        'health': {'status': 'ok'}, 'model': service.model, 'policies': {'policies': service.policy_list()},
        'examples': {'examples': service.examples}, 'evaluation': service.evaluation,
        'analyses': {example['id']: {policy: service.analyze(example['features'], policy) for policy in service.models}
                     for example in service.examples}}, compact=True)

    live = replay_session(service)
    write('live-test-fixture.json', live)

    engine = service.engine
    visual = {'historical': engine.output_visualization(examples['policy-contrast']['features'])}
    analyses = {}
    for row in live['flows']:
        protocol = row['protocol'].lower()
        visual[protocol] = engine.output_visualization(row['features'])
        analyses[protocol] = {policy: service.analyze(row['features'], policy) for policy in service.models}
    visual['liveAnalyses'] = analyses
    write('visualization-test-fixture.json', visual)
    print('Captured real service, replay and visualization responses for frontend fixtures.')


if __name__ == '__main__':
    main()
