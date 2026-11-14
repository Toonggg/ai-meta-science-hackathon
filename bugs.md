# Episteme — Bug Report & Resolution Log

Bugs and issues identified during the front-end code review and their resolution status.

---

## 🔴 High Severity

### B1 — XSS via `raw_ids` in timeline event cards
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

The `raw_ids` array was interpolated into a `data-raw` attribute using `esc()`, but the join delimiter was `,`. If a raw ID contained an unexpected format or delimiter, split logic in click handlers could pass unvalidated IDs.
- **Fix:** Validated that IDs match `/^[ER]\d+$/i` before DOM injection, attribute parsing, and API request creation in `evCard`, `[data-raw]`, `[data-ref]`, and `[data-del]` handlers.
- **Status:** ✅ Resolved

---

### B2 — `showPane()` selector was too broad — clashed across dialogs
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

`$$(".dlg-tabs button")` selected every `.dlg-tabs button` on the page, including the diary view picker (`#view-pick`). Opening settings or switching tabs in settings stripped the active state from the diary view picker.
- **Fix:** Scoped selectors and click listeners strictly to `#settings .dlg-tabs button`.
- **Status:** ✅ Resolved

---

### B3 — Event polling replaced timeline HTML even when nothing changed (race condition)
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

The polling interval serialized the entire events array to full JSON on every tick and re-rendered the timeline on changes, resetting scroll position and recreating DOM nodes unnecessarily.
- **Fix:** Switched to a lightweight, deterministic signature (`id:ts:step:status:confirmation:title`) and preserved scroll position using `window.scrollTo` when a real change occurs.
- **Status:** ✅ Resolved

---

## 🟡 Medium Severity

### B4 — `form.addEventListener("submit")` on the add-form could double-fire
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

Rapid clicks on "Add" or pressing Enter repeatedly during async request submission caused multiple event additions.
- **Fix:** Added an `addSubmitting` guard and disabled the submit button during in-flight submission.
- **Status:** ✅ Resolved

---

### B5 — `fillProvider()` leaked display style changes
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

When switching back from provider "none", labels were restored with `style.display = ""`, which can fail to restore stylesheet grid layouts correctly.
- **Fix:** Used `l.style.removeProperty("display")`.
- **Status:** ✅ Resolved

---

### B6 — `#q-input` Enter handler fired even when textarea was multi-line
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js), [index.html](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/index.html)

Textarea submitted on Enter without notice, breaking multi-line questions and IME composition.
- **Fix:** Added `!e.isComposing` guard and updated the placeholder text to explicitly inform the researcher: `(Enter to stress-test, Shift+Enter for newline)`.
- **Status:** ✅ Resolved

---

### B7 — `toast._t` property on a function was a side-effect hack
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

Timer ID was attached as a mutable property on `toast`.
- **Fix:** Replaced with a module-level `let _toastTimer = null;`.
- **Status:** ✅ Resolved

---

### B8 — `loadConfirms` raced with user interaction
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

When polling updated confirm cards, active typing in another confirm card's input was cleared on re-render.
- **Fix:** Preserved typed values across card re-renders and restored them to their respective input fields.
- **Status:** ✅ Resolved

---

### B9 — `clearTimeout(qPoll)` should be `qPoll = null` after clearing
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

Stale timer ID references remained in `qPoll`.
- **Fix:** Explicitly set `qPoll = null;` after every clear, error, and completion.
- **Status:** ✅ Resolved

---

### B10 — `stChecking` Set was never bounded on check-all failure
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)

If `#st-check-all` encountered an unexpected exception, `stChecking` retained IDs and left spinners permanently active.
- **Fix:** Added a comprehensive `try / catch / finally` block in `#st-check-all` guaranteeing `stChecking.clear()`.
- **Status:** ✅ Resolved

---

## 🟢 Low Severity / Code Quality

### B11 — `$$` helper returns a spread array
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Confirmed design intent (static array snapshot).
- **Status:** ✅ Verified / No change required

---

### B12 — CSRF / Token security model on localhost
**File:** [server.py](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/server.py)
- Confirmed `same_origin()` Origin-header check protects localhost from cross-origin browser requests.
- **Status:** ✅ Verified / Safe for localhost MVP

---

### B13 — Defensive initialization for `syncType()`
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Added null-safe checks on `form` and `#add-type`.
- **Status:** ✅ Resolved

---

### B14 — `modeNote()` and `renderJob()` accessed `state.status.ai.label` without null checks
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Guarded `state.status?.ai?.label || "AI"` and `state.status?.ai?.model`.
- **Status:** ✅ Resolved

---

### B15 — `loadDiary()` and `loadConfirms()` called in parallel at boot could race
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Sequenced `await loadDiary();` before `loadConfirms();` so timeline events exist before confirm cards cite them.
- **Status:** ✅ Resolved

---

### B16 — CSS: `dialog` width was declared twice
**File:** [style.css](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/style.css)
- Consolidated dialog width into a single definition: `width: min(640px, 94vw);`.
- **Status:** ✅ Resolved

---

### B17 — `e.target.closest("pre, dd")` check in card click was fragile
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Expanded exclusion to `!e.target.closest("pre, dd, a, button, input, textarea, select, label")`.
- **Status:** ✅ Resolved

---

### B18 — External links missing `rel="noopener"`
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- All dynamic links audited; all contain `target="_blank" rel="noopener"`.
- **Status:** ✅ Verified / Safe

---

### B19 — `info` prompt auto-dismiss was not cancellable
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Added a dismiss button (`×`) and paused timer on mouse hover.
- **Status:** ✅ Resolved

---

### B20 — No loading state for claims tab
**File:** [app.js](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/episteme/static/app.js)
- Added an instant loading placeholder with spinner into `#c-out` when `#c-run` is clicked.
- **Status:** ✅ Resolved

---

## Summary

All 20 bugs and code quality items have been addressed and verified.
