---
name: dhr-batch-recipe-design-system
description: Design system for DHR 배합 프로그램 v3 — a Korean manufacturing batch-recipe Windows desktop tool. Use when designing for this product, recreating its surfaces, or producing artifacts that should match its dark amber-on-near-black aesthetic.
---

# DHR 배합 프로그램 — Design System

## When to use this skill
Apply when the user asks for designs, mockups, slides, or interfaces that should look like or extend the DHR 배합 프로그램 v3 desktop application. Signals: mentions of "DHR", "배합", "Korean manufacturing", "shop-floor", "FluentWindow", or asks for variants of the mixing/recipe/DHR-management screens.

Do **not** use this skill for:
- Generic Korean dark-mode designs (this system is product-specific)
- Anything calling for color palettes outside the deep-dark + amber range
- Consumer or marketing surfaces (this is a tool, not a product page)

## What's in the system

| Path | What it contains |
|---|---|
| `README.md` | Product context, content fundamentals (voice/tone/Korean copy patterns), visual foundations (color, type, spacing, animation), iconography mapping |
| `colors_and_type.css` | All tokens as CSS custom properties — import this directly into HTML artifacts |
| `assets/` | Net-new wordmark (flagged) + assets README listing what is and isn't here |
| `fonts/` | Inter Tight + Noto Sans KR (Bahnschrift/Pretendard substitutes — flagged) |
| `preview/` | 16 design-system-tab cards covering colors, type, spacing, components, brand |
| `ui_kits/desktop/index.html` | React-free recreation of the three primary surfaces: mixing page, sign-in modal, DHR recipe library |

## How to apply this system

### Always
- **Import `colors_and_type.css`** at the top of every new HTML artifact. It sets `body` background to the diagonal gradient and font stack automatically. All tokens are exposed as `--bg-primary`, `--accent`, `--surface-alt`, etc.
- **Korean copy first**, English only for the single `Welcome Back!` headline. Voice is terse polite imperative — see README → Content fundamentals.
- **No emoji, no decorative imagery, no animation flourishes.** This is shop-floor software.
- **Cards = 14px radius, no shadow.** The single exception is the `MintInfoCard` KPI which gets `--shadow-amber-glow`.
- **Borders are white at 4–18% alpha**, never solid grays.
- **Iconography**: Lucide stroke=2 substitutes for FluentIcon. Mapping table in README.

### Color rules
- The accent variable is `--accent` (`#E3A12F`). The token name is `MINT_*` in the source repo for legacy reasons — the actual color is amber/gold. Do **not** introduce mint or teal anywhere.
- Primary buttons use `--accent-gradient` fill with `--text-on-accent` (`#1A1206`) text.
- Selected sidebar items: `--accent-18` background + `--accent` text + 3px amber left border + bold weight.
- Selected table rows: `--accent-22` background + `--accent` text.
- Errors fill at 10–20% red alpha; never solid red blocks.

### Type rules
- Stack: Inter Tight (Latin) + Noto Sans KR (Korean). Keep Bahnschrift / Malgun Gothic / Pretendard / Segoe UI in the fallback chain.
- Sizes are pixel-defined: 11 (tiny labels, uppercase), 13 (secondary), 14 (body — explicit), 17 (amount entry, 13pt original), 24 (page titles), 30 (h1).
- Weights ≥ 500 in chrome. Korean is sentence-case; Latin uppercase labels get `letter-spacing: 0.3px`.
- Required-field markers: `*` in `--accent`.

### Layout rules
- Window 1200×800. Sidebar 220px. Titlebar 36px. Status bar 28px. Page gutters 28×22.
- Card padding: 32×26 hero, 14×10 toolbar, 20×15 KPI.
- Table row height: 48px (factory-readable).
- Default vertical rhythm between cards: 16px. Inside-card: 14px.

### Things to flag if asked to do them
- Drawing icons from scratch → ask if Lucide substitute is acceptable
- Adding photographic imagery → product never carries imagery
- Adding emoji → product never uses emoji
- Adding animations beyond the InfoBar slide-in → product is intentionally still
- Replacing the wordmark → current one is net-new; surface this if the user has an official mark

## Reference files to read before starting
1. `README.md` — full context, every time
2. `colors_and_type.css` — for token names (don't invent new colors)
3. `ui_kits/desktop/index.html` — for component patterns (sidebar item, table row, KPI card, primary button)
4. `preview/components-*.html` — for isolated component shapes

## Authored by
Reverse-engineered from `ykh00046/Program-estimation` (branch `main`, app root `v3/`). Source-of-truth file: `v3/ui/styles.py`.
