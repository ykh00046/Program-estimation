# Fonts

## Substitution notice

The source app (`v3/main.py`) declares this font stack for QApplication:

```
Pretendard, Segoe UI, Noto Sans KR
```

…and the global Qt stylesheet pins:

```
'Bahnschrift', 'Malgun Gothic', 'Segoe UI', sans-serif
```

**Bahnschrift** is the visual identity but is a Microsoft Windows system font, not freely redistributable. **Pretendard** is also free but heavyweight to ship. For this design system we substitute:

| Source | Substitute | Why |
|---|---|---|
| Bahnschrift | **Inter Tight** (Google Fonts) | Geometric grotesque, similar x-height and condensed feel |
| Noto Sans KR / Pretendard | **Noto Sans KR** (Google Fonts) | Direct match for Korean glyph coverage |

In `colors_and_type.css` the `--font-sans` token keeps the original Bahnschrift name in the stack so a real Windows install still resolves correctly:

```css
--font-sans: 'InterTight', 'Bahnschrift', 'Pretendard', 'Malgun Gothic',
             'NotoSansKR', 'Noto Sans KR', 'Segoe UI', sans-serif;
```

## ASK FOR THE USER

If pixel-fidelity matters, please drop **Bahnschrift Regular** + **Bahnschrift SemiBold** (`.ttf` or `.woff2`) into this folder and we will register them in `colors_and_type.css`. The Inter Tight substitution is close but not identical.

For now, previews load Inter Tight + Noto Sans KR via Google Fonts CDN inline:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap" rel="stylesheet">
```
