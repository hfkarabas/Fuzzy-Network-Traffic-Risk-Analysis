# TASK 09A — Turkish / English localization

Baseline: `5e0bb59e66cd48968eb3bce41e2808fac434849f`, initially clean.

Delivered a full-width globe language button immediately above the sidebar research
notice, matching navigation row dimensions/styles. It shows English in Turkish
mode and Türkçe in English mode, with localized accessible labels. The notice now
correctly explains that the application is local and live capture is optional and
user-initiated. No header dropdown was introduced.

Turkish remains the first-visit default. `tr`/`en` selection persists under
`fuzzy-network-risk.language`; reload restores it, invalid values default to Turkish,
and blocked storage still permits switching in the current session. Switching
updates HTML language/title and number/time formatting immediately without page
reload, resetting analysis state or sending extra inference/output requests.

The lightweight architecture is `web/src/i18n/{store.ts,messages.ts,index.tsx}`:
a reusable subscription hook, typed keys, source-language phrase catalog, explicit
bilingual status/policy labels and pure React presentation adapter. It translates
rendered text/accessibility attributes only, not DOM after-render mutations, API
payloads or model objects. Machine-valued options keep original values separately
from translated labels. Known dynamic rule/explanation templates use cataloged
fragments while preserving rule IDs, strengths and full-precision measurements.

All six routes, historical/live memberships, rule activations, output/centroid,
policy cards, tooltips, errors, invalid/partial flows and loading/empty states are
covered. Existing charts are reused. No dependencies or backend changes were needed.
Shared components, App/LiveTraffic, format helpers and fatal-error presentation now
subscribe to the language store; scoped CSS allows long labels/tabs to wrap.

## Executed validation

- **44 frontend tests passed, zero failed**: all 36 existing regressions plus
  eight localization/persistence cases.
- TypeScript and Vite production build passed, using existing healthy dependencies.
- Every route switches both ways; the English DOM/SVG and accessibility-attribute
  audit found no remaining Turkish UI text on those routes.
- Existing backend reference strings, including all rule explanations and warnings,
  translate without mutating their original objects. API/input values remain intact.
- Fresh-module storage restoration, invalid preference, blocked storage, explicit
  fallback, partial/invalid flows, offline errors, grouping/decimal formatting and
  absence of extra analysis/plot requests on language change are tested.

Coverage initially caught two missing split captions (card results and flow-count
unit); these were added. Number-format coverage also guards English thousands
separators against accidental decimal punctuation conversion.

`validation.json` records protected-path comparisons, catalog sizes and source
hashes. `frontend_tests.txt` and `build.txt` contain actual normalized command output.
Backend/model/capture code, configurations, datasets/LFS, original reference
outputs, dependency lockfiles and all existing frontend tests are unchanged.
No dataset processing, unrelated backend suite or model experiment was run.
No remote Git operation was performed.

## Intentional untranslated data / limitations

Machine identifiers, feature columns, dataset class names, addresses, filenames and
actual OS interface names remain verbatim. The separate backend `/docs` reference
and raw OpenAPI descriptions retain their original language outside the React UI.
Future unknown external OS/driver wording falls back to its original message until
cataloged; missing semantic UI keys display localized Text unavailable rather than
raw keys. No external translation service is used.

Native browser screenshot/layout inspection was not performed; responsive styles,
DOM/SVG rendering and accessible labels were validated automatically. Usage and
extension instructions are in `docs/localization.md`; README links to that guide.
The local commit hash and final working-tree status are supplied in the final response.
