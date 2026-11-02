#!/bin/sh
# Run from the repository after `npm ci && npm run build` in web-static.
# Publishes an already-built frontend atomically. Keeps prior releases for rollback.
set -eu
cd "$(dirname "$0")/.."
test -f web-static/dist/index.html
if test -d web-static/dist/data; then
    echo 'dist/data must be absent: run the complete npm run build' >&2
    exit 1
fi
release="/srv/nohentai/www/releases/$(date -u +%Y%m%dT%H%M%S)-$$"
install -d -m 0755 "$release"
cp -a web-static/dist/. "$release/"
chmod -R a+rX "$release"
ln -s "$release" /srv/nohentai/www/current.next
mv -Tf /srv/nohentai/www/current.next /srv/nohentai/www/current
printf 'Published: %s\n' "$release"
