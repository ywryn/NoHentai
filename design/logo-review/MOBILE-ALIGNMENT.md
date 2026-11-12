# Mobile branding follow-up

Decision: retain the original 46-icon family (91dc48e). The two proposed icon directions were declined and are archived only. Neither was adopted in the application.

Navigation and route outer gutters share --page-gutter (16px below 768px, 24px otherwise). Navigation follows the 1240px content alignment on wide screens. Removed competing forced header padding and logo button inset. The current F image has ~4px of left transparent inset when displayed at 40px; the brand link offsets that inset for optical alignment. This does not modify the generated image or change the 44px button height. Card-internal padding remains intact.

Printed/daily page side padding now overrides route stylesheet load-order differences. Statistics grids use minmax(0,1fr), shrinkable panels and wrapping header controls to prevent page-wide overflow at 320px; data and chart types are unchanged.

Logo exploration: original F is compared with G (curved terminal, lighter lower-right) and H (compact contour). These are built-in image_gen outputs, saved unchanged as assets/logo-g.png and logo-h.png. Exact prompts: refinement-generation-notes.txt. F remains the active public identity; B remains the admin identity.

Preview: https://nohentai.com:8445/
Logo comparison: https://nohentai.com:8446/

Validation: Vue/TypeScript production build passed. Existing responsive browser suite passed with a new optical-alignment assertion. HTTPS checks across five public routes and six viewport widths (320/390/600/768/1024/1440px) passed for brand alignment, route gutters and page overflow. Eight logo assets, new comparison ordering, keyboard preview and choice persistence passed. No production deployment or database changes.
