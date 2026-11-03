"""Explicit local TASK07 preservation/evidence audit; never invoked by startup."""
from pathlib import Path
import hashlib
import json
import platform
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '29471e132cbbd2189b8807880a286056ebeb24c6'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    report = ROOT / 'reports/realtime'
    def evidence(source, target):
        raw = (ROOT/source).read_bytes()
        text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        text = '\n'.join(line.rstrip() for line in text.splitlines())+'\n'
        (report/target).write_text(text, encoding='utf-8', newline='\n')
        return text
    tests = evidence('.tmp/task07-tests.txt', 'test_run.txt')
    build = evidence('.tmp/task07-build.txt', 'build.txt')
    python_count = int(re.search(r'(\d+) passed in ', tests)[1])
    frontend_count = int(re.search(r'Tests\s+(\d+) passed', tests)[1])
    assert (python_count, frontend_count) == (227, 21)
    assert 'tsc --noEmit' in build and 'built in' in build
    integration = json.loads((report/'integration.json').read_text(encoding='utf-8'))
    assert integration['status'] == 'PASS' and integration['direct_offline_live_policy_comparisons'] == 6
    manifest = json.loads((ROOT/'reports/web/historical_integrity.json').read_text(encoding='utf-8'))
    mismatches = [name for name, expected in manifest.items() if not (ROOT/name).is_file() or sha(ROOT/name) != expected]
    assert not mismatches, mismatches
    archive = json.loads((ROOT/'config/dataset_archive_v1.json').read_text(encoding='utf-8'))
    assert sha(ROOT/archive['artifact']) == archive['sha256']
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT)
    permitted = {'.gitignore', 'README.md', 'src/fuzzy_network_risk/webapp/api.py',
                 'web/src/App.tsx', 'web/src/App.test.tsx', 'web/src/styles.css'}
    changed = []
    names = git('ls-tree', '-r', '--name-only', BASELINE).decode().splitlines()
    for name in names:
        if name == archive['artifact']: continue
        previous, current = git('show', BASELINE+':'+name), (ROOT/name).read_bytes()
        if previous.replace(b'\r\n', b'\n') != current.replace(b'\r\n', b'\n'): changed.append(name)
    assert set(changed) == permitted, changed
    ignored = ['.tmp/task07-integration.txt', '.venv/Scripts/python.exe', 'web/dist/index.html',
               'web/node_modules/.package-lock.json', '.tmp/test.pcap', '.tmp/test.pcapng']
    assert len(git('check-ignore', *ignored).decode().splitlines()) == len(ignored)
    source_names = ['src/fuzzy_network_risk/realtime/flows.py', 'src/fuzzy_network_risk/realtime/capture.py',
        'src/fuzzy_network_risk/realtime/monitor.py', 'src/fuzzy_network_risk/webapp/api.py',
        'web/src/LiveTraffic.tsx', 'web/src/live-test-fixture.json', 'tests/test_realtime.py',
        'web/src/LiveTraffic.test.tsx', 'scripts/validate_realtime.py', 'requirements-live.txt']
    result = {'status': 'PASS', 'baseline_commit': BASELINE, 'platform': platform.platform(),
        'python': platform.python_version(), 'optional_scapy': '2.8.0',
        'python_tests_passed': python_count, 'frontend_tests_passed': frontend_count, 'failed_tests': 0,
        'typescript_and_build': 'PASS', 'integration': integration,
        'historical_raw_hashes_verified': len(manifest), 'historical_mismatches': mismatches,
        'prior_tracked_files_compared': len(names)-1, 'intentional_preexisting_changes': changed,
        'dataset_archive_sha256': archive['sha256'], 'dataset_archive_bytes': (ROOT/archive['artifact']).stat().st_size,
        'frozen_models_policies_pipeline_launchers_lockfiles': 'Unchanged against baseline',
        'source_sha256': {name: sha(ROOT/name) for name in source_names},
        'packet_capture_and_generated_files_ignored': True, 'remote_git_operations': 'None',
        'limits': ['No actual captured packets: Npcap unavailable', 'No native Linux/macOS capture test',
                   'Legacy feature profile not independently validated against the exact 2017 exporter']}
    (report/'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
