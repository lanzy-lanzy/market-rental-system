# Emerald Glass — UI Design System

Every template in this project uses one visual language: **liquid glass** surfaces
(translucent, blurred, rim-lit) layered over a **neumorphic** warm ivory canvas,
tinted with **municipal emerald** and **Philippine gold**.

All classes below are defined in `static/css/input.css` and already compiled into
`static/css/output.css`. Use them instead of raw Tailwind colour utilities.

---

## 1. Palette

| Token | Class / variable | Use |
| --- | --- | --- |
| Emerald (primary) | `emerald-50 … emerald-950` | Brand, primary actions, active nav |
| Gold (accent) | `gold-50 … gold-900`, `#FCD116` | Highlights, totals, primary CTA on dark |
| Ivory (canvas) | `ivory-50 … ivory-400`, `bg-surface` | Page background |
| Ink (text) | `text-ink`, `text-ink-soft`, `text-ink-muted` | Headings / body / secondary |
| Semantic | `text-emerald-700`, `text-red-600`, `text-amber-600`, `text-sky-600` | Status text |

All ink/semantic pairs clear WCAG AA (≥ 4.5:1) against the glass surfaces —
verified with a contrast script whenever the palette changes.

**Never** use `bg-slate-50`, `text-slate-600`, `border-slate-200`, `bg-gray-100`,
`text-gray-700` etc. in new markup. Replace with the tokens above.

---

## 2. Surfaces

| Class | Description |
| --- | --- |
| `.panel` | Liquid-glass card: translucent white, 22px blur, white rim, soft emerald shadow, `rounded-2xl` |
| `.panel-flat` | Lighter glass, no heavy shadow |
| `.panel-header` | Header strip inside a panel (gradient + hairline divider) |
| `.panel-body` | Padded body of a panel |
| `.panel-title` / `.panel-subtitle` | Header title / subtitle text |
| `.glass` / `.glass-strong` / `.glass-deep` | Raw glass surfaces (deep = dark emerald glass) |
| `.glass-dark` / `.glass-dark-strong` | **Dark** frosted glass — required for cards floating over photography or dark imagery, where white type would otherwise wash out |
| `.section-title` | Small uppercase emerald label with gold underline |
| `.divider-gold` | Short gold rule (3px) |
| `.shimmer-line` | Full-width gold gradient hairline |

> **Contrast rule:** white / `text-emerald-50` type may only sit on `.glass-deep`,
> `.glass-dark`, `.glass-dark-strong` or a solid emerald gradient. Never on
> `.panel` / `.glass` / `.glass-strong` — those are light surfaces and take
> `text-ink` / `text-ink-soft` / `text-ink-muted`.

Page background (aurora mesh) is already applied to `<body>` — do not add a solid
background to the content wrapper.

---

## 3. Buttons

```
.btn                        base (inline-flex, rounded, transitions)
.btn.btn-primary            emerald gradient, white text
.btn.btn-gold               gold gradient, deep green text
.btn.btn-ghost              frosted glass, neumorphic shadow
.btn.btn-outline            transparent, emerald border
.btn.btn-danger             red gradient
.btn.btn-sm / .btn.btn-lg   size modifiers
.btn-icon                   36px square glass icon button
.btn-icon.btn-icon-danger   red on hover
.btn-icon.btn-icon-gold     gold on hover
.btn-on-dark        ghost button for dark surfaces (photo heroes, deep emerald)
```

Never use `rounded-full` pill buttons for primary CTAs — the design language is
rounded-rectangular (`rounded-xl` / `rounded-2xl`).

---

## 4. Forms

```
.field             inset neumorphic input/select/textarea well
.field-label       label text (bold, ink-soft)
.field-hint        helper text
.field-error       error text
.form-grid         responsive 2-column grid
.form-section      full-width uppercase section divider inside a form
```

Django widgets already render with the `.field` class (see `core/forms.py`
`TW_INPUT` / `TW_SELECT` / `TW_TEXTAREA`). Add layout utilities only:

```html
{{ form.first_name }}                    → already styled
{{ form.street }}                        → already styled
<select class="field w-full">            → add .field + .w-full
<input class="field w-full">               → add .field + .w-full
```

Use `text-ink` for the value colour when overriding, never `text-slate-900`.

---

## 5. Tables

```html
<div class="table-wrap">
  <div class="overflow-x-auto">
    <table class="table min-w-[900px]">
      <thead><tr><th>…</th></tr></thead>
      <tbody><tr><td>…</td></tr></tbody>
      <tfoot><tr><td>…</td></tr></tfoot>
    </table>
  </div>
</div>
```

- `thead th` — uppercase, emerald, gradient tint (automatic)
- `tbody tr:hover` — soft emerald tint (automatic)
- `tfoot` — gold-tinted totals row (automatic)
- Right-aligned numeric cells: add `class="num"`.

---

## 6. Stats, badges, chips, alerts

```
.stat-card              glass stat tile (hover lifts)
.stat-label / .stat-value / .stat-meta
.stat-icon              neumorphic icon chip (+ .stat-icon-gold / -red / -blue)

.badge.badge-success / -muted / -warning / -danger / -info / -gold
.badge-dot             inner dot (use inside a badge)

.chip / .chip-emerald / .chip-gold

.alert / .alert-success / -error / -warning / -info / -neutral
```

---

## 7. Navigation & page furniture

```
.nav-link            sidebar link (deep emerald glass sidebar)
.nav-link.is-active      gold pill
.nav-link.is-muted-active translucent emerald pill
.nav-sub-link        nested sub link (+ .is-active)
.nav-section         uppercase group label

.page-head / .page-title / .page-sub
.filter-bar          frosted filter row
.kpi-strip / .kpi-item / .kpi-value / .kpi-label
.avatar / .avatar-gold
.progress / .progress-bar / .progress-bar-gold
.empty-state / .empty-icon
.mono                 monospace numerals/ids
.link-emerald         emerald text link
```

---

## 8. Official documents (print / PDF previews)

```
.doc / .doc-head / .doc-title / .doc-rule / .doc-table / .sig-line
.receipt / .receipt-band / .receipt-total
```

Black-on-white layouts with emerald headings and a gold rule. Use these in
`print_*.html` and `reports/pdf/*.html` — never glass or neumorphism on paper.

---

## 9. Rules

1. **Never remove Django logic.** Keep `{% url %}`, `{% if %}`, `{% for %}`,
   `{% csrf_token %}`, `hx-*` attributes, `{{ form.* }}` and every context variable
   exactly as-is. Only classes, wrappers and decorative markup may change.
2. Keep every SVG icon.
3. Prefer adding a wrapper `<div class="panel">` around a card instead of
   restyling every child.
4. Rounded corners: `rounded-xl` (small), `rounded-2xl` (cards), `rounded-full`
   only for avatars/dots/pills.
5. Print templates (`print_*.html`, `reports/pdf/*`) must stay **black on white**:
   no glass, no blur, no neumorphic shadows. Only swap the palette to
   emerald/gold headings and keep body text dark.
6. Use `text-ink` / `text-ink-soft` / `text-ink-muted` for text; emerald for
   brand emphasis; gold for accents and totals.
7. Tabular numbers for money: `class="num"` on the cell.
8. The aurora mesh on `<body>` is the page background — never add a solid page
   background or a full-width white wrapper; let each card be its own panel.
