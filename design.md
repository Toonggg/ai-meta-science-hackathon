# Episteme UI — Design Improvements

> Apple-design sensibility: reduce clutter, let the science breathe, honour the existing theme system.

---

## 1 · Header & Navigation

### 1.1 — Header is too busy; competing for attention
The header packs brand + 3-step nav + Search toggle + Source badge + AI toggle + AI badge + theme picker all in one row. On a 13" laptop it wraps, and everything looks equally important.

**Suggestion:** Separate the header into two visual layers:
- **Top bar:** Brand on the left, a compact utility strip on the right (theme picker, a single unified "⚙ Settings" icon that opens the model + sources dialog).
- **Below the brand:** The three-step workflow tabs, centred, with generous whitespace. These are the hero of the tool — they should feel like a progress indicator, not buttons crammed between logos.

### 1.2 — Search / AI toggles feel like afterthoughts
Two bare checkboxes with one-word labels ("Search", "AI") next to two status badges creates a cluster of six small, misaligned elements. A researcher has to squint.

**Suggestion:** Replace with a single "Capabilities" popover (or a row of two pill-toggle switches with inline status), e.g.:

```
  [🔍 Search · 7/9 up]   [🤖 Claude · Opus 5.5]
```

Each pill is both the toggle and the badge. Tapping opens the detail dialog. One element per capability instead of three.

### 1.3 — Theme picker has no visual cue
It's a plain `<select>` that looks like a form input, not a preference control.

**Suggestion:** Replace with a small circle/swatch icon that opens a minimal popover showing five colour swatches. Hovering a swatch previews instantly; clicking commits. Much less visual weight than a dropdown.

### 1.4 — Step numbers in nav pills could be more Apple
The numbered circles inside buttons are a good idea but look slightly cramped. The active state colour-fills the number but the rest of the pill is transparent.

**Suggestion:** Use a segmented-control style (like iOS): a continuous pill with three segments, a sliding highlight behind the active one (CSS transition on `transform: translateX`). The numbers can stay, but each segment gets equal width and the highlight animates smoothly.

---

## 2 · Layout & Spacing

### 2.1 — `max-width: 1280px` is tight for a three-column feeling
On ultrawide monitors the UI feels like a narrow column. On 13" screens, the 380px sidebar compresses the main column.

**Suggestion:**
- Increase `max-width` to 1400px (or `min(1400px, 94vw)`).
- Let the sidebar respond: at `<1200px` collapse it into a slide-out drawer triggered by a tab/icon, rather than stacking vertically where it pushes the timeline off-screen.

### 2.2 — Padding is inconsistent
`main` has `24px` padding; cards have `14px 16px`. The "add form" card and the timeline cards have different horizontal rhythms.

**Suggestion:** Standardise on a 4px base grid. Main padding: `32px`. Card padding: `16px 20px`. All `gap` values multiples of `8px`. This makes everything feel intentional.

### 2.3 — The "add form" doesn't feel like the primary action
It's a card among cards. For the core action of the diary tab, it deserves hero treatment.

**Suggestion:**
- Make it a floating bar at the top of the main column, slightly elevated (`box-shadow` + subtle border), always visible, with the input stretching to fill. Think of Apple's Spotlight bar: minimal, centred, inviting.
- Collapse the "expanded" state to an inline detail disclosure rather than a block that pushes the timeline down.

### 2.4 — No visual grouping between the add form, prompts, confirms, and timeline
These four elements stack vertically with no separator logic. Prompts and confirms are ephemeral; the timeline is permanent. They feel like one pile.

**Suggestion:** Give ephemeral prompts/confirms a subtle indented treatment or a thin top-border accent, and add a visual "— Timeline —" marker (or just 16px extra margin) before the timeline begins.

---

## 3 · Timeline

### 3.1 — Timeline line (`::before`) and dots are a bit retro
The 2px vertical line with absolute-positioned circles works, but the layout breaks subtly when cards have long content (the line doesn't extend to bottom, dots misalign on small screens).

**Suggestion:**
- Use a CSS `border-left` on a wrapper div instead of `::before` pseudo-element — easier to contain and debug.
- Make dots 24px instead of 28px for a lighter feel; use a subtle ring instead of a solid fill for non-active types.

### 3.2 — Event cards lack a clear information hierarchy
Title, chip, meta, body all fight for attention. The chip says "Plan" and the border-left says "Plan" (same colour) — redundant signalling.

**Suggestion:**
- Remove the left border from cards (the dot already signals the type).
- Move the chip from inside the card to be part of the dot label, or make it a subtle superscript on the dot.
- Give the title more visual weight (16px semibold) and the meta less (11px, lighter opacity).

### 3.3 — Delete button (×) hover reveal is hard to discover
`opacity: 0` on a button that only appears on hover is invisible to touch users and hard to find for keyboard users.

**Suggestion:** Always show the delete button but at low opacity (`0.3`); brighten on hover. Or move delete into the expanded body section as a text link ("Remove this entry").

### 3.4 — The "All / Decisions / Raw capture" view picker is lost
It's a small set of tab-buttons in the `tl-head` row, easily missed.

**Suggestion:** Make it a full-width segmented control directly above the timeline, with a short description of each view underneath (tooltip or subtitle). This is a critical filter — it shouldn't hide.

---

## 4 · Sidebar (Diary Tab)

### 4.1 — "Reviewer: ask the log" card is powerful but under-presented
It's the tool's killer feature (the success criterion from the brief). It sits in a sidebar that many users won't scroll to.

**Suggestion:**
- Promote "Ask the log" to a floating action: a persistent "Ask" button at the bottom-right that opens a chat-like panel (Apple's sheet pattern). This makes the reviewer Q&A feel first-class.
- Keep the sidebar card for export and capture instructions.

### 4.2 — Export and Capture cards are admin/ops, not science
They compete visually with "Ask the log" for attention.

**Suggestion:** Collapse them under a single "⚙ Utilities" disclosure or move them to a footer area. The researcher doesn't need to see `curl` snippets while reviewing a diary.

### 4.3 — "Reload demo session" and "Start empty diary" are dangerous near each other
Two ghost buttons side by side, one benign and one destructive.

**Suggestion:** Move "Start empty diary" to a ⋯ menu or put it behind a destructive confirmation modal with a text-input check (like GitHub's "type the repo name to confirm"). The current `confirm()` dialog is easy to click through.

---

## 5 · Task 1 — Question Vetting

### 5.1 — The pipeline cards ("1 · Local rules", "2 · Literature search", "3 · AI refinement") are a grid of equal-weight boxes
They don't communicate flow.

**Suggestion:** Connect them with arrows or a horizontal progress bar that fills as each stage completes. Use subtle animation (a shimmer or pulse on the "running" stage). Each card could collapse into a compact chip once done, making room for the results.

### 5.2 — The verdict banner is great but the text is small relative to the word
`font-size: 26px` for the verdict word but the explanation beside it is default size. The layout is `flex` with `gap: 16px` but the explanation wraps without visual separation.

**Suggestion:**
- Make the verdict word larger (32–36px) and the explanation a distinct block below it (not beside it). Think of a macOS alert: big icon/word on the left, explanation paragraph on the right, clearly separated.
- Add a 1px divider or use a two-row layout within the verdict box.

### 5.3 — The 2×2 card grid ("Ambiguous terms", "Assumptions", "Evidence needed", "Already answered") is dense
All four cards have the same visual weight, even when one has 8 items and another has zero.

**Suggestion:**
- Size cards to content (use `auto-fit` with `min-content` instead of fixed `minmax(340px, 1fr)`).
- Give empty cards a muted treatment (just the title + "None found" in grey, no full card chrome).
- Consider a vertical stack on narrow viewports rather than a grid, since the content is sequential.

### 5.4 — Example question buttons feel disconnected
They're small pill-buttons below the textarea with no label.

**Suggestion:** Add a "Try an example:" label prefix, and style them as suggestion chips (like Google Search suggestions — lightly outlined, clearly interactive).

---

## 6 · Task 3 — Claim Map

### 6.1 — The claims table is too wide for the data
Five columns (`Claim`, `Evidence`, `Diary`, `Status`, `Why`) at 100% width makes cells sparse on wide screens and cramped on narrow ones.

**Suggestion:**
- Use a card-per-claim layout instead of a table on narrow screens (`<900px`). Each card shows claim text, status pill, evidence list, diary links, and issues as stacked blocks.
- On wide screens, keep the table but use `table-layout: fixed` with controlled proportions, and add alternating row tinting for scanability.

### 6.2 — Summary stat boxes are unordered
The four summary stats (`supported`, `weak`, `overclaimed`, `unsupported`) are flex-wrapped with no implied order or proportion.

**Suggestion:** Arrange them in a single horizontal bar where width is proportional to count (like a stacked bar chart), with the colour coding. This gives an instant visual feel for the balance. Below it, keep the numeric labels.

### 6.3 — "Load demo paper" button is buried
It's a ghost button with a text cue beside it — easy to miss.

**Suggestion:** Make it a prominent outlined button with an icon (📄), or show the demo paper as a dismissible example pre-loaded in the textarea (greyed out, cleared on focus).

---

## 7 · Typography & Micro-Interactions

### 7.1 — Font size is 14px throughout; no scale
Everything is 14px except a few `small` and `h2` elements. There's no typographic hierarchy to guide the eye.

**Suggestion:** Establish a scale: `11px` (captions) → `13px` (body small) → `14px` (body) → `16px` (section titles) → `20px` (page titles) → `28px` (hero verdicts). Use `font-weight` variation (400, 500, 600) rather than size alone.

### 7.2 — No transitions on interactive elements
Buttons and cards snap between states. The `.flash` animation is the only motion.

**Suggestion:** Add subtle transitions:
- Button hover: `background-color 0.15s ease`.
- Card expand/collapse: `max-height` transition with `overflow: hidden` (or use `<details>` with the new CSS `::details-content` animation).
- Tab switching: a crossfade (`opacity` transition on the entering section).
- Toast: slide-up + fade-in instead of instant appear.

### 7.3 — Code snippets (`<pre>`, `<code>`) are harsh
The `pre` blocks use `11px` mono and a stark border. They feel like a different app.

**Suggestion:** Use the same `--panel` / `--bg` pairing but with a softer border (`0.5px` or `border-color` at 50% opacity), slightly larger font (`12px`), and rounded corners matching the card radius.

---

## 8 · Dialogs

### 8.1 — Settings dialog has two concerns in one dialog
"Model" and "Search sources" are tabs in one dialog, but they're saved together. This is confusing if you only want to change the model.

**Suggestion:** Either:
- Save each pane independently (so changing the model doesn't require scrolling past sources), or
- Split into two dialogs accessible from separate UI entry points.

### 8.2 — Source status dialog (`dialog.wide`) is an information dump
A 980px-wide table with 7 columns is overwhelming for a tool that should be about science.

**Suggestion:**
- Default to a compact card view: each source as a small card with status dot, name, and a sparkline-style heartbeat bar. A "Details" toggle expands to the full table for power users.
- The key insight (N of M sources up, next check in X min) should be prominent at the top; the per-source breakdown is secondary.

### 8.3 — `dialog::backdrop` is opaque
`rgba(0,0,0,.6)` is heavy. Apple uses lighter backdrops that let you see the content behind.

**Suggestion:** `rgba(0,0,0,.3)` for dark themes, `rgba(0,0,0,.15)` for light. Add a `backdrop-filter: blur(8px)` for a frosted-glass effect (works in all modern browsers).

---

## 9 · Responsiveness

### 9.1 — Only one breakpoint (`980px`)
The UI goes from two-column to one-column with nothing in between. On tablets (768–980px) everything is stacked vertically and the header wraps awkwardly.

**Suggestion:** Add intermediate breakpoints:
- `>1200px`: full layout as now.
- `980–1200px`: narrower sidebar (280px) or sidebar as a collapsible panel.
- `768–980px`: single column, sidebar items become cards in a horizontal scroll row.
- `<768px`: single column, full-stack. Tiers grid becomes a vertical stack.

### 9.2 — No `touch-action` or mobile-friendly tap targets
Buttons are `8px 14px` padding — fine for desktop but too small for touch. The delete button (×) is tiny.

**Suggestion:** Ensure all tap targets are at least `44×44px` on mobile (Apple's Human Interface Guideline). Use `@media (pointer: coarse)` to increase padding on touch devices.

---

## 10 · Accessibility

### 10.1 — No `aria-label` on icon-only buttons
The delete button (×) has no accessible name. The theme picker has an `aria-label`, which is good — extend that to all interactive elements.

### 10.2 — Focus management on tab switch
Switching tabs with the nav buttons doesn't move focus to the new content. A keyboard user has to tab through the hidden sections.

**Suggestion:** After `showTab()`, focus the first focusable element in the revealed section (the `h2`, or the first input).

### 10.3 — Confirmation prompts and pivot cards are not announced
Screen readers won't know new content appeared. Use `role="alert"` or `aria-live="polite"` on `#prompts` and `#confirms`.

### 10.4 — Timeline entries rely on colour alone for type
The coloured dot and chip are the only type indicators. Users with colour vision deficiencies can't distinguish Plan from Run.

**Suggestion:** Add a small icon or letter inside the dot (P, R, S, !, ★, A, ?) in addition to the colour. The current `e.step` number in the dot isn't the type.

---

## 11 · Performance & Architecture

### 11.1 — innerHTML-heavy rendering
Every update rebuilds the entire timeline/claims/question output via innerHTML string concatenation. This causes:
- Loss of scroll position.
- Loss of user selection.
- Flicker.

**Suggestion (non-urgent):** For the timeline specifically, diff against the current DOM: only insert new events, remove deleted ones, and update changed ones. The current `open` state preservation hack (`$$(".ev.open").map(…)`) would become unnecessary.

### 11.2 — Polling every 4 seconds on the diary
`setInterval(…, 4000)` fires even when the tab is inactive or the diary hasn't changed. On a long session this adds up.

**Suggestion:** Use `requestIdleCallback` or `document.visibilityState` to skip polls when the tab is hidden. Consider SSE (`EventSource`) from the server to push changes instead of polling.

---

## 12 · Visual Polish (Quick Wins)

| What | Now | Suggested |
|---|---|---|
| Card border-radius | `10px` | `12px` (matches macOS window corners) |
| Card shadow (dark) | `0 1px 2px + 0 4px 14px` | Add a subtle inner glow: `inset 0 1px 0 rgba(255,255,255,.03)` for depth |
| Primary button | Flat accent fill | Subtle gradient: `linear-gradient(…)` from accent to accent-dark, or just `filter: brightness(1.05)` on hover |
| Input focus ring | `outline: 2px solid accent@40%` | Use `outline-offset: 2px` for a floating ring effect (Apple style) |
| Toast | Bottom-centre, instant appear | Bottom-centre, slide-up with `transform: translateY(20px)` → `translateY(0)` + opacity fade |
| Empty states | Grey text centred | Add a subtle illustration or icon + actionable CTA button |
| Scrollbar | Browser default | Custom thin scrollbar using `::-webkit-scrollbar` (4px, accent colour) for dark themes |

---

## Summary — Priority

1. **Header simplification** (§1) — biggest first-impression win.
2. **"Ask the log" promotion** (§4.1) — surfaces the killer feature.
3. **Spacing & grid rhythm** (§2) — makes everything feel cohesive.
4. **Transitions & polish** (§7.2, §12) — moves from "prototype" to "product".
5. **Responsive breakpoints** (§9) — usability on real hardware.
6. **Accessibility** (§10) — correctness.
7. **Rendering architecture** (§11) — long-term scalability.
