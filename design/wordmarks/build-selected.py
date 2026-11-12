"""Outline the selected A treatment; build-time tools only: fonttools, uharfbuzz."""
from pathlib import Path
from io import BytesIO
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

root = Path(__file__).resolve().parents[2]
font = instantiateVariableFont(TTFont(root / 'design/wordmarks/fonts/nunito.ttf'), {'wght': 850}, inplace=True)
font_data = BytesIO(); font.save(font_data)
face = hb.Face(font_data.getvalue()); shaped_font = hb.Font(face)
shaped_font.scale = (font['head'].unitsPerEm, font['head'].unitsPerEm)
buf = hb.Buffer(); buf.add_str('NoHentai'); buf.guess_segment_properties()
hb.shape(shaped_font, buf, {'kern': True})
glyphs = font.getGlyphSet(); order = font.getGlyphOrder()
svg = SVGPathPen(glyphs, ntos=lambda n: format(round(n, 3), 'g'))
bounds = BoundsPen(glyphs); x = 0
for info, position in zip(buf.glyph_infos, buf.glyph_positions):
    transform = (1, 0, 0, -1, x + position.x_offset, -position.y_offset)
    glyphs[order[info.codepoint]].draw(TransformPen(svg, transform))
    glyphs[order[info.codepoint]].draw(TransformPen(bounds, transform))
    x += position.x_advance - 40  # Selected A: tracking -0.04em at 1000 UPM.
left, top, right, bottom = bounds.bounds
view = f'{left - 2:.3f} {top - 2:.3f} {right - left + 4:.3f} {bottom - top + 4:.3f}'
width = round((right - left + 4) / (bottom - top + 4) * 20, 3)
path = svg.getCommands()
standalone = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="{width}" height="20" fill="currentColor"><title>NoHentai</title><path d="{path}"/></svg>\n'
(root / 'web-static/public/brand/wordmark-a.svg').write_text(standalone)
component = f'''<!-- Selected A: Nunito 850, -0.04em tracking, shaped and outlined at build time.
     Source and SIL OFL: design/wordmarks/fonts/. Regenerate: build-selected.py. -->
<template>
  <svg class="nh-brand-wordmark" viewBox="{view}" width="{width}" height="20" fill="currentColor" aria-hidden="true" focusable="false">
    <path d="{path}" />
  </svg>
</template>
<style scoped>
.nh-brand-wordmark {{ display: block; flex: 0 0 auto; color: var(--text-color); }}
</style>
'''
(root / 'web-static/src/components/ui/BrandWordmark.vue').write_text(component)
print(f'NoHentai wordmark: {width} × 20px; glyph outlines, no runtime font request')
