# TASK04 initial audit and implementation record

At start HEAD was cb5d9b6bdf6cd78932802dff734b66a8af461cb5 with a clean tree.
TASK02 grouped_v1 and day_v1 configs, TASK02B A_frozen/A_refit/B_membership/C_rules
fold configs, original rules, reports, tests and source caches were present.
TASK02B selection.json confirmed A_frozen won because improvements failed its gate.
WebService loaded task02b/selected_v2.json (verbatim grouped_v1), three explicit
policies and task02b/comparison_summary.csv; metrics.json supplied historical tests.
The active model ID was and remains
ba9a293bc6b8068e86558eab707c93399c54499cfb6010b24677427f781cde1b.

The 22 complete IF–THEN rules and selected memberships are recorded in the preserved
grouped_v1.json and copied selected_v4.json; no baseline file was edited. Existing
TASK02 grouped-test and all Friday source groups/signatures are excluded from the
eligible cache. Original grouped train/validation/test role sizes were
8217/1753/1750; day train/validation/test were 1607145/422299/666572 (Friday
quality/evaluation subset). Exact provenance and exclusions are in the preserved
TASK02B evaluation_integrity.md and new partition_audit.json.

The new registered hypotheses and all unsuccessful outcomes are retained. The
backend now loads task04/selected_v4.json and verifies manifest content hashes.
Health/model endpoints expose configuration identity, and startup rejects an older
already-running application even when its scoring model ID is the same.
Analysis API fields and all existing validation behavior are backward compatible.
No additional input, page removal or visual redesign occurred; styles.css and the
real example catalog are unchanged. The sole UI addition is an evaluation card
identifying TASK04 candidates, reused validation and negative findings.

Exact example inputs/labels remain outside the engine except the five numerical
inputs; predictions were checked against direct inference for all three policies.
Historical examples need no changed predictions because scoring/policies are
byte-identical. Model metadata is updated via the manifest; existing old evaluation
evidence is visibly distinct from new candidate comparisons. Version identities are
additive API metadata. JS contains no membership/inference fitting code.

See scientific_report.md for measured diagnostics, metrics, uncertainty, day stress,
rules/features, selected policies and limitations. validation.json records actual
release checks. No remote Git synchronization, download, GPU, classifier or new
capture was used. Figures, build/dependency files and transient predictions are
ignored; small candidate configs, numerical reports and source are versioned.
