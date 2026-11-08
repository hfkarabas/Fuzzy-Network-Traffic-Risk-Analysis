"""One application version (SemVer) across Python, API, frontend and changelog."""

import json
import re
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

import fuzzy_network_risk
from fuzzy_network_risk.webapp.api import create_app

ROOT = Path(__file__).resolve().parents[1]
VERSION = fuzzy_network_risk.__version__
SEMVER = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?')


def test_version_is_semantic():
    assert SEMVER.fullmatch(VERSION)


def test_pyproject_reads_the_single_source():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    assert 'version' not in project['project'] and project['project']['dynamic'] == ['version']
    assert project['tool']['setuptools']['dynamic']['version'] == {'attr': 'fuzzy_network_risk.__version__'}


def test_frontend_package_and_lock_match():
    package = json.loads((ROOT / 'web/package.json').read_text(encoding='utf-8'))
    lock = json.loads((ROOT / 'web/package-lock.json').read_text(encoding='utf-8'))
    assert package['version'] == lock['version'] == lock['packages']['']['version'] == VERSION


def test_api_and_metadata_report_the_version():
    with TestClient(create_app()) as client:
        assert client.app.version == VERSION
        assert client.get('/api/health').json()['app_version'] == VERSION
        assert client.get('/api/model').json()['app_version'] == VERSION
        assert client.get('/openapi.json').json()['info']['version'] == VERSION


def test_changelog_documents_the_current_version():
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert re.search(rf'^## \[{re.escape(VERSION)}\]', changelog, re.M)


def test_frontend_fixture_matches_current_version():
    fixture = json.loads((ROOT / 'web/src/test-fixture.json').read_text(encoding='utf-8'))
    assert fixture['model']['app_version'] == VERSION
