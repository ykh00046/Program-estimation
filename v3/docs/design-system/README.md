# DHR 배합 프로그램 — Design System

> A design system reverse-engineered from the **DHR 배합 프로그램 v3** — a Korean manufacturing batch-recipe management Windows desktop application built with PySide6 and qfluentwidgets.

---

## Product context

**DHR 배합 프로그램 v3** (literally "DHR Mixing Program v3") is a single-user Windows desktop application for the Korean manufacturing floor. Operators load a saved recipe, enter a target batch weight in grams, scan or type material LOT numbers row-by-row, sign for the work, and generate an Excel/PDF DHR (Device History Record) sheet plus a Google Sheets backup.

It is a **shop-floor tool**, not a consumer app. Every screen is in Korean, every workflow assumes a single operator standing in front of a scale with a barcode scanner, and the UI deliberately uses high-contrast colors and large hit targets (48px row heights, 44px buttons) so it remains readable in factory lighting.

### Surfaces represented
There is one product, one surface: the **desktop application**. The sidebar exposes seven sub-interfaces:

| Sidebar item | Purpose |
|---|---|
| 배합 (Mixing) | The main work screen — recipe + amount + materials table + save |
| 수기 입력 (Manual Input) | Fall-back manual entry path for missing recipes |
| 일괄 생성 (Bulk Creation) | Paste-driven bulk DHR generation |
| DHR 관리 (DHR Management) | Recipe library — split-pane list + editor |
| 기록 조회 (Records) | Search and reprint past batch records |
| 설정 (Settings) | PDF scan effects + signature options |
| 작업자 변경 (Change Worker) | Re-open the worker selection dialog |

### Sources

This design system was derived from a single GitHub repository:

- **Repo**: [`ykh00046/Program-estimation`](https://github.com/ykh00046/Program-estimation) (branch: `main`)
- **App root**: `v3/`
- **Files studied**:
  - `v3/CLAUDE.md` — project overview, stack, conventions
  - `v3/main.py` — app bootstrap, theme/font setup
  - `v3/ui/styles.py` — the canonical `UITheme` token table (SSOT)
  - `v3/ui/components.py` — `StyledButton`, `LabeledField`, `InfoCard`, `MintInfoCard`, `StatusBar`, `DataTableWidget`, `ConfirmDialog`
  - `v3/ui/main_window.py` — `FluentWindow` shell + sidebar wiring
  - `v3/ui/builders.py` — page composition (mixing page, settings page, action pages)
  - `v3/ui/notifications.py` — InfoBar toast helpers
  - `v3/ui/panels/recipe_panel.py`, `work_info_panel.py`, `material_table_panel.py`, `recipe_management_interface.py` — the actual screens

The reader is not assumed to have repository access; everything needed to design _for_ this brand has been extracted into this folder.

---

## Index

| File | What's in it |
|---|---|
| `README.md` | This file — context, content fundamentals, visual foundations, iconography |
| `colors_and_type.css` | All color and typography tokens as CSS custom properties |
| `SKILL.md` | Cross-compatible Agent Skill manifest for downstream use |
| `assets/` | Iconography, signature placeholders, and brand marks |
| `fonts/` | Bahnschrift substitute (Inter Tight) + Noto Sans KR Korean fallback |
| `preview/` | Design System tab cards (~700×variable px each) |
| `ui_kits/desktop/` | React/JSX recreation of the desktop app — sidebar, mixing page, recipe manager |

---

## Content fundamentals

The product is in **Korean**, addressing a single shop-floor operator. The voice is **terse, instructional, and respectful** — formal sentence endings (`-입니다`, `-하세요`, `-합니다`) without being stiff.

### Tone
- **Imperative and direct** for primary actions: `저장` (Save), `초기화` (Reset), `LOT 자동 배정` (Auto-assign LOT).
- **Polite explanatory** for system messages: `배합량을 먼저 설정해주세요!` ("Please set the batch amount first!"), `해당 일자에 맞는 자재LOT 정보를 찾을 수 없습니다.` ("No matching material LOT info found for that date.")
- **Status-bar style** for ambient messages: `기본 스케일: M-65 | 허용오차: ±0.05`, `테이블이 초기화되었습니다.` ("Table has been reset.")
- **Welcome moment**, but only one: the worker sign-in dialog says `Welcome Back!` in English with `작업을 시작하려면 작업자를 선택하세요` ("Select a worker to start work") underneath. This is the only English headline in the product.

### Casing & punctuation
- Korean labels use **standard sentence case**; no all-caps Korean.
- The component library does push **uppercase Latin labels** through `LabeledField` — that helper applies `.upper()` and `letter-spacing: 0.3px` to label text. So when a label happens to be Latin (a worker name, a code), it ends up like `WORKER NAME`. Korean labels are unaffected because Korean has no case.
- Required-field markers: a single accent-colored `*` after the label (`레시피명 *`).
- Punctuation is sparse. Status bar separators are ` | ` with spaces. Inline parentheses for hints: `초기화 (Ctrl+R)`.

### Pronouns and address
- **No first-person**, no `I` / `we` / `우리`. The app does not editorialize.
- Where the user is addressed it's via implicit polite imperative (`-하세요`). Not `당신` (you).

### Examples (lifted verbatim)

| Korean | Gloss |
|---|---|
| `DHR 배합 프로그램` | Window title |
| `배합 중량 (g)` | "Batch weight (g)" — input label |
| `자재 목록` | "Material list" — section title |
| `LOT 자동 배정` | "Auto-assign LOT" — secondary button |
| `배합 저장` | "Save batch" — primary button |
| `작업자를 선택하세요.` | "Please select a worker." — validation message |
| `LOT: A2026-0142 저장이 완료되었습니다.` | Toast on success — concrete LOT in the message, period at end |
| `기본 스케일: M-65 \| 허용오차: ±0.05` | Idle status bar |
| `이미 실행 중입니다.` | "Already running." — single-instance guard |

### Vibe
Quietly confident, never cheerful. There is no marketing copy anywhere in the product, no "Pro tip", no emoji, no exclamation points outside of warnings. Errors are stated as facts (`저장 중 오류가 발생했습니다`), not apologized for.

### Emoji
**None.** The product does not use emoji in UI strings, log messages, or button labels. The CLAUDE.md developer doc uses ❌ / ✅ to mark wrong-vs-right code patterns, but those never reach users.

---

## Visual foundations

### Color
A **deep-dark base** (`#0C0F14` → `#10151F` diagonal gradient) carrying an **amber/gold accent** (`#E3A12F`) that shifts to a brighter gradient (`#F2C066` → `#D9901E`) on primary buttons. The token name in source is `MINT_ACCENT` for legacy reasons — the actual color is amber/gold, not mint. (One file, `main.py`, sets a teal `#03DAC6` Fluent theme color, but `setStyleSheet(UIStyles.get_main_style())` is called immediately after and overrides it everywhere the user actually looks.) Treat amber `#E3A12F` as canonical.

Surfaces step up in two levels: `#10141B` (cards on background) and `#141A23` (cards on cards / inputs). Borders are not solid lines — they are **white at 4–18% opacity** (`rgba(255,255,255,0.04…0.18)`), giving panels a subtle inner glow rather than a hard frame.

Status colors: green `#2ECC71`, amber-warning `#F5A623`, red `#FF4D4F`. Error fills use `rgba(239,68,68,0.1–0.2)`.

### Type
- **Primary stack**: `'Bahnschrift', 'Malgun Gothic', 'Segoe UI', sans-serif` set globally on `QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTextEdit, QPlainTextEdit`.
- **Application-level fallbacks** (`setFontFamilies` in main.py): `Pretendard, Segoe UI, Noto Sans KR`.
- Bahnschrift is the visual identity — a Microsoft DIN-flavored geometric sans, condensed-friendly. On the web it has no exact match; this design system substitutes **Inter Tight** (close geometry, similar x-height) and pairs it with **Noto Sans KR** for Korean. Flagged in `fonts/README.md`.
- Sizes are pixel-defined in stylesheets: `11px` (tiny captions, uppercase labels), `13px` (secondary buttons), `14px` (default body — explicitly set on every input class), `13pt` for amount entry, `30–32px` for KPI values, `24px` for page titles via `LargeTitleLabel`.
- Weights: 500 / 600 / 700 / 800. The product never uses weights below 500 in chrome.
- Letter-spacing: `0.3px` on `LabeledField` uppercase labels, `0.5–0.6px` on KPI titles. Headline `Welcome Back!` uses `-0.5px` (negative) — the only place tracking goes negative.

### Spacing and rhythm
- Card border-radius: **14px** (`CARD_BORDER_RADIUS`). Buttons: **8px**. Pills/chips inside dialogs: **16px** outer.
- Card content padding: `26–32px` for hero cards, `10–14px` for compact toolbars.
- Page gutter (around the whole MixingPage content): `28px × 22px`.
- Default vertical rhythm between cards: `16px`. Inside-card spacing: `14px`.
- Table row height: **48px** — wide for thumb-on-trackball factory environments.
- Input padding: `8px 12px` (compact), `10px 14px` (default).

### Backgrounds
- The window background is a **subtle diagonal gradient** from `#0C0F14` (top-left) to `#10151F` (bottom-right). Always linear, always 0,0 → 1,1.
- Cards are **flat fills** on top of that gradient. No card-on-card gradients. No noise/texture.
- No imagery. No illustrations. No background patterns. The product carries zero decoration — it is a tool, not a product page.
- "Mica" (Windows 11 acrylic) is **explicitly disabled** in `main_window.py` with `self.setMicaEffectEnabled(False)`. The product wants opaque, predictable surfaces.

### Animation
- The product does **not animate decoratively**. Hover and focus state changes are instant (Qt default ~150ms color transitions through stylesheet repaint, no easing curves).
- Status messages auto-clear after 5000ms via `QTimer.singleShot` — a hard timeout, not a fade.
- The single piece of motion design is the **InfoBar toast** (qfluentwidgets default): slides in from top-right, dismisses on its own. We don't override timing.
- No bounces, no parallax, no page transitions.

### Hover & press states
- **Inputs**: `FIELD_BG` `rgba(255,255,255,0.08)` → hover `0.12` → pressed `0.16`. Border doesn't change on hover; only the fill brightens.
- **Focus on input**: border becomes `1px solid #E3A12F` AND fill switches to `rgba(227,161,47,0.08)` — the amber tint follows you into the field.
- **Primary button hover**: gradient brightens (`#F2C066→#D9901E` → `#FFD07A→#E3A12F`).
- **Primary button pressed**: collapses to flat `#D9901E` (the gradient end color).
- **Secondary button hover**: background fills with `FIELD_BG`, text goes from `TEXT_SECONDARY` to `TEXT_PRIMARY`, border lightens.
- **Sidebar item hover**: amber-tinted background `rgba(227,161,47,0.12)`, text brightens.
- **Sidebar item selected**: amber-tinted background `rgba(227,161,47,0.18)`, text becomes amber, **3px amber left border**, font goes bold.
- **Table row hover**: amber tint at 12% alpha. Selected: amber tint at 22% with a `2px solid #E3A12F` cell outline.
- No press shrink. No transform-scale. The product never moves things on press.

### Borders
- Borders are **opacity-based whites**, never solid grays. Five tiers:
  - `BORDER_SUBTLE_LIGHT` `rgba(255,255,255,0.04)` — between table rows
  - `BORDER_SUBTLE` `rgba(255,255,255,0.06)` — card edges
  - `BORDER_COLOR` `rgba(255,255,255,0.08)` — dividers, default input borders
  - `BORDER_LIGHT` `rgba(255,255,255,0.18)` — input borders that need to read as "field"
  - `ACCENT_BORDER` `rgba(227,161,47,0.35)` — disabled-primary outline
- Group boxes get a 1px subtle border + `8px` radius.

### Shadows & elevation
- Only one component uses a real drop shadow: **`MintInfoCard`** (the KPI card). It applies a `QGraphicsDropShadowEffect`: blur 28, color `rgba(227,161,47,55)` (amber at ~22% alpha), offset `0 6`. This produces a warm amber glow under the card, not a neutral gray drop shadow.
- All other elevation is conveyed by **surface color stepping**, not shadow.

### Capsules vs protection gradients
- The product does **not** use protection gradients (image overlays, scrim fades).
- Pills/capsules appear only as toast `InfoBar`s and the worker dialog (which uses a `16px` rounded frameless dialog shell).

### Transparency & blur
- Used **structurally**, not decoratively: white-alpha tints carry the entire input/border/hover system. There are zero `backdrop-filter: blur`s, zero glassmorphism effects.

### Imagery
- The only "imagery" is a captured **signature PNG** from a signature pad widget — it lands on PDFs, not in the UI chrome.
- Color vibe of any imagery: irrelevant; there isn't any.

### Corner radii
- `4px` — sidebar item highlight
- `6px` — small inputs (LineEdit, SpinBox, Search)
- `8px` — buttons, group boxes, tab pane
- `14px` — cards (`CARD_BORDER_RADIUS`)
- `16px` — frameless modal dialogs

### Cards
A card is `#141A23` (`SURFACE_ALT`) fill, `1px solid rgba(255,255,255,0.06)` border, `14px` radius, **no shadow** (with the one MintInfoCard exception above). They sit directly on the gradient background. Card padding is content-driven: 32×26 for hero, 14×10 for toolbar, 20×15 for KPI.

### Layout rules
- **FluentWindow** shell: 280px collapsible left sidebar, content area fills the rest. Sidebar collapses to `~48px` on hover-out (when `sidebar.hover_expand` is on).
- **Default window size**: 1200×800. The amount-entry primary screen is designed at this size; deeper screens (record view, recipe manager) tolerate resizing up.
- **Status bar** at the bottom of the mixing page: 28px tall, with system clock pinned right and a Google Sheets backup indicator next to it.
- The product **stays on top** by default (`Qt.WindowStaysOnTopHint`) — a deliberate choice for shop-floor multi-tasking.

---

## Iconography

### Source
The product imports **`qfluentwidgets.FluentIcon`** (`FIF`) — the Microsoft Fluent UI System Icons set, redistributed inside qfluentwidgets as an **embedded SVG sprite**. Sidebar items are tagged with these enum values lifted directly from `builders.py`:

| Sidebar item | FluentIcon constant |
|---|---|
| 배합 | `FIF.MIX_VOLUMES` |
| 수기 입력 | `FIF.EDIT` |
| 일괄 생성 | `FIF.PASTE` |
| DHR 관리 | `FIF.LIBRARY` |
| 기록 조회 | `FIF.HISTORY` |
| 설정 | `FIF.SETTING` |
| 작업자 변경 | `FIF.PEOPLE` |

The icons render at sidebar size (~16–20px), monochrome, color-tinted to match text. They are NOT brand-customized.

### Substitution in this design system
The qfluentwidgets icon SVGs are not redistributable as standalone assets here. For the web-based UI kit + preview cards we substitute **[Lucide](https://lucide.dev)** (CDN-loaded), choosing icons whose stroke weight (~1.5–2px), sharp corners, and 24×24 grid most closely match Fluent UI System Icons. The mapping:

| FluentIcon | Lucide substitute | Reasoning |
|---|---|---|
| `MIX_VOLUMES` | `flask-conical` | Closest manufacturing/mixing visual |
| `EDIT` | `pencil` | Direct match |
| `PASTE` | `clipboard-paste` | Direct match |
| `LIBRARY` | `library` | Direct match |
| `HISTORY` | `history` | Direct match |
| `SETTING` | `settings` | Direct match |
| `PEOPLE` | `users` | Direct match |

**This substitution is flagged.** If pixel-fidelity to Fluent System Icons is required downstream, fetch them from [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) and replace `lucide` references.

### Other graphical elements
- **No emoji.** The product never uses emoji as iconography.
- **No unicode glyphs as icons.** Even the "+" / "−" category-add buttons in `recipe_management_interface.py` are real button labels, not graphical icons.
- **No PNG icons.** Everything is SVG via the qfluentwidgets sprite.
- **No raster brand mark.** The product has no logo image — its identity is the text "DHR 배합 프로그램" in the title bar plus the amber accent. We construct a wordmark in `assets/dhr-wordmark.svg` for use in slides and previews; this is **net-new** and flagged.

---
