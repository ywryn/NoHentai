# Icon style directions

Preview: https://nohentai.com:8446/icon-directions.html

A / の流: open loops, sweeping terminals and asymmetric soft contours, relating to the selected F identity. Anime influence is concentrated in the eye, reading and gallery symbols.
B / コマ: comic frames, dialogue panels, paper corners and angular terminals. Monochrome geometry, without decorative sparkles or extra badges.

Both families cover the same 46 icon names as the application. These are individually authored editable SVG paths, not raster image-generation outputs or stroke-style filters over the existing icons. Review them at 16/20/24/32px in the same colors and contexts. Basic action semantics stay recognizable. The UI examples are local interactive specimens; they do not call application APIs.

Source: sets.mjs. Template: page.html. Generate: node design/icon-directions/build.mjs.
Outputs: design/logo-review/icon-directions.html and assets/icons-direction-{a,b}.svg.
The generator verifies complete coverage against web-static/src/icons/paths.ts. Selection is stored only in localStorage and can be copied into the conversation.

Deploy only these three generated files to /srv/nohentai/logo-review/ and assets/. The current icon catalog also links to the comparison. No production or integrated-preview application replacement has been performed for these proposals. Selected front/admin logos remain F/B.

Validation: all 92 icons render; 320/360/390/600/720/768/1024/1440px without page overflow; selectable size/color/theme, query and empty state, choice persistence, demo first/last/previous/next behavior and download responses checked in Chromium. No JavaScript errors.
