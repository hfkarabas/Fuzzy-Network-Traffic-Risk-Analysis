"""Score flow measurements from the command line with the deployed model and policy.

By default this uses exactly what the web application serves: the frozen
configuration in config/fuzzy/task04 (integrity-checked against its manifest)
and a calibrated alert policy (Balanced unless --policy is given). The engine's
embedded ``alert_threshold`` is historical metadata and is used only when
explicitly requested with --embedded-threshold for reproducing old reports.

Input: one JSON object with the five exact feature keys, or a JSON array of
such objects, read from --input or stdin. Labels and metadata are rejected.

Exit status: 0 every record was scored; 1 at least one record abstained
(invalid_input / no_rule_activation); 2 usage, input or configuration error.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from fuzzy_network_risk.config_integrity import frozen_text_matches  # noqa: E402
from fuzzy_network_risk.engine import MamdaniRiskEngine  # noqa: E402
from fuzzy_network_risk.policy import PolicyRiskModel  # noqa: E402

DEPLOYED = ROOT / 'config/fuzzy/task04'
DEFAULT_MODEL = DEPLOYED / 'selected_v4.json'
DEFAULT_POLICIES = DEPLOYED / 'selected_policies.json'
MANIFEST = DEPLOYED / 'selected_manifest.json'
POLICY_NAMES = ('Sensitive', 'Balanced', 'Conservative')
EXIT_OK, EXIT_ABSTAINED, EXIT_ERROR = 0, 1, 2


class CliError(Exception):
    pass


def _path(value):
    path = Path(value)
    return path if path.is_absolute() else (Path.cwd() / path)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Score flow measurements with the deployed fuzzy model and alert policy.'
    )
    parser.add_argument('--input', type=Path, help='JSON file with one object or an array; stdin if omitted')
    parser.add_argument(
        '--policy', choices=POLICY_NAMES, help='alert policy (default: the policy file default, Balanced)'
    )
    parser.add_argument(
        '--model', type=_path, default=DEFAULT_MODEL, help='model configuration (default: deployed selected_v4.json)'
    )
    parser.add_argument(
        '--policies',
        type=_path,
        default=DEFAULT_POLICIES,
        help='policy configuration calibrated for --model (default: deployed)',
    )
    parser.add_argument(
        '--embedded-threshold',
        action='store_true',
        help="use the model's historical embedded alert threshold instead of a policy",
    )
    parser.add_argument('--compact', action='store_true', help='single-line JSON output')
    args = parser.parse_args(argv)
    if args.embedded_threshold and args.policy:
        parser.error('--policy cannot be combined with --embedded-threshold')
    return args


def _verify_deployed(model_path, policies_path):
    """Refuse silently modified deployed configurations, as the web runtime does."""
    if model_path.resolve() != DEFAULT_MODEL.resolve() and policies_path.resolve() != DEFAULT_POLICIES.resolve():
        return
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for path, default, key in (
        (model_path, DEFAULT_MODEL, 'model_sha256'),
        (policies_path, DEFAULT_POLICIES, 'policy_sha256'),
    ):
        if path.resolve() == default.resolve() and not frozen_text_matches(path.read_bytes(), manifest[key]):
            raise CliError(f'Deployed configuration hash mismatch: {path.name}')


def load_scorer(args):
    try:
        if args.embedded_threshold:
            engine = MamdaniRiskEngine.load(args.model)
            if args.model.resolve() == DEFAULT_MODEL.resolve():
                _verify_deployed(args.model, DEFAULT_POLICIES)
            return engine
        _verify_deployed(args.model, args.policies)
        return PolicyRiskModel.load(args.model, args.policies, args.policy)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise CliError(f'Cannot load model/policy configuration: {exc}') from exc
    except ValueError as exc:  # e.g. policy calibrated for a different model
        raise CliError(str(exc)) from exc


def read_records(args, stdin):
    try:
        text = args.input.read_text(encoding='utf-8') if args.input else stdin.read()
        value = json.loads(text)
    except OSError as exc:
        raise CliError(f'Cannot read input: {exc}') from exc
    except json.JSONDecodeError as exc:
        raise CliError(f'Input is not valid JSON: {exc}') from exc
    records = value if isinstance(value, list) else [value]
    if not records or not all(isinstance(record, dict) for record in records):
        raise CliError('Input must be a JSON object or a non-empty array of objects')
    return value, records


def main(argv=None, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    args = parse_args(argv)
    try:
        scorer = load_scorer(args)
        original, records = read_records(args, stdin)
        try:
            results = [scorer.predict_one(record) for record in records]
        except ValueError as exc:  # schema error: labels, metadata or unknown keys
            raise CliError(str(exc)) from exc
    except CliError as exc:
        print(f'error: {exc}', file=stderr)
        return EXIT_ERROR
    if args.embedded_threshold:
        for result in results:
            result['alert_policy'] = {
                'name': 'embedded',
                'threshold': scorer.config['alert_threshold'],
                'historical_metadata_only': True,
            }
    output = results if isinstance(original, list) else results[0]
    json.dump(output, stdout, ensure_ascii=False, allow_nan=False, indent=None if args.compact else 2)
    stdout.write('\n')
    return EXIT_OK if all(result['status'] == 'ok' for result in results) else EXIT_ABSTAINED


if __name__ == '__main__':
    sys.exit(main())
