# NoHentai branding

Approved identity: public G, Admin B. Approved icon family: the original 46-icon set in src/icons/paths.ts, not either of the later style proposals.

The public mark is web-static/public/brand/mark-g.png, copied unchanged from the selected built-in image_gen output. Admin uses mark-b.png. BrandMark is the shared renderer. The favicon follows the current route; public PWA and Apple touch icons use G. Original generation prompts are retained in design/logo-review/generation-notes.txt.

Mobile gutters are 16px. G's opaque left edge starts at 154px on a 1254px canvas; App.vue compensates that transparent inset at the 40px display size. If the identity or display size changes again, verify the visible edge against page content. Privacy mode must exclude brand marks while retaining artwork protection.

All UI icons share AppIcon.vue, with AdminIcon as a compatibility wrapper. npm run icons:build --prefix web-static rebuilds the SVG sprite and review catalog; production builds also run this step. Rejected styles remain in design/icon-directions only as design history.

Release checks: TypeScript/Vue checks, Vite/PWA build, 18 Node regressions, responsive browser suite, G/B route favicon and asset loading, original 46-icon catalog, first/last-page controls and six viewport widths passed.

Deployment uses deploy/publish-frontend.sh to publish static files and atomically switch /srv/nohentai/www/current. No backend restart, schema migration or data change is required. The prior release is /srv/nohentai/www/releases/20261112T114423-618496; switching current back to that release restores the previous frontend. Keep previous hashed assets available for existing tabs. Production source is tracked on master; revert the branding commits separately if reverting code is required.
