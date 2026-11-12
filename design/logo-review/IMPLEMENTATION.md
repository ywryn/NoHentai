# Selected branding and UI icons

Branch: feat/brand-and-icons-20261112
Public site: selected concept F. Admin login, sidebar and mobile navigation: concept B.

Preview: https://nohentai.com:8445/
Admin preview: https://nohentai.com:8445/#/admin/overview
SVG library specimen: https://nohentai.com:8446/icons.html

The original generated PNGs are copied unchanged into web-static/public/brand/. BrandMark handles consistent dimensions; the favicon switches on initial entry and Vue route changes. PWA and Apple touch entry points use F. Privacy mode excludes only brand marks; content images keep their blur behavior.

46 project-maintained SVG icons share paths.ts and AppIcon.vue. AdminIcon is a compatibility wrapper. Navigation, theme/privacy/view toggles, pagination (including first/last), search, detail actions/copy, reader controls, translator navigation/edit/close, and admin operations use the shared renderer. Native form controls, ratings and chart visualizations remain managed by their existing components. No additional runtime dependency.

Run npm run icons:build --prefix web-static to regenerate the portable sprite and specimen page. This also runs before builds. The public sprite is always generated; the separate review artifacts are generated when design/logo-review exists.

Validation:
- Vue/TypeScript checks and Vite/PWA production build passed.
- 18 Node regressions passed.
- browser_review.py: reader navigation, directory/keyboard/long-page segments, OCR stale response handling, mobile bubbles/editor, retry and error states passed. Synthetic fixtures only.
- browser_layout.py: light/dark at 360/600/768/1024/1440px, view switching, pagination/history/jump, loading/empty/error/retry and four admin layouts passed. Brand favicon and privacy-mode checks included.
- Actual HTTPS preview: F/B asset loading, favicon changes, first/last navigation, 360/390/600/768/1024/1440px and the 46-icon specimen passed; no JavaScript errors.

Only static preview files were updated. Production master and services remain at 40b67b9. The pre-change preview static files are retained at /srv/nohentai/integrated-review/www-before-brand-20261112. Restore that directory's contents over /srv/nohentai/integrated-review/www/ to roll back the preview; no database rollback is involved. Previous hashed bundles remain available for clients during service-worker updates.
