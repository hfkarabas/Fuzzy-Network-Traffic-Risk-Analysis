# Turkish / English interface

Turkish is the default for a new visitor, regardless of browser language. Use the
globe button **directly above the sidebar's research notice**: it displays **English**
in Turkish mode and **Türkçe** in English mode. It uses the same full-width row,
padding, radius and typography as sidebar navigation. The responsive sidebar and
all existing route hashes remain unchanged.

The preference is stored in localStorage as `fuzzy-network-risk.language`, with
values `tr` or `en`. A fresh page load restores that preference. Invalid/missing
values fall back to Turkish. Disabled storage does not prevent in-session
switching. Selection updates `document.documentElement.lang`, the document title,
numbers/time presentation and all subscribed views immediately without reloading.
It does not reset forms, selected flows, explanation tabs or monitoring sessions.

## Presentation-only architecture

- `web/src/i18n/store.ts`: a small language store with React's external-store
  subscription API, guarded persistence, locale and document-language updates.
- `web/src/i18n/messages.ts`: source-language phrase catalog plus explicit
  `tr`/`en` labels for semantic keys, policy names and flow/capture reason codes.
- `web/src/i18n/index.tsx`: reusable `useI18n`, typed `TranslationKey`/`t`, fallback
  helpers, language switcher and a pure React presentation adapter.
- `web/src/format.ts`: locale-aware number/scientific/fixed-decimal formatting.

Existing components call `useI18n().localize` around their returned React tree.
The adapter translates rendered string children and visible/accessibility
attributes (`title`, `aria-label`, `aria-description`, `placeholder`, `alt`). It
does **not** manipulate DOM text after rendering and does not inspect or mutate
API objects, feature columns, numeric values, SVG coordinates, class names,
identifiers, event handlers or input values. It preserves option values separately
from translated labels so localized policy names cannot become API identifiers.
Technical children can opt out with `data-i18n-skip`.

This allows the existing Turkish source UI to stay readable and preserves the
backend's original Turkish presentation data. Exact phrases are preferred;
known template fragments translate dynamic rule conditions, explanations and
captions in one non-cascading, Unicode-word-boundary-aware pass. Rule IDs,
strengths, source measurements and inference results remain original. Only the
known backend risk-explanation template needs decimal punctuation conversion;
already localized numbers (including English thousands separators) are untouched.

## Extending and checking translations

Add a Turkish source phrase and its English translation to `english`, or an
explicit `{tr,en}` label to `labels`. New function components should use the
reusable hook/adapter, or typed `t(key)` for explicit labels. Never localize an
API key, dataset label, membership parameter or model object in place. Wrap only
the presentation boundary and keep machine-valued select options explicit.

Unknown human-readable source messages remain available as a fallback; recognized
fragments can still translate. Missing semantic `app.*`, `risk.*`, `policy.*` or
`ui.*` keys show localized **Text unavailable** rather than raw resource keys.
`fallback(key, source)` permits an explicit source fallback. New backend wording
should be added to the catalog; there is no external or automatic translation
service. Pure catalog/hook changes must not add a language field to inference or
capture requests.

Run `npm --prefix web test` and `npm --prefix web run build` (or existing Make
targets). Localization tests cover every route, switching from each page,
storage restoration/failure, chart/accessibility labels, dynamic backend texts,
invalid/partial flows, unchanged request values and no extra analysis on switching.
Existing Turkish visualization/API-response tests remain unchanged and passing.
CSS permits long translated tabs, sidebar labels and rule descriptions to wrap.

## Intentional boundaries

Source feature identifiers, dataset attack labels, rule/model IDs, file paths,
addresses and actual OS interface names remain verbatim technical data. Raw
OpenAPI schemas and the separate backend `/docs` HTML reference retain their
original language; this task localizes the React application, not backend API
documentation. Future unrecognized OS/driver error wording can retain original
text until cataloged. Native browser screenshot/layout inspection was not
performed; automated DOM/SVG, typechecking and build validation are recorded in
`reports/web/task09a/`.
