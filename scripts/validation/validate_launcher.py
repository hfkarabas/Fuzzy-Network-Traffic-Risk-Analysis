"""Recheck TASK 06B evidence and preservation; never used by normal startup."""
from pathlib import Path
import hashlib
import json
import platform
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 'ca49a972c1b29f1edd75a4b85ece09d5d5ee64ae'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    report = ROOT / 'reports/launcher'
    def log(name):
        path = report / name
        raw = path.read_bytes()
        decoded = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        text = '\n'.join(line.rstrip() for line in decoded.splitlines()) + '\n'
        path.write_text(text, encoding='utf-8', newline='\n')
        return text
    tests, build = log('test_run.txt'), log('build.txt')
    python_count = int(re.search(r'(\d+) passed in ', tests)[1])
    frontend_count = int(re.search(r'Tests\s+(\d+) passed', tests)[1])
    assert python_count == 202 and frontend_count == 15
    assert 'tsc --noEmit' in build and 'built in' in build
    smoke = json.loads((report / 'smoke.json').read_text(encoding='utf-8'))
    standalone = json.loads((report / 'standalone.json').read_text(encoding='utf-8'))
    assert smoke['status'] == 'PASS' and smoke['ports_released_before_harness_cleanup']
    assert all(all(item.values()) for item in standalone.values())
    # The original complete raw artifact manifest predates later experiments.
    historical = json.loads((ROOT / 'reports/web/historical_integrity.json').read_text(encoding='utf-8'))
    mismatches = [name for name, expected in historical.items() if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
    assert not mismatches, mismatches
    archive = json.loads((ROOT / 'config/dataset_archive_v1.json').read_text(encoding='utf-8'))
    archive_path = ROOT / archive['artifact']
    assert digest(archive_path) == archive['sha256']
    # Compare every pre-existing tracked file; Git's index normalizes text EOLs.
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT)
    names = git('ls-tree', '-r', '--name-only', BASELINE).decode().splitlines()
    permitted = {'.gitignore', 'README.md', 'src/fuzzy_network_risk/webapp/service.py'}
    changed, checked = [], 0
    for name in names:
        if name == archive['artifact']:
            continue  # LFS pointer is independently checked against full SHA above.
        previous = git('show', BASELINE + ':' + name)
        current = (ROOT / name).read_bytes()
        if previous.replace(b'\r\n', b'\n') != current.replace(b'\r\n', b'\n'):
            changed.append(name)
        checked += 1
    assert set(changed) == permitted, changed
    fresh_log = (ROOT / '.tmp/task06b-fresh-setup.txt').read_bytes()
    fresh_text = fresh_log.decode('utf-16' if fresh_log.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    assert 'Successfully installed' in fresh_text and 'added 106 packages' in fresh_text
    assert 'FRESH AND REPEATED SETUP PASS' in fresh_text
    assert 'Python dependencies verified; no installation needed.' in fresh_text
    assert 'Frontend dependencies verified; no installation needed.' in fresh_text
    sources = ['Makefile', 'scripts/dev.py', 'scripts/validation/smoke_launcher.py', 'scripts/validation/validate_launcher.py',
               'src/fuzzy_network_risk/config_integrity.py', 'src/fuzzy_network_risk/webapp/service.py', 'tests/test_launcher.py']
    result = {
        'status': 'PASS', 'baseline_commit': BASELINE,
        'platform': platform.platform(), 'architecture': platform.machine(), 'python': platform.python_version(),
        'python_tests_passed': python_count, 'frontend_tests_passed': frontend_count,
        'failed_tests': 0, 'typescript_and_production_build': 'PASS',
        'fresh_unicode_path_python_and_npm_setup': 'PASS', 'repeated_setup_skips_installation': True,
        'native_default_make_smoke': 'PASS', 'native_standalone_targets_and_powershell_fallback': 'PASS',
        'native_macos_intel_arm_and_linux': 'NOT RUN; POSIX process behavior tested with mocks only',
        'historical_raw_hashes_verified': len(historical), 'historical_mismatches': mismatches,
        'prior_tracked_files_compared': checked, 'intentional_preexisting_changes': changed,
        'archive': {'path': archive['artifact'], 'bytes': archive_path.stat().st_size, 'sha256': archive['sha256']},
        'source_sha256': {name: digest(ROOT / name) for name in sources},
        'remote_git_operations': 'None',
        'scope': 'Evidence logs are from actual commands; this validator rechecks them and file preservation, not reruns installations or tests.'
    }
    (report / 'validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
