# NoHentai Logo concept review

Preview: https://nohentai.com:8446/

- A: の字回环
- E: の字 · 大折角
- F: の字 · 简式收笔
- B: 藏书字母
- C: 漫画分镜
- D: 折页纸鹤

Six transparent PNG concepts generated with the built-in image_gen tool. Exact prompts and asset paths are recorded in generation-notes.txt. These are concept proposals; vector refinement follows selection. Production branding is unchanged.

The standalone page includes light/dark backgrounds, navigation lockups, 16/24/32px previews, image downloads, an accessible zoom dialog and local-only selection persistence. Copy the selected proposal and send it back in the conversation; no submission backend exists.

Deployment root: /srv/nohentai/logo-review
Nginx configuration: /etc/nginx/conf.d/nohentai-logo-review.conf
Firewall: TCP 8446 (IPv4/IPv6)

To redeploy, copy index.html, generation-notes.txt and assets/ to the deployment root. No application build or production restart is needed. To retire the preview, remove its Nginx configuration, validate and gracefully reload Nginx, remove the UFW rule for 8446/tcp and then remove the deployment root. Never remove shared TLS certificates.

Validated in Chromium at 320, 390, 768, 1100 and 1440px: no horizontal overflow, all six original images load, selection survives reload, modal arrow navigation and selection work, no JavaScript errors. HTTPS responds 200.
