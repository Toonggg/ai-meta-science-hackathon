# Episteme — Bug Report

Bugs and issues found during a full front-end code review.

---

## 🔴 High Severity

### B1 — XSS via `raw_ids` in timeline event cards
**File:** [app.js#L297](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L297)

The `raw_ids` array is interpolated into a `data-raw` attribute using `esc()`, but the join delimiter is `,`. If a malicious raw ID contains a comma, the split logic in the click handler (`rawBtn.dataset.raw.split(",")`) will produce unexpected IDs that are then passed unvalidated to `api("/api/raw?ids=…")`. While the server filters by known IDs, the URL is constructed with `encodeURIComponent` of attacker-controlled input without length limits. The same pattern appears for `data-ref` and `data-del`.

**Impact:** Low in practice (localhost only, token-protected), but should be tightened.

**Fix:** Validate that each ID matches `/^[ER]\d+$/` before using it in API calls.

---

### B2 — `showPane()` selector is too broad — clashes across dialogs
**File:** [app.js#L114](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L114)

```js
$$(".dlg-tabs button").forEach(b => b.classList.toggle("active", b.dataset.pane === name));
$$("#settings .pane").forEach(p => (p.hidden = p.dataset.pane !== name));
```

The first line selects **all** `.dlg-tabs button` on the page, not just those inside `#settings`. The diary tab also has `.dlg-tabs` buttons (the "All / Decisions / Raw capture" view picker). When `openSettings("model")` is called, **every** `.dlg-tabs button` whose `dataset.pane` doesn't match "model" loses its `active` class — including the diary view picker, which doesn't use `data-pane` at all. This means the diary view picker's active state is silently cleared when you open Settings.

**Fix:** Scope the selector: `$$("#settings .dlg-tabs button")`.

---

### B3 — Event polling replaces timeline HTML even when nothing changed (race condition)
**File:** [app.js#L716-L727](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L716-L727)

The polling interval serializes the entire events array to JSON (`JSON.stringify(snap.events)`) and compares strings to detect changes. This is O(n) on every tick, and can cause:
- **Lost user state:** If the user is mid-type in the "add form" or mid-scroll, and a new event arrives from a capture hook, the timeline is rebuilt, discarding scroll position. The `open` state is preserved via a re-scan, but scroll position is not.
- **Jank on large diaries:** Stringifying 200+ events every 4 seconds on a slow machine.

**Fix:** Compare only a server-provided version counter or hash, and use DOM diffing (insert/remove individual elements) rather than full innerHTML replacement.

---

## 🟡 Medium Severity

### B4 — `form.addEventListener("submit")` on the add-form can double-fire
**File:** [app.js#L412-L427](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L412-L427)

The submit handler `await`s `api("/api/events", ev)`, then `await loadDiary()`, then calls `flash()`. During this time, the button is not disabled — a fast double-click (or holding Enter) will fire two submissions. The `busy()` helper disables the button, but the add-form submit handler does **not** use `busy()`.

**Fix:** Disable the submit button immediately on submit, re-enable after the handler completes, or use a `submitting` guard flag.

---

### B5 — `fillProvider()` leaks display style changes
**File:** [app.js#L129](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L129)

```js
$$('.pane[data-pane="model"] label').forEach(l => (l.style.display = p.id === "none" && l.querySelector("input") ? "none" : ""));
```

When the provider is "none", the label elements are hidden with inline `style.display = "none"`. When switching back, the style is set to `""` (empty string). This works in Chrome but is fragile: if the CSS class specifies `display: grid` (which it does — `dialog label { display: grid }`), setting `style.display = ""` relies on cascade fallback. If any inline style was set on the element before, it may not reset correctly.

**Fix:** Use `l.style.removeProperty("display")` instead of `= ""`, or toggle a CSS class.

---

### B6 — `#q-input` Enter handler fires even when textarea is multi-line
**File:** [app.js#L568](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L568)

```js
$("#q-input").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#q-run").click(); } });
```

The question textarea is `rows="2"`, implying multi-line input. But pressing Enter submits instead of adding a newline (Shift+Enter is required for a newline). This is undiscoverable and inconsistent with the claims textarea (`#c-input`, `rows="10"`) which has no such handler and allows free Enter.

**Fix:** Either remove the Enter-to-submit shortcut (a textarea should accept Enter), or add a placeholder hint like "(Enter to submit, Shift+Enter for newline)".

---

### B7 — `toast._t` property on a function is a side-effect hack
**File:** [app.js#L23-L27](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L23-L27)

```js
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), 3200);
}
```

Storing the timer ID as a property on the function object (`toast._t`) works but is unconventional and will confuse future maintainers. It's also not cleared if `toast` is reassigned.

**Fix:** Use a module-level variable (`let _toastTimer`).

---

### B8 — `loadConfirms` races with user interaction
**File:** [app.js#L478-L485](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L478-L485)

`loadConfirms()` is called from the 4-second polling loop. It compares a key string to decide whether to re-render. But if the user has typed into a confirm card's input field, and the key string hasn't changed (no new confirms from the server), it skips rendering — which is correct. However, if a **different** confirm card resolves (changing the key), it re-renders **all** confirm cards, wiping out text the user was typing in another card.

**Fix:** Preserve per-card input values across re-renders, or only remove/add the specific cards that changed.

---

### B9 — `clearTimeout(qPoll)` should be `qPoll = null` after clearing
**File:** [app.js#L588-L605](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L588-L605)

After `clearTimeout(qPoll)`, the `qPoll` variable still holds the old timer ID. If the next `setTimeout` returns the same ID (unlikely but possible in theory), a later `clearTimeout` might clear the wrong timer.

**Fix:** Set `qPoll = null` after `clearTimeout(qPoll)`.

---

### B10 — `stChecking` Set is never bounded
**File:** [app.js#L191](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L191)

If the "Check" button is clicked rapidly, source IDs accumulate in `stChecking`. The `finally` block in the per-source check handler deletes the ID, but if the request throws before reaching `finally` (e.g., a network error in `api()`), `stChecking` could grow without cleanup, showing permanent "checking…" spinners.

**Fix:** Wrap the check in a try/finally that always removes from `stChecking`.

**Status:** Partially mitigated — the per-source handler does have try/finally, but the "Check all" handler (`#st-check-all`) adds IDs in bulk before the request and only clears them in `finally`. If the request throws before `finally`, the individual source state isn't cleaned.

---

## 🟢 Low Severity / Code Quality

### B11 — `$$` helper returns a spread array, not a live NodeList
**File:** [app.js#L5](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L5)

```js
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
```

This is fine and intentional (avoids live NodeList mutations), but the naming `$$` conventionally implies jQuery-like live results. Minor, but worth a comment.

---

### B12 — `NEEDS_TOKEN` on the server only checks POST paths, but no CSRF token on the form
**Files:** [server.py#L47](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/server.py#L47), [app.js#L14-L16](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L14-L16)

The token is embedded in a `<meta>` tag and sent as `x-episteme-token`. This is good. But `POST /api/events` (the main event ingestion endpoint) does **not** require the token (it's designed for external tools like `curl`). If a malicious page on the same machine can discover the port (e.g., by scanning localhost ports), it could inject fake events without the token.

**Mitigation:** The server checks `same_origin()` (the `Origin` header), which blocks cross-origin POSTs from other web pages. This is adequate for localhost, but note that non-browser clients (scripts, other apps) can trivially forge the `Origin` header. Since this is an MVP on `127.0.0.1`, this is acceptable.

---

### B13 — `syncType()` called before the form element exists in some timing scenarios
**File:** [app.js#L408-L411](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L408-L411)

The `const form = $("#add-form")` and subsequent `syncType()` call happen at top-level module execution. The `<script>` tag is at the end of `<body>`, so the DOM is ready. However, if the script were ever loaded with `defer` or `async`, this would break.

**Fix:** No immediate action needed, but wrapping in a `DOMContentLoaded` listener would be defensive.

---

### B14 — `modeNote()` accesses `state.status.ai.label` without null checks
**File:** [app.js#L51-L55](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L51-L55)

If `state.status` is `null` (before `loadStatus()` resolves) and a response comes in that calls `modeNote()`, it will throw `Cannot read properties of null`. This can happen if an "Ask" form submission completes before the initial `loadStatus()` call.

**Fix:** Guard: `state.status?.ai?.label || "AI"`.

---

### B15 — `loadDiary()` and `loadConfirms()` called in parallel at boot but can race
**File:** [app.js#L713](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L713)

```js
await Promise.all([loadStatus(), loadDiary(), loadConfirms().catch(() => {}), refreshCapture()]);
```

`loadConfirms()` reads from `#confirms` and may render cards that reference diary events (via `data-ref`). If it resolves before `loadDiary()`, the referenced events won't be in the DOM yet, so clicking a `[data-ref]` button immediately would show "not in the diary".

**Impact:** Minimal (the user would have to click extremely fast), but a correctness issue.

**Fix:** Chain: `await loadDiary(); await loadConfirms();` — or make the ref-click handler tolerate missing targets gracefully (it already does via `toast()`).

---

### B16 — CSS: `dialog` width is declared twice
**File:** [style.css#L182](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/style.css#L182) and [style.css#L230](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/style.css#L230)

```css
dialog { ... width: min(520px, 92vw); ... }  /* line 182 */
dialog { width: min(640px, 94vw); }           /* line 230 */
```

The second rule overrides the first. The first declaration (520px) is dead code.

**Fix:** Remove the `width` from line 182, or consolidate into one rule.

---

### B17 — `e.target.closest("pre, dd")` check in card click is fragile
**File:** [app.js#L403](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L403)

```js
if (card && !e.target.closest("pre, dd")) card.parentElement.classList.toggle("open");
```

This prevents toggling when clicking inside `<pre>` or `<dd>` (so users can select text). But it doesn't prevent toggling when clicking inside `<a>`, `<button>`, or `<input>` elements that might be added to the card body in the future. The check should be more inclusive.

**Fix:** `!e.target.closest("pre, dd, a, button, input, textarea, select")`.

---

### B18 — Missing `rel="noopener"` on some dynamically generated links
**File:** [app.js#L624](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L624)

The `paperItem()` function generates `<a>` tags with `target="_blank" rel="noopener"` — good. But some other generated links (e.g., in `renderSources()` at line 158, and `renderStatus()` at line 235) also include `rel="noopener"` — also good. No missing cases found on closer inspection. ~~Marking as resolved.~~

**Status:** Not a bug — all external links include `rel="noopener"`. Keeping this note for audit completeness.

---

### B19 — `info` prompt auto-dismiss is not cancellable
**File:** [app.js#L437](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L437)

```js
setTimeout(() => el.remove(), 7000);
```

"Info" prompts (like "Expectation held") auto-dismiss after 7 seconds. If the user wants to read it again, it's gone. There's no way to pin or re-show it.

**Fix:** Add a small close button and don't auto-dismiss, or add a "show past notifications" area.

---

### B20 — No loading state for the claims tab
**File:** [app.js#L682-L686](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js#L682-L686)

When "Build claim map" is clicked, `busy()` is used on the button, but the `#c-out` div stays empty (or shows the previous result) with no intermediate skeleton or spinner. On a slow model, the user sees nothing happening below the button for several seconds.

**Fix:** Show a skeleton or "Analyzing claims…" placeholder in `#c-out` immediately when the button is clicked.

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 High  | 3     |
| 🟡 Medium | 7    |
| 🟢 Low   | 10    |
