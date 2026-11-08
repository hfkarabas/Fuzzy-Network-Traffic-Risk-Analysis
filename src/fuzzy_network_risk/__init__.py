"""Reproducible network-flow preparation and explainable Mamdani risk inference."""

# Single source of truth for the application version (Semantic Versioning).
# pyproject.toml reads it dynamically; web/package.json and package-lock.json must
# match (enforced by tests/test_versioning.py). The fuzzy model has its own,
# independent identity: model_id (SHA-256), model_version and configuration_version.
__version__ = '2.0.0'
