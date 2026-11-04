#!/bin/sh
# Publish immutable assets before atomically switching the SPA shell.
# Old tabs can still import old chunks after a release switch.
set -eu
cd "$(dirname "$0")/.."
test -f web-static/dist/index.html
if test -d web-static/dist/data; then
    echo 'dist/data must be absent: run the complete npm run build' >&2
    exit 1
fi
web_root="${NOHENTAI_WEB_ROOT:-/srv/nohentai/www}"
install -d -m 0755 "$web_root/releases" "$web_root/assets"
exec 9>"$web_root/publish.lock"
flock 9
# Seed old hash assets too, including releases predating the shared directory.
for previous in "$web_root"/releases/*; do
    if test -d "$previous/assets" && ! test "$previous/assets" -ef "$web_root/assets"; then
        cp -an "$previous/assets/." "$web_root/assets/"
    fi
done
cp -an web-static/dist/assets/. "$web_root/assets/"
chmod -R a+rX "$web_root/assets"
release="$web_root/releases/$(date -u +%Y%m%dT%H%M%S)-$$"
install -d -m 0755 "$release"
cp -a web-static/dist/. "$release/"
rm -rf "$release/assets"
ln -s ../../assets "$release/assets"
chmod -R a+rX "$release"
ln -sfnT "$release" "$web_root/current.next"
mv -Tf "$web_root/current.next" "$web_root/current"
printf 'Published: %s\n' "$release"
