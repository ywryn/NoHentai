# NoHentai UI icons

Shared source: paths.ts. Shared Vue renderer: components/ui/AppIcon.vue.

- 24 × 24 coordinate grid; 1.8px stroke; round caps and joins.
- Draw within 3–21px bounds; prefer open shapes and generous internal spaces.
- Render at 16/18px in compact controls, 20/24px in toolbars.
- Use currentColor; no separate light/dark files or icon fonts.
- All SVGs are decorative (aria-hidden, focusable=false). Icon-only buttons need a meaningful aria-label; stateful controls retain aria-pressed/expanded and disabled semantics.
- Use chevron-left/right for adjacent pages, first-page/last-page for page boundaries, arrow-left for return, external for leaving the current context.
- Direction names describe screen direction. Reading-order logic remains in the reader, not the icon renderer.
- Keep actual keyboard instructions as text. Do not replace chart data, rating values or textual mathematical operators with pictograms.
- AdminIcon is a compatibility wrapper over AppIcon. Its arrow/chevron/back aliases map to directional icons without changing admin actions.

These project-maintained paths have no external runtime or icon-font dependency. PrimeVue remains responsible for its form and chart components. This change does not replace business components or chart visualizations.

Privacy mode excludes only .nh-brand-mark; artwork retains its existing blur behavior.

Branding uses the user-selected image-generation originals, without pixel edits: public/brand/mark-g.png (public site) and mark-b.png (admin). Both are transparent 1254px PNGs; the PWA manifest declares the actual size and purpose:any. They are not declared maskable because their safe area has not been designed for every OS mask. G/B provenance and prompts: design/logo-review/generation-notes.txt.

Preview deployment only: https://nohentai.com:8445/
Logo and SVG icon specimen page: https://nohentai.com:8446/icons.html
