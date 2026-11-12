# Modern Web Guidance review — 2026-11-12

Branch: feat/modern-web-guidance-20261112
Deployment base: master 14ca669077fb65db948a5b5150b020ab93475679.
Preview: https://nohentai.com:8445/
Production https://nohentai.com/ remains on the base commit. No production code, service, database, schema, queue, schedule or external OCR operation was changed.

## Skill workflow and scope

Read the installed modern-web-guidance/SKILL.md, then used the broad modernization flow:

1. `legacy-scan web-static/src --json`: 0 findings across 35 deterministic rules / 33 guides. The tool states this covers approximately 20% of its guidance corpus; zero findings is not a complete design or accessibility assessment.
2. Manually reviewed actual components, semantics, responsive layout and motion handling. Searched `modal dialog focus`, `responsive card layout`, `reduce motion animations`, and, after an axe finding, `text color contrast`.
3. Retrieved and read `dialog`, `accessibility`, `responsive-design`, `card`, `motion` and `color` before implementing corresponding changes. No unverified scanner finding was acted upon.
4. Implemented and verified changes with built Vue components in Chromium, synthetic delayed/error upstreams, actual read-only preview data, screenshots and axe.
5. Re-ran the same legacy scan: still 0 findings. Safe fallbacks and third-party controls were not rewritten to chase a scan score.

The CLI currently requires Node >=22. Guidance was executed with the already available isolated Node 22 runtime, not by changing the app/server Node 20 runtime.

## Confirmed issues and final behavior

### Reading directory: native modal

The old custom `div role=dialog` did not make the background inert or contain focus. ThumbGrid now uses `dialog.showModal()`, a labelled heading, autofocus on its jump field, and native close/focus-return behavior. GalleryReader no longer intercepts modal Escape or always forces focus onto a different counter button.

`closedby=any` is progressive enhancement. Where its interface is unavailable, a small coordinate-based fallback closes only when both the press and release are outside the dialog. Clicking internal padding or dragging a text selection onto the backdrop does not dismiss it. Dialog/backdrop scroll containment is shared with existing admin dialogs. The sheet uses `75dvh` with `75vh` retained as fallback. Touch controls have 44px minimum targets on coarse pointers.

Guide quote: `dialog` — "The browser returns it to the invoker."

### Native interaction and readable semantics

PrimeVue readonly Rating generated five radio inputs inside each gallery link. StaticRating displays equivalent stars and one accessible rating value without form controls or extra tab stops. Duplicate image-title announcements inside those links were removed. Actual pages show **150 nested inputs before vs 0 after** for 30 rows. Numerical rating values and the existing full-star threshold are unchanged.

Translator authentication now uses a real form, a named password field, autocomplete, required validation and an associated alert/error state. Its mobile sheet heading and result selectors are native buttons rather than button-like containers with interactive descendants. The vertical sheet drag handle reserves only that gesture axis (`touch-action:pan-x`) instead of disabling all native touch gestures. Result editing and deletion retain separate controls; edit textareas and delete buttons have explicit names. Admin routes expose one main landmark instead of nesting their existing main within App's main. Admin confirmation content is rendered before opening; returnValue is cleared after reading.

Guide quote: `accessibility` — "Prefer HTML elements and attributes to ARIA".

### Container-driven results

Gallery results provide a size container; individual rows query their own inline size. A narrow panel on a desktop now gets the same readable title wrapping as a narrow page. Cover grids fit actual available space, including two covers at 320px, and retain intrinsic aspect-ratio placeholders. Existing viewport rules remain as fallback where container queries are unavailable.

Guide quote: `card` — "Base the layout on the card's available space, not the viewport."
Guide quote: `responsive-design` — "Use dynamic viewport units".

### Motion is deliberate

Removed the universal `animation-duration:0.01ms` / `transition-duration:0.01ms` override. Skeleton sweeps, spinners, task scans and toast motion now opt in under `prefers-reduced-motion:no-preference`; static progress remains visible. Spatial hover, switch, sheet and page-turn transitions are handled in their own components, keeping color/opacity feedback. The book reader observes live preference changes without rewriting saved animation settings. Translator result scrolling also honors the preference.

Guide quote: `motion` — "Keep non-motion transitions".

### Contrast and forced colors

Axe found two light-theme tool labels at **4.47:1**. A small adjustment to the existing muted-text token yields **4.89:1** against the same surface. Forced Colors Mode uses system color tokens and explicit active-navigation outlines, without opting out of system colors or changing branding.

Guide quote: `color` — "Maintain 4.5:1 for normal text".

## Deliberately preserved

- G logo, A outlined wordmark, B admin logo, original shared SVG icon family.
- Statistics metrics and chart types, navigation, search grammar, first/last pagination, view-mode persistence, reading direction, translation/OCR contracts and admin permissions.
- PrimeVue category popover and form/chart components: they already provide working interactions; replacing them without a confirmed benefit would add risk and dependencies.
- Existing aspect-ratio image placeholders and viewport fallbacks, rather than blindly deleting older-looking code.

## Validation and evidence

- Vue/TypeScript checks passed; Vite/PWA assets generated; standalone post-build removed mutable data snapshots.
- 18 Node regressions passed.
- `tests/browser_layout.py` passed: light/dark at 360/600/768/1024/1440px; cover/list layouts, touch targets, pagination/history/jump, popovers, loading/empty/error/retry, four admin layouts, brand geometry.
- `tests/browser_review.py` passed: reader initial position, keyboard/long segments, directory jump/Escape, stale OCR response handling, bubbles/editor, native sheet Space/Enter operation, image retry, detail/search errors and statistics recovery.
- `tests/browser_modern_guidance.py` passed: static ratings, narrow desktop container and 320px covers; native modal focus, browser-chrome traversal, Escape and simulated missing-closedby fallback; live reduced motion, saved settings, native translator submit/error, admin landmark, Forced Colors Mode, and a short 320px coarse-pointer viewport.
- Axe 4.10.3 reported **0 violations** for the home and admin-login fixtures in both light/dark themes. Each report includes one incomplete/manual check. This is not a claim of complete WCAG certification.
- Actual HTTPS preview tested with read-only catalog data: 30 rows, no nested inputs, no horizontal overflow; approved brand assets remain present. Admin login has one main landmark.
- Before/after legacy scan: 0 / 0, with the tool's approximately 20% coverage limitation explicitly retained.

Screenshots and raw axe report are under /tmp/nohentai-modern-guidance/. axe is test-only and optional; supplying /tmp/nohentai-axe.min.js enables that portion of the browser suite. No browser-test fixture or fake data is served by the preview.

Known validation limits: no real VoiceOver/TalkBack hardware session or physical soft-keyboard test was available. Safari-specific closedby degradation was exercised through feature removal in Chromium, not a real Safari build. Existing release behavior for fonts and opaque media remains unchanged.

## Isolation and rollback

Only the isolated preview's static files were updated. The prior preview is retained at /srv/nohentai/integrated-review/www-before-mwg-20261112. Restoring its contents restores the previous preview, with no database rollback. Production remains at 14ca669. Merge/deploy to production requires a later user decision.
