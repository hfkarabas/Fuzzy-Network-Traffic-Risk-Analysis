"""The CI workflow is manual-only by project decision and mirrors local checks."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/ci.yml'


def load():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))
    # YAML 1.1 reads the bare key `on` as boolean True.
    return workflow, workflow.get('on', workflow.get(True))


def test_only_manual_trigger_and_read_only_token():
    workflow, triggers = load()
    assert list(triggers) == ['workflow_dispatch']
    assert workflow['permissions'] == {'contents': 'read'}


def test_jobs_run_the_same_checks_as_make_lint_and_make_test():
    workflow, _ = load()
    steps = {
        name: ' '.join(str(step.get('run', '')) for step in job['steps']) for name, job in workflow['jobs'].items()
    }
    assert 'ruff check' in steps['lint'] and 'ruff format --check' in steps['lint'] and 'typecheck' in steps['lint']
    assert 'requirements-dev.txt' in steps['python-tests'] and 'pytest' in steps['python-tests']
    assert 'requirements-web.txt' in steps['web-only-profile'] and 'requirements-dev' not in steps['web-only-profile']
    assert 'npm ci' in steps['frontend'] and 'test' in steps['frontend'] and 'run build' in steps['frontend']


def test_dataset_archive_is_never_downloaded():
    workflow, _ = load()
    assert workflow['env']['GIT_LFS_SKIP_SMUDGE'] == '1'
    for job in workflow['jobs'].values():
        for step in job['steps']:
            if str(step.get('uses', '')).startswith('actions/checkout'):
                assert step['with']['lfs'] is False
