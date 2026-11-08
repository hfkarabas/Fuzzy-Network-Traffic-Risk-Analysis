"""Launcher control-flow, native owned-tree cleanup and platform simulations."""

import hashlib
import json
import signal
import socket
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import dev
import pytest

from fuzzy_network_risk.config_integrity import frozen_text_matches

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    'version,accepted',
    [
        ((20, 19, 0), False),
        ((22, 22, 1), False),
        ((22, 22, 2), True),
        ((24, 14, 9), False),
        ((24, 15, 0), True),
        ((25, 0, 0), False),
        ((26, 0, 0), True),
    ],
)
def test_node_lock_engine_intersection(version, accepted):
    assert dev.node_compatible(version) == accepted


def declarations(root):
    (root / 'requirements.txt').write_text('demo_package==1.2.3\n')
    (root / 'requirements-web.txt').write_text('-r requirements.txt\n')
    (root / 'pyproject.toml').write_text('[project]\nrequires-python=">=3.12"\n')


def test_requirement_graph_changes_and_unpinned_rejection(tmp_path):
    declarations(tmp_path)
    pins, a = dev.requirements(tmp_path)
    assert pins == {'demo-package': '1.2.3'}
    (tmp_path / 'requirements.txt').write_text('demo_package==1.2.4\n')
    assert a != dev.requirements(tmp_path)[1]
    (tmp_path / 'requirements.txt').write_text('demo_package>=1.2.4\n')
    with pytest.raises(dev.LaunchError, match='Unsupported'):
        dev.requirements(tmp_path)


def test_conflicting_pins_across_includes_rejected(tmp_path):
    declarations(tmp_path)
    (tmp_path / 'requirements-dev.txt').write_text('-r requirements-web.txt\ndemo_package==9.9.9\n')
    with pytest.raises(dev.LaunchError, match='Conflicting pins'):
        dev.requirements(tmp_path, 'requirements-dev.txt')


def test_test_profile_installs_dev_declarations_with_separate_marker(monkeypatch, tmp_path):
    declarations(tmp_path)
    (tmp_path / 'requirements-dev.txt').write_text('-r requirements-web.txt\ntest_tool==2.0\n')
    executable = tmp_path / '.venv/bin/python'
    monkeypatch.setattr(dev, 'valid_venv', lambda _: (executable, {'version': [3, 14, 0]}))
    seen = []
    monkeypatch.setattr(
        dev, 'python_health', lambda exe, pins, root: seen.append(pins) or {'ok': False, 'mismatch': pins}
    )
    monkeypatch.setattr(dev, 'capture', lambda *_args, **_kwargs: 'pip 26')
    calls = []
    monkeypatch.setattr(dev, 'run_command', lambda cmd, root: calls.append(cmd))
    with pytest.raises(dev.LaunchError, match='verification failed'):
        dev.ensure_python(tmp_path, 'dev')
    assert calls[-1][-2:] == ['-r', tmp_path / 'requirements-dev.txt']
    assert seen[0] == {'demo-package': '1.2.3', 'test-tool': '2.0'}
    monkeypatch.setattr(dev, 'python_health', lambda *_: {'ok': True})
    dev.ensure_python(tmp_path, 'dev')
    dev.ensure_python(tmp_path)
    assert (tmp_path / '.tmp/launcher/python-dev.json').is_file() and (tmp_path / '.tmp/launcher/python.json').is_file()


def test_repository_lock_files_are_consistent_and_layered():
    root = Path(__file__).resolve().parents[1]
    profiles = {
        name: dev.requirements(root, name)[0]
        for name in [
            'requirements.txt',
            'requirements-web.txt',
            'requirements-live.txt',
            'requirements-research.txt',
            'requirements-dev.txt',
        ]
    }
    core = profiles['requirements.txt']
    assert {'numpy', 'pandas'} <= set(core) and not {'fastapi', 'pytest', 'duckdb', 'scapy'} & set(core)
    assert (
        core.items()
        <= profiles['requirements-web.txt'].items()
        <= profiles['requirements-live.txt'].items()
        <= profiles['requirements-dev.txt'].items()
    )
    assert core.items() <= profiles['requirements-research.txt'].items() <= profiles['requirements-dev.txt'].items()
    web = profiles['requirements-web.txt']
    assert {'fastapi', 'uvicorn'} <= set(web) and not {
        'pytest',
        'httpx',
        'duckdb',
        'datasets',
        'matplotlib',
        'pyarrow',
        'scapy',
    } & set(web)
    assert {'pytest', 'httpx', 'scapy', 'pyarrow', 'datasets'} <= set(profiles['requirements-dev.txt'])


def test_platform_paths_and_no_manager_autoinstall(tmp_path):
    assert str(dev.venv_python(tmp_path, True)).endswith('Scripts\\python.exe') or str(
        dev.venv_python(tmp_path, True)
    ).endswith('Scripts/python.exe')
    assert dev.venv_python(tmp_path, False) == tmp_path / '.venv/bin/python'
    env = dev.environment(tmp_path / 'web')
    assert env['PYTHON_MANAGER_AUTOMATIC_INSTALL'] == 'false' and env['TEMP'] == str(tmp_path / '.tmp')


def test_choose_installed_python_and_missing_error(monkeypatch, tmp_path):
    monkeypatch.setattr(dev, 'windows', lambda: False)
    monkeypatch.setattr(dev.shutil, 'which', lambda n: '/valid python' if n == 'python3.14' else None)

    def probe(path, root):
        return {'version': [3, 14, 0] if str(path) == '/valid python' else [3, 9, 0], 'executable': str(path)}

    monkeypatch.setattr(dev, 'python_info', probe)
    assert str(dev.choose_python(tmp_path)[0]).replace('\\', '/') == '/valid python'
    monkeypatch.setattr(dev.shutil, 'which', lambda _: None)
    with pytest.raises(dev.LaunchError, match='No Python runtime'):
        dev.choose_python(tmp_path)


def test_existing_invalid_environment_is_preserved(tmp_path):
    folder = tmp_path / '.venv'
    folder.mkdir()
    sentinel = folder / 'personal-file'
    sentinel.write_text('keep')
    with pytest.raises(dev.LaunchError, match='not be overwritten'):
        dev.valid_venv(tmp_path)
    assert sentinel.read_text() == 'keep'


def test_python_adoption_skip_change_and_corruption(monkeypatch, tmp_path):
    declarations(tmp_path)
    executable = tmp_path / '.venv/Scripts/python.exe'
    info = {'version': [3, 14, 0]}
    monkeypatch.setattr(dev, 'valid_venv', lambda _: (executable, info))
    monkeypatch.setattr(dev, 'python_health', lambda *_: {'ok': True})
    calls = []
    monkeypatch.setattr(dev, 'run_command', lambda cmd, root: calls.append(cmd))
    monkeypatch.setattr(dev, 'capture', lambda *_args, **_kwargs: 'pip 26')
    dev.ensure_python(tmp_path)
    dev.ensure_python(tmp_path)
    assert calls == []
    (tmp_path / 'requirements.txt').write_text('demo_package==1.2.4\n')
    dev.ensure_python(tmp_path)
    assert calls[-1][0] == executable and 'install' in calls[-1] and '--force-reinstall' not in calls[-1]
    count = len(calls)
    results = iter([{'ok': False, 'detail': 'broken binary', 'mismatch': {}}, {'ok': True}])
    monkeypatch.setattr(dev, 'python_health', lambda *_: next(results))
    dev.ensure_python(tmp_path)
    assert len(calls) == count + 1 and '--force-reinstall' in calls[-1]


def test_missing_venv_created_locally_and_pip_bootstrapped(monkeypatch, tmp_path):
    declarations(tmp_path)
    executable = dev.venv_python(tmp_path)
    results = iter([None, (executable, {'version': [3, 14, 0]})])
    monkeypatch.setattr(dev, 'valid_venv', lambda _: next(results))
    monkeypatch.setattr(dev, 'choose_python', lambda _: (Path('/installed/python'), {}))
    health = iter([{'ok': False, 'mismatch': {'demo-package': '1.2.3'}}, {'ok': True}])
    monkeypatch.setattr(dev, 'python_health', lambda *_: next(health))

    def missing(*args, **kwargs):
        raise dev.LaunchError('no pip')

    monkeypatch.setattr(dev, 'capture', missing)
    calls = []
    monkeypatch.setattr(dev, 'run_command', lambda cmd, root: calls.append(cmd))
    dev.ensure_python(tmp_path)
    assert calls[0][-2:] == ['venv', tmp_path / '.venv']
    assert calls[1] == [executable, '-m', 'ensurepip', '--upgrade']
    assert all(cmd[0] == executable for cmd in calls[1:])


def frontend_fixture(root):
    web = root / 'web'
    modules = web / 'node_modules'
    (modules / '.bin').mkdir(parents=True)
    (modules / '.package-lock.json').write_text('{}')
    (modules / 'react').mkdir()
    (modules / 'react/package.json').write_text('{"version":"19.0.0"}')
    for name in ['vite', 'vitest', 'tsc']:
        (modules / '.bin' / (name + '.cmd' if dev.windows() else name)).write_text('fixture')
    lock = {
        'lockfileVersion': 3,
        'packages': {
            '': {},
            'node_modules/react': {'version': '19.0.0'},
            'node_modules/other-platform': {'version': '1', 'optional': True},
        },
    }
    (web / 'package-lock.json').write_text(json.dumps(lock))
    (web / 'package.json').write_text('{}')
    return lock


def test_frontend_partial_or_corrupt_installation(monkeypatch, tmp_path):
    lock = frontend_fixture(tmp_path)
    monkeypatch.setattr(dev, 'capture', lambda *_args, **_kwargs: '')
    assert dev.frontend_health(tmp_path, lock, 'node')
    (tmp_path / 'web/node_modules/react/package.json').write_text('{"version":"18.0.0"}')
    assert not dev.frontend_health(tmp_path, lock, 'node')


def test_npm_adoption_lock_change_and_no_lock_mutation(monkeypatch, tmp_path):
    frontend_fixture(tmp_path)
    monkeypatch.setattr(
        dev, 'node_tools', lambda _: ('node', ['node', 'npm-cli.js'], {'version': '24.19.0', 'arch': 'arm64'}, '11.0.0')
    )
    monkeypatch.setattr(dev, 'frontend_health', lambda *_: True)
    calls = []
    monkeypatch.setattr(dev, 'run_command', lambda cmd, root: calls.append(cmd))
    dev.ensure_frontend(tmp_path)
    dev.ensure_frontend(tmp_path)
    assert not calls
    lock = tmp_path / 'web/package-lock.json'
    lock.write_text(lock.read_text() + '\n')
    before = lock.read_bytes()
    dev.ensure_frontend(tmp_path)
    assert 'ci' in calls[-1] and '--include=dev' in calls[-1] and lock.read_bytes() == before


def test_missing_node_instructions(monkeypatch):
    monkeypatch.setattr(dev.shutil, 'which', lambda _: None)
    with pytest.raises(dev.LaunchError, match='nodejs.org'):
        dev.node_tools()


def test_exclusive_lease_released_on_error(tmp_path):
    path = tmp_path / 'setup.lock'
    with pytest.raises(RuntimeError):
        with dev.Lease(path):
            with pytest.raises(dev.LaunchError, match='Another launcher'):
                with dev.Lease(path):
                    pass
            raise RuntimeError()
    with dev.Lease(path):
        pass


def test_real_port_conflict_does_not_kill_listener():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        sock.listen()
        port = sock.getsockname()[1]
        assert not dev.port_available(port)
        assert sock.fileno() != -1
    assert dev.port_available(port)


def test_health_readiness_and_wrong_application(monkeypatch):
    child = SimpleNamespace(check=lambda: None)
    manifest = {'model_id': 'correct', 'configuration_version': 'v1'}
    monkeypatch.setattr(dev, 'http_json', lambda _: manifest)
    dev.wait_ready([child], 8000, manifest, timeout=0.1)
    monkeypatch.setattr(dev, 'http_json', lambda _: {'model_id': 'other'})
    with pytest.raises(dev.LaunchError, match='different model'):
        dev.wait_ready([child], 8000, manifest, timeout=0.1)


@pytest.mark.parametrize('failure', ['backend', 'frontend', 'interrupt', 'running-exit'])
def test_lifecycle_failure_and_interrupt_cleanup(monkeypatch, failure):
    monkeypatch.setattr(dev, 'windows', lambda: False)
    monkeypatch.setattr(dev, 'model_assets', lambda _: {'model_id': 'test'})
    monkeypatch.setattr(dev, 'port_available', lambda _: True)
    monkeypatch.setattr(dev, 'wait_ready', lambda *_: None)
    closed = []

    class Fake:
        def __init__(self, name, args, root):
            self.name = name
            if name == failure:
                raise dev.LaunchError('synthetic failure')

        def check(self):
            if failure == 'running-exit':
                raise dev.LaunchError('unexpected exit')

        def close(self):
            closed.append(self.name)

    monkeypatch.setattr(dev, 'Child', Fake)
    if failure == 'interrupt':
        dev.serve('run', 'python', 'node', smoke_seconds=0)
    else:
        with pytest.raises(dev.LaunchError):
            dev.serve('run', 'python', 'node', smoke_seconds=0)
    assert closed == ([] if failure == 'backend' else ['backend'] if failure == 'frontend' else ['frontend', 'backend'])


def test_conflict_prevents_any_spawn(monkeypatch):
    monkeypatch.setattr(dev, 'model_assets', lambda _: {})
    monkeypatch.setattr(dev, 'port_available', lambda _: False)
    monkeypatch.setattr(dev, 'Child', lambda *_: pytest.fail('unrelated process must not be touched'))
    with pytest.raises(dev.LaunchError, match='No duplicate'):
        dev.serve('run')


def test_posix_owned_session_flags_and_cleanup(monkeypatch, tmp_path):
    monkeypatch.setattr(dev, 'windows', lambda: False)
    recorded = {}
    killed = []

    class Stream(list):
        def close(self):
            pass

    class Fake:
        pid = 12345
        stdout = Stream()

        def poll(self):
            return 0

        def wait(self, timeout):
            return 0

    def popen(args, **kwargs):
        recorded.update(kwargs)
        return Fake()

    monkeypatch.setattr(dev.subprocess, 'Popen', popen)
    monkeypatch.setattr(dev.os, 'killpg', lambda pid, sig: killed.append((pid, sig)), raising=False)
    monkeypatch.setattr(dev.signal, 'SIGKILL', 9, raising=False)
    child = dev.Child('mock-posix', ['python'], tmp_path)
    child.close()
    assert recorded['start_new_session'] and 'creationflags' not in recorded
    assert killed == [(12345, signal.SIGTERM), (12345, signal.SIGKILL)]


def test_real_owned_process_tree_cleanup_with_unicode_path(tmp_path):
    folder = tmp_path / 'Ü space'
    folder.mkdir()
    port_file = folder / 'port.txt'
    grandchild = (
        'import socket,time;from pathlib import Path;s=socket.socket();s.bind(("127.0.0.1",0));s.listen();Path('
        + repr(str(port_file))
        + ').write_text(str(s.getsockname()[1]));time.sleep(60)'
    )
    parent = (
        'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(grandchild) + ']);time.sleep(60)'
    )
    child = dev.Child('owned-test', [sys.executable, '-c', parent], folder)
    try:
        deadline = time.monotonic() + 8
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert port_file.exists()
        port = int(port_file.read_text())
        assert not dev.port_available(port)
    finally:
        child.close()
    deadline = time.monotonic() + 4
    while not dev.port_available(port) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert dev.port_available(port)


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'])
def test_lf_crlf_frozen_models_without_data_or_refitting(tmp_path, newline):
    paths = [
        'config/fuzzy/task04/selected_manifest.json',
        'config/fuzzy/task04/selected_v4.json',
        'config/fuzzy/task04/selected_policies.json',
        'web/catalog/examples.json',
        'reports/dataset/provenance.json',
        'reports/dataset/classes.csv',
        'reports/fuzzy/metrics.json',
        'reports/fuzzy/task02b/comparison_summary.csv',
        'reports/fuzzy/task04/comparison.csv',
    ]
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / relative).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', newline))
    manifest = dev.model_assets(tmp_path)
    from fuzzy_network_risk.webapp.service import WebService

    service = WebService(tmp_path)
    assert service.engine.model_id == manifest['model_id']
    example = service.examples[0]
    assert service.analyze(example['features'], 'Balanced')['risk_score'] == example['risk_score']
    assert not (tmp_path / 'datasets').exists() and not (tmp_path / 'data').exists()


def test_hash_guard_only_allows_line_ending_conversion():
    raw = b'{\n  "a": 1\n}\n'
    expected = hashlib.sha256(raw).hexdigest()
    assert frozen_text_matches(raw.replace(b'\n', b'\r\n'), expected)
    assert not frozen_text_matches(raw + b' ', expected)
    assert not frozen_text_matches(raw.replace(b'1', b'2'), expected)
