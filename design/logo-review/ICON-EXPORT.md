# Browser and installed-app icon exports

The selected public artwork remains G and the admin artwork remains B. Header
PNGs and header layout are unchanged. Icons are now dedicated layouts rather
than using the 1254px header source directly.

- Public tab: `brand/favicon-g-v4.png`, 48px, warm neutral rounded-square background,
  centered visible bounds without an optical vertical offset. The earlier
  downward adjustment was withdrawn after comparing the rounded-background version.
- Admin tab: `brand/favicon-b-v2.png`, 48px, centered visible bounds.
- Apple home screen: `brand/apple-touch-g-v2.png`, opaque 180px.
- PWA: opaque G icons at 192px and 512px plus a separate 512px maskable export.
  The maskable art fits the central circle of radius 40% of the icon size,
  following https://www.w3.org/TR/appmanifest/#icon-masks.
- Legacy `favicon.ico` (16/32/48), `favicon.svg` and `pwa-*` discovery URLs are
  synchronized too. Explicit references use new filenames to avoid old cached
  artwork. The manifest URL stays unchanged and its explicit `/` ID matches its
  previous computed identity from start_url.

Regenerate with the existing browser-test Python environment:

```sh
python -m pip install -r tests/requirements-browser.txt
python -m playwright install chromium
python web-static/scripts/build-brand-icons.py
npm run build --prefix web-static
```

The script composes SVG layouts around the original PNGs and exports them using
Chromium. No new runtime dependency is required. The visible bounds exclude
nearly transparent generation noise. The warm neutral app-icon background is
opaque; the platform supplies any rounded mask.

Deploy the updated static build through `deploy/publish-frontend.sh`. Include the
manifest MIME location from `deploy/nginx.conf` in the live TLS server config;
check `nginx -t` before a graceful reload. Rollback uses the prior static release
symlink and, if needed, the saved nginx configuration. No database changes.

Validation includes an actual headed Chromium tab-strip comparison, source PNG
hash preservation, declared dimensions and opacity, mask safe-area checks,
responsive header regressions and initial/admin route favicon switching. The
repository contains no native Android/iOS/Capacitor/Cordova/Tauri/Electron app
project; independently packaged APK/IPA launcher icons cannot be verified here.
Installed OS shortcuts can retain cached artwork; their update timing is not
controlled by the page and has not been validated on physical devices.

The prior transparent `brand/favicon-g-v2.png` is retained for comparison.
The rounded background changes only the public tab icon, not the admin or installed-app layouts.

For height comparison, `favicon-g-v3.png` retains the previous downward shift;
`favicon-g-v4.png` is the centered rounded-background version.
