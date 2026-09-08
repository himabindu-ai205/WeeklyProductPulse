---
name: Editorial Pulse
colors:
  surface: '#fff8f5'
  surface-dim: '#e0d8d5'
  surface-bright: '#fff8f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#faf2ee'
  surface-container: '#f4ece8'
  surface-container-high: '#eee7e3'
  surface-container-highest: '#e9e1dd'
  on-surface: '#1e1b19'
  on-surface-variant: '#56423c'
  inverse-surface: '#33302d'
  inverse-on-surface: '#f7efeb'
  outline: '#89726b'
  outline-variant: '#dcc1b8'
  surface-tint: '#9d4324'
  primary: '#9a4021'
  on-primary: '#ffffff'
  primary-container: '#b95837'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb59d'
  secondary: '#635d57'
  on-secondary: '#ffffff'
  secondary-container: '#e7ded6'
  on-secondary-container: '#67625b'
  tertiary: '#615b53'
  on-tertiary: '#ffffff'
  tertiary-container: '#7a746b'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd0'
  primary-fixed-dim: '#ffb59d'
  on-primary-fixed: '#390b00'
  on-primary-fixed-variant: '#7e2c0e'
  secondary-fixed: '#eae1d9'
  secondary-fixed-dim: '#cdc5bd'
  on-secondary-fixed: '#1f1b16'
  on-secondary-fixed-variant: '#4b4640'
  tertiary-fixed: '#eae1d7'
  tertiary-fixed-dim: '#cec5bb'
  on-tertiary-fixed: '#1f1b15'
  on-tertiary-fixed-variant: '#4b463e'
  background: '#fff8f5'
  on-background: '#1e1b19'
  surface-variant: '#e9e1dd'
typography:
  display-title:
    fontFamily: Lora
    fontSize: 2.25rem
    fontWeight: '400'
    lineHeight: 2.75rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: DM Sans
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: DM Sans
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: DM Sans
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: 0em
  metric-xl:
    fontFamily: DM Sans
    fontSize: 2.5rem
    fontWeight: '700'
    lineHeight: 2.75rem
    letterSpacing: -0.03em
  metric-md:
    fontFamily: DM Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2rem
    letterSpacing: -0.02em
  body-lg:
    fontFamily: DM Sans
    fontSize: 1.125rem
    fontWeight: '400'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  body-md:
    fontFamily: DM Sans
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: 1.5rem
    letterSpacing: 0em
  body-sm:
    fontFamily: DM Sans
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
    letterSpacing: 0.01em
  label-md:
    fontFamily: DM Sans
    fontSize: 0.8125rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.04em
  label-sm:
    fontFamily: DM Sans
    fontSize: 0.6875rem
    fontWeight: '600'
    lineHeight: 0.875rem
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  space-2xs: 0.25rem
  space-xs: 0.5rem
  space-sm: 0.75rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  container-max-width: 900px
  card-padding: 1.5rem
---

## Brand & Style

This design system delivers an internal executive briefing experience centered on clarity, poise, and literary restraint. Rooted in warm tactile paper tones and deliberate editorial typography, it replaces generic enterprise SaaS clutter with an unhurried, high-signal reading environment.

### Design Movement
Warm Editorial Minimalism:
- Grounded, physical feel derived from natural paper substrates and warm charcoal typography.
- Strictly functional layout prioritizing rapid scanning, quiet hierarchy, and unornamented content.
- Clean typographic contrast between expressive editorial display text and systematic, geometric data presentation.
- Zero gratuitous decoration: no heavy skeuomorphic drops, no glowing synthetic gradients, and no illustrative emojis in headers, pills, or badges.

## Colors

The color palette is deliberately calibrated to evoke natural paper stocks, muted inks, and restrained terracotta signaling. 

### Palette Architecture
- **Canvas / Background**: `#F7F4EE` — Soft warm parchment canvas for the global page backdrop.
- **Surface / Cards**: `#FDFBF7` — Elevated off-white paper substrate for cards, modules, and inputs.
- **Primary Ink**: `#1A1715` — Deep carbon charcoal for primary headlines, critical metric values, and primary body copy.
- **Secondary Ink**: `#4A453F` — Medium-warm charcoal for section subheadings, secondary descriptors, and metric labels.
- **Tertiary Ink / Muted**: `#8C857C` — Soft gray-taupe for metadata timestamps, field hints, and dormant borders.
- **Primary Accent (Terracotta)**: `#C96442` — Signature clay accent used for primary interactive states, key focal badges, and curated highlights.
- **Functional Semantics**:
  - Positive / Success: `#3D8C5C` (Restrained forest green)
  - Negative / Error: `#C0392B` (Muted carmine red)
  - Warning / Attention: `#D97706` (Warm amber)
- **Structural Hairlines**: `rgba(90, 75, 60, 0.08)` — Delicate organic borders preserving clean divisions without optical weight.

## Typography

The type system is deliberately balanced between high-utility clarity and editorial nuance:
- **Display Page Title Only**: Lora Italic is reserved exclusively for the primary masthead title, providing a dignified, literary point of arrival.
- **Workhorse Typeface**: DM Sans drives every other UI element, including metric cards, section headers, badges, tables, checklist items, and body copy.
- **Numerical Rhythm**: Metrics and numeric readouts utilize tabular lining figures (`font-variant-numeric: tabular-nums`) to ensure strict vertical alignment across comparative rows.
- **Casing & Weight**: Sub-headers and badges utilize clean uppercase labels with subtle letter spacing to create rhythmic scan points.

## Layout & Spacing

The layout is built around a focused, centered briefing column configured to prevent optical fatigue and excessive eye travel.

### Layout Principles
- **Container Structure**: Strict centered single-column layout with an absolute maximum width of `900px`.
- **Canvas Margins**:
  - Desktop (≥1024px): Centered `900px` container with auto horizontal margins.
  - Tablet (768px – 1023px): `2rem` inline padding.
  - Mobile (<768px): `1rem` inline padding; cards collapse into single-column vertical stacks.
- **Grid Architecture**: Internal cards leverage an adaptable 2 or 3-column subgrid with `1rem` to `1.5rem` gutters for KPIs and metric clusters.
- **Vertical Cadence**: Generous section spacing (`3rem`) partitions distinct analytical segments, while card interiors adhere to strict `1.5rem` breathing space.

## Elevation & Depth

This system intentionally departs from synthetic elevated drop shadows, employing physical layering and hairline definition:
- **Surface Contrast**: Elevation is established purely through color separation—floating `#FDFBF7` paper panels over the ambient `#F7F4EE` canvas.
- **Hairline Boundaries**: Every card, input, and boundary uses a precise `1px` border defined by `rgba(90, 75, 60, 0.08)`.
- **Subtle Surface Lift (Hover Only)**: Interactive cards feature an understated micro-elevation on hover (`box-shadow: 0 4px 12px rgba(26, 23, 21, 0.03)`), maintaining the sensation of handling physical paper stock.

## Shapes

The geometry unites soft architectural framing with organic editorial pills:
- **Card Panels**: Rigorously bounded at `16px` (`1rem`) border radius, striking a balance between structure and approachable warmth.
- **Interactive Buttons & Chips**: Fully circular pill caps (`980px` or `9999px`), ensuring tactile touch targets and clear distinction from rectangular reading cards.
- **Form Controls & Checks**: Radii scaled down to `4px` – `8px` for focused, precise interactions.

## Components

### Buttons
- **Primary**: Full pill radius (`980px`), solid `#C96442` terracotta fill, `#FDFBF7` paper-white text, padding `0.625rem 1.25rem`. Active state scales gently (`0.98`).
- **Secondary / Outline**: Pill radius, transparent fill, `1px solid rgba(90, 75, 60, 0.18)`, `#1A1715` text. Hover background shifts to `rgba(90, 75, 60, 0.04)`.
- **Ghost / Text**: Pill radius, no border, `#4A453F` text, hover background `rgba(90, 75, 60, 0.05)`.

### Cards & Modules
- **Background**: `#FDFBF7`.
- **Corner Radius**: `16px`.
- **Border**: `1px solid rgba(90, 75, 60, 0.08)`.
- **Padding**: `1.5rem`.
- **Divider Rule**: Internal card separations use a hairline line: `border-bottom: 1px solid rgba(90, 75, 60, 0.06)`.

### Metrics & KPI Blocks
- **Value**: Displayed in `DM Sans` 700 weight, `#1A1715`.
- **Label**: Positioned above or below the value in `DM Sans` 600, uppercase, `0.75rem`, `#8C857C`.
- **Trend Indicators**: Minimalist inline badges with colored arrow glyphs (e.g., `+12.4%`) using `#3D8C5C` or `#C0392B` with zero background noise.

### Status Badges & Chips
- **Geometry**: Pill radius (`980px`), padding `0.25rem 0.75rem`.
- **Typographic Style**: `DM Sans`, 600 weight, `0.6875rem`, uppercase, tracking `+0.05em`.
- **Tone Palette**:
  - Standard: Background `rgba(90, 75, 60, 0.06)`, text `#4A453F`.
  - Terracotta: Background `rgba(201, 100, 66, 0.1)`, text `#C96442`.
  - Positive: Background `rgba(61, 140, 92, 0.1)`, text `#3D8C5C`.
  - Alert: Background `rgba(192, 57, 43, 0.1)`, text `#C0392B`.
  - Warning: Background `rgba(217, 119, 6, 0.1)`, text `#D97706`.

### Checklists & Task Items
- **Container**: Minimalist horizontal flex strip with `0.75rem` vertical spacing.
- **Control**: Square checkbox with `4px` border radius, `1.5px solid rgba(90, 75, 60, 0.3)`. Checked state fills with `#C96442` and a crisp white SVG check icon.
- **Label**: `DM Sans` 400, `#1A1715`. Checked items shift to `#8C857C` with a clean strike-through.

### Input Fields
- **Background**: Transparent or `#FDFBF7`.
- **Border**: `1px solid rgba(90, 75, 60, 0.15)`, radius `8px`.
- **Focus**: Border color transitions to `#C96442` with an ambient glow (`box-shadow: 0 0 0 3px rgba(201, 100, 66, 0.12)`).