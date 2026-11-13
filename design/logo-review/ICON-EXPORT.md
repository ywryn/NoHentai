# Browser and installed-app icon exports

The selected public artwork remains G and the admin artwork remains B. Header
PNGs and header layout are unchanged. Icons are now dedicated layouts rather
than using the 1254px header source directly.

- Public tab: `brand/favicon-g-v2.png`, 48px, centered visible bounds and a
  downward optical adjustment equivalent to 0.5px at the usual 16px tab size.
  This addresses the reported upward appearance; it is an optical correction,
  not a claim that the source image's vertical bounding box was off-center.
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
