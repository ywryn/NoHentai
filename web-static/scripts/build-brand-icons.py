"""Export icon-only layouts without changing the selected logo artwork.

Requires tests/requirements-browser.txt and `playwright install chromium`.
Run from any directory: python web-static/scripts/build-brand-icons.py
The browser rasterizes SVG compositions; the header's source PNGs are untouched.
"""
import base64
import struct
from pathlib import Path
from playwright.sync_api import sync_playwright

PUBLIC = Path(__file__).resolve().parents[1] / 'public'
BACKGROUND = '#faf8f5'
# Visible artwork bounds (alpha > 16); ignore near-transparent generation noise.
BOUNDS = {'g': (153, 249, 1037, 1015), 'b': (210, 267, 1045, 984)}


def composition(mark, fraction, down=0, background=None, rounded=False):
    left, top, right, bottom = BOUNDS[mark]
    extent = max(right - left, bottom - top) / fraction
    cx, cy = (left + right) / 2, (top + bottom) / 2
    # Moving the viewBox up moves the artwork down. Down is a canvas fraction.
    x, y = cx - extent / 2, cy - extent * (0.5 + down)
    data = base64.b64encode((PUBLIC / f'brand/mark-{mark}.png').read_bytes()).decode()
    radius = extent * 0.22 if rounded else 0
    surface = f'<rect x="{x}" y="{y}" width="{extent}" height="{extent}" rx="{radius}" fill="{background}"/>' if background else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {extent} {extent}">'
            f'{surface}<image width="1254" height="1254" href="data:image/png;base64,{data}"/></svg>')


def ico(images):
    offset = 6 + 16 * len(images)
    entries = []
    for size, png in images:
        entries.append(struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(png), offset))
        offset += len(png)
    return struct.pack('<HHH', 0, 1, len(images)) + b''.join(entries) + b''.join(png for _, png in images)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def render(svg, size):
            data = page.evaluate('''async ({svg, size}) => {
              const image = new Image();
              image.src = 'data:image/svg+xml;base64,' + btoa(svg);
              await image.decode();
              const canvas = document.createElement('canvas');
              canvas.width = canvas.height = size;
              canvas.getContext('2d').drawImage(image, 0, 0, size, size);
              return canvas.toDataURL('image/png').split(',')[1];
            }''', {'svg': svg, 'size': size})
            return base64.b64decode(data)

        def write(name, svg, size):
            png = render(svg, size)
            (PUBLIC / name).write_bytes(png)
            return png

        # A half-pixel downward optical adjustment at the usual 16px tab size.
        # Only the public-site tab icon uses it; app and header layouts do not.
        tab = composition('g', 0.82, down=0.5 / 16, background=BACKGROUND, rounded=True)
        admin = composition('b', 0.82)
        write('brand/favicon-g-v3.png', tab, 48)
        write('brand/favicon-b-v2.png', admin, 48)
        (PUBLIC / 'favicon.ico').write_bytes(ico([(s, render(tab, s)) for s in (16, 32, 48)]))
        # Keep legacy discovery URLs consistent with the explicitly linked assets.
        png = base64.b64encode(render(tab, 48)).decode()
        (PUBLIC / 'favicon.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
            f'<image width="48" height="48" href="data:image/png;base64,{png}"/></svg>\n')
        app = composition('g', 0.72, background=BACKGROUND)
        for size in (192, 512):
            png = write(f'brand/app-g-{size}-v2.png', app, size)
            (PUBLIC / f'pwa-{size}x{size}.png').write_bytes(png)
        write('brand/apple-touch-g-v2.png', app, 180)
        # The artwork's bounding rectangle fits the central 40%-radius circle.
        write('brand/app-g-maskable-512-v2.png', composition('g', 0.58, background=BACKGROUND), 512)
        browser.close()
    print('Exported centered tab icons, Apple touch icon, PWA icons and legacy aliases.')


if __name__ == '__main__':
    main()
