# G logo wordmark studies

Review: https://nohentai.com:8446/wordmarks.html

A 柔圆: Nunito 850, rounded and compact.
B 轻行: Outfit 650 with lettering-only -8deg shear.
C 书卷: Fraunces Italic 600, editorial reading style.
D 刻线: Sora 650, compact geometric contrast.

These are font-based wordmark treatments with exact NoHentai spelling. Font sources and SIL Open Font License copies are retained in fonts/ and notes.txt. Font files are served locally for the comparison page; no fonts are added to the production frontend until selection.

To update the temporary page, copy index.html to /srv/nohentai/logo-review/wordmarks.html, notes.txt to wordmark-notes.txt, and fonts/ to wordmark-fonts/. The page uses the existing assets/logo-g.png on that review origin. No build or API is required.

Validation: all four fonts loaded; seven viewport widths (320/360/390/600/768/1024/1440px), three compact sizes (16/18/20px), phone-preview overflow, theme switch, persisted selection and console errors checked in Chromium.

Separate requested UI edit: remove only the redundant right arrow next to 开始阅读 in GalleryDetail; retain the reading icon, link, label and click behavior. Its obsolete CSS is removed. Vite/PWA build and actual detail-link check passed.
