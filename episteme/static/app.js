// Episteme UI: vanilla JS, no build step.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const TYPE_LABEL = { plan: "Plan", run: "Run", surprise: "Surprise", pivot: "Pivot", note: "Note", artifact: "Artifact", question: "Question" };
const SOURCE_LABEL = { chat: "AI chat", colab: "Colab", github: "GitHub", manual: "manual", agent: "agent hook", episteme: "Episteme", git: "git hook", tool: "script" };

let state = { events: [], status: null };

// Per-start token from the server: marks writes as coming from this page (confirm, settings, clear...).
const TOKEN = document.querySelector('meta[name="episteme-token"]')?.content || "";
async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json", "x-episteme-token": TOKEN }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
const useAI = () => $("#use-ai").checked;

let _toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(_toastTimer); _toastTimer = setTimeout(() => (t.hidden = true), 3200);
}

async function busy(btn, fn) {
  const label = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${useAI() ? "Thinking…" : "Analysing…"}`;
  try { return await fn(); } catch (e) { toast("Error: " + e.message); } finally { btn.disabled = false; btn.innerHTML = label; }
}

// Tiny markdown: **bold**, *italic*, bullet lists, paragraphs, [E12] citations.
function md(text) {
  const inline = (s) => esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<i>$2</i>")
    .replace(/\[(E\d+(?:\s*,\s*E\d+)*)\]/g, (_, ids) => ids.split(/\s*,\s*/).map((id) => `<button class="ref" data-ref="${id}">${id}</button>`).join(" "));
  let html = "", list = false;
  for (const line of String(text).split("\n")) {
    const m = line.match(/^\s*[-*]\s+(.*)/);
    if (m) { if (!list) { html += "<ul>"; list = true; } html += `<li>${inline(m[1])}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; }
    if (line.trim()) html += `<p>${inline(line)}</p>`;
  }
  return html + (list ? "</ul>" : "");
}

function modeNote(res) {
  const aiLabel = state.status?.ai?.label || "AI";
  const aiModel = state.status?.ai?.model;
  const modelStr = aiModel ? ` · ${aiModel}` : "";
  let s = `<div class="mode">${res.mode === "ai" ? "Answered by " + esc(aiLabel) + esc(modelStr) : "Local rules (no model call)"}</div>`;
  if (res.ai_error) s += `<div class="warn-note">AI unavailable (${esc(res.ai_error)}). Showing heuristic result instead.</div>`;
  return s;
}

// ---------------------------------------------------------------- theme
$("#theme").value = document.documentElement.dataset.theme;
$("#theme").addEventListener("change", (e) => {
  document.documentElement.dataset.theme = e.target.value;
  localStorage.setItem("theme", e.target.value);
});

// ---------------------------------------------------------------- tabs
function showTab(name) {
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((t) => (t.hidden = t.id !== "tab-" + name));
  history.replaceState(null, "", "#" + name);
}
$$("#tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ---------------------------------------------------------------- status / settings
async function loadStatus() {
  state.status = await api("/api/status");
  const ai = state.status.ai, src = state.status.search;
  const badge = $("#ai-badge");
  badge.textContent = ai.available ? `${ai.label} · ${ai.model}` : "No model";
  badge.classList.toggle("on", ai.available);
  const box = $("#use-ai");
  box.disabled = !ai.available;
  box.checked = ai.available && localStorage.getItem("useAI") !== "0";
  const sb = $("#src-badge");
  sb.textContent = src.available ? `${src.up}/${src.enabled} sources up` : "Sources off";
  sb.classList.toggle("on", src.up > 0 && src.up === src.enabled);
  sb.classList.toggle("warn", src.up > 0 && src.up < src.enabled);
  sb.classList.toggle("bad", src.available && src.up === 0 && src.sources.some((x) => x.enabled && x.last_check));
  sb.title = "Search sources: click for live status and manual checks";
  $("#tier-src").textContent = src.available ? `${src.up}/${src.enabled} online · status` : "all off · configure";
  $("#use-search").disabled = !src.available;
  $("#use-search").checked = src.available && localStorage.getItem("useSearch") !== "0";
  // One header pill summarises both capabilities; the details live in the menu it opens.
  const sum = $("#hdr-sum");
  sum.textContent = [ai.available ? ai.model : "No model", src.available ? `${src.up}/${src.enabled} sources` : "no search"].join(" · ");
  sum.classList.toggle("on", ai.available || src.up > 0);
  syncTiers();
  if ($("#settings").open) renderSources();
}
const useSearch = () => $("#use-search").checked;
function syncTiers() {
  $('#tiers [data-tier="search"]').classList.toggle("off", !useSearch());
  $('#tiers [data-tier="ai"]').classList.toggle("off", !useAI());
}
$("#use-ai").addEventListener("change", (e) => { localStorage.setItem("useAI", e.target.checked ? "1" : "0"); syncTiers(); });
$("#use-search").addEventListener("change", (e) => { localStorage.setItem("useSearch", e.target.checked ? "1" : "0"); syncTiers(); });
setInterval(() => loadStatus().catch(() => {}), 30000); // reflect the background health poller

function openSettings(pane) {
  const ai = state.status.ai;
  const sel = $("#s-provider");
  sel.innerHTML = ai.providers.map((p) => `<option value="${p.id}">${esc(p.label)}</option>`).join("");
  sel.value = ai.provider;
  fillProvider(true);
  renderSources();
  showPane(pane);
  $("#settings").showModal();
}
function showPane(name) {
  $$("#settings .dlg-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.pane === name));
  $$("#settings .pane").forEach((p) => (p.hidden = p.dataset.pane !== name));
}
$$("#settings .dlg-tabs button").forEach((b) => b.addEventListener("click", () => showPane(b.dataset.pane)));
$("#ai-badge").addEventListener("click", () => { $("#hdr-menu").open = false; openSettings("model"); });
$("#src-badge").addEventListener("click", () => { $("#hdr-menu").open = false; openStatus(); });
document.addEventListener("click", (e) => { // close the header menu on any click outside it
  if ($("#hdr-menu").open && !e.target.closest("#hdr-menu")) $("#hdr-menu").open = false;
});

function fillProvider(initial) {
  const ai = state.status.ai;
  const p = ai.providers.find((x) => x.id === $("#s-provider").value);
  const current = initial && p.id === ai.provider;
  $("#s-model").value = current ? ai.model : p.model;
  $("#s-base").value = current ? ai.base_url : p.base_url;
  $("#s-key").value = "";
  $("#s-key").placeholder = current && ai.has_key ? "•••••• saved (leave blank to keep)" : p.env_key_found ? "found in environment" : p.needs_key ? "paste key" : "not needed";
  $$('.pane[data-pane="model"] label').forEach((l) => {
    if (p.id === "none" && l.querySelector("input")) {
      l.style.display = "none";
    } else {
      l.style.removeProperty("display");
    }
  });
  const hints = {
    anthropic: "Claude via the Messages API. Key from console.anthropic.com, or set ANTHROPIC_API_KEY before ./run.",
    openai: "OpenAI, or any OpenAI-compatible server: LM Studio (http://localhost:1234/v1), llama.cpp, vLLM, OpenRouter. Local servers need no key.",
    gemini: "Google Gemini. Key from aistudio.google.com, or set GEMINI_API_KEY.",
    ollama: "Local model, nothing leaves your machine. Install Ollama, then: ollama pull llama3.1:8b. Bigger models give better critiques if your hardware allows.",
    none: "No model. Local rules + literature search still work.",
  };
  $("#s-hint").textContent = hints[p.id] || "";
}
$("#s-provider").addEventListener("change", () => fillProvider(false));

const STATE_LABEL = { up: "up", down: "paused", error: "error", unknown: "not checked yet", off: "off", needs_key: "needs key" };
function renderSources() {
  const src = state.status.search;
  const groups = { papers: "Papers (free, queried together)", datasets: "Datasets (free, queried together)", web: "Web (your key, tried in order)" };
  let html = "";
  for (const [g, title] of Object.entries(groups)) {
    html += `<div class="grp">${title}</div>`;
    const list = src.sources.filter((s) => s.group === g);
    if (g === "web") list.sort((a, b) => src.web_order.indexOf(a.id) - src.web_order.indexOf(b.id));
    for (const s of list) {
      const detail = s.state === "down" ? `${esc(s.error)} · retry in ${s.retry_in}s` : s.state === "up" ? `${s.latency}s` : esc(s.error || "");
      const keyInput = s.key === "none" ? "" :
        `<input type="${s.key_label === "API key" ? "password" : "text"}" data-key="${s.id}" autocomplete="off"
          placeholder="${s.has_key ? "saved / from env" : (s.key === "required" ? "API key (required)" : esc(s.key_label) + " (optional)")}"
          title="${esc(s.key_hint || "")}">`;
      html += `<div class="srow"><input type="checkbox" data-en="${s.id}" ${s.enabled || (s.key === "required" && !s.has_key) ? "checked" : ""}>
        <span class="dotc ${s.state}"></span>
        <span><a href="${esc(s.home)}" target="_blank" rel="noopener">${esc(s.label)}</a> <small>${STATE_LABEL[s.state] || s.state}${detail ? " · " + detail : ""}</small></span>
        <span>${keyInput}</span></div>`;
    }
  }
  $("#src-list").innerHTML = html;
}
$("#src-check").addEventListener("click", async (e) => {
  const b = e.target; b.disabled = true; b.textContent = "Checking…";
  try { state.status.search = await api("/api/sources/check", {}); renderSources(); } finally { b.disabled = false; b.textContent = "Check all now"; }
});

$("#s-save").addEventListener("click", async (e) => {
  e.preventDefault();
  await api("/api/settings", { provider: $("#s-provider").value, model: $("#s-model").value, base_url: $("#s-base").value, api_key: $("#s-key").value });
  const enabled = {}, keys = {};
  $$("[data-en]").forEach((c) => (enabled[c.dataset.en] = c.checked));
  $$("[data-key]").forEach((i) => { if (i.value.trim()) keys[i.dataset.key] = i.value.trim(); });
  await api("/api/sources", { enabled, keys });
  localStorage.setItem("useAI", "1"); localStorage.setItem("useSearch", "1");
  await loadStatus();
  $("#settings").close();
  toast(`Saved · ${state.status.ai.available ? state.status.ai.label : "no model"} · ${state.status.search.enabled} sources enabled`);
});

// ---------------------------------------------------------------- source status panel
const ago = (t) => {
  if (!t) return "never";
  const s = Math.max(0, Math.round(Date.now() / 1000 - t));
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.floor(s / 60)} min ago` : `${Math.floor(s / 3600)} h ago`;
};
const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const VIA = { poll: "auto", manual: "manual", search: "search" };
const ST_TEXT = { up: "online", down: "paused", error: "error", unknown: "not checked yet", off: "turned off", needs_key: "needs key" };
let stTimer = null, stChecking = new Set();

async function refreshStatus() {
  const src = await api("/api/sources");
  state.status.search = src;
  renderStatus(src);
}
function openStatus() {
  renderStatus(state.status.search);
  $("#status-dlg").showModal();
  refreshStatus();
  clearInterval(stTimer);
  stTimer = setInterval(() => { if ($("#status-dlg").open) refreshStatus().catch(() => {}); else clearInterval(stTimer); }, 2000);
}
$("#st-close").addEventListener("click", () => { $("#status-dlg").close(); loadStatus(); });
$("#status-dlg").addEventListener("close", () => { clearInterval(stTimer); loadStatus(); });
$("#st-configure").addEventListener("click", (e) => { e.preventDefault(); $("#status-dlg").close(); openSettings("sources"); });
document.addEventListener("click", (e) => { if (e.target.closest(".open-status")) { e.preventDefault(); openStatus(); } });

function renderStatus(src) {
  const issues = src.sources.filter((s) => s.enabled && ["down", "error"].includes(s.state)).length;
  $("#st-summary").innerHTML = src.available
    ? `<b>${src.up} of ${src.enabled}</b> enabled sources online${issues ? ` · ${issues} paused or failing (searches use the others)` : ""} · ` +
      (src.polling ? (src.next_poll_in != null ? `next automatic check in <b>${mmss(src.next_poll_in)}</b> (every ${src.poll_every / 60} min)` : "automatic check running…") : "automatic checks off (offline mode)")
    : "All sources are turned off" + (src.polling ? "" : " (offline mode)");
  const groups = { papers: "Papers", datasets: "Datasets", web: "Web search (your keys)" };
  let html = `<table class="st"><thead><tr><th>Status</th><th>Source</th><th>Latency</th><th>Last check</th><th>Recent checks</th><th>Uptime</th><th></th></tr></thead><tbody>`;
  for (const [g, title] of Object.entries(groups)) {
    html += `<tr><th colspan="7">${title}</th></tr>`;
    const list = src.sources.filter((s) => s.group === g);
    if (g === "web") list.sort((a, b) => src.web_order.indexOf(a.id) - src.web_order.indexOf(b.id));
    for (const s of list) {
      const busy = s.checking || stChecking.has(s.id);
      const st = busy ? `<span class="spinner"></span>checking…` : `<span class="dotc ${s.state}"></span> <span class="stxt ${s.state}">${ST_TEXT[s.state] || s.state}</span>`;
      let err = "";
      if (!busy && s.state === "down") err = `${esc(s.error)}${s.retry_in ? ` · retry in ${mmss(s.retry_in)}` : ""}`;
      else if (!busy && s.state === "error") err = esc(s.error);
      const hist = `<div class="hist">${Array.from({ length: 24 - s.history.length }, () => '<span class="hb"></span>').join("")}${s.history.map((h) =>
        `<span class="hb ${h.ok ? "ok" : "bad"} ${h.via === "poll" ? "poll" : ""}" title="${new Date(h.t * 1000).toLocaleTimeString()} · ${VIA[h.via] || h.via} · ${h.ok ? h.ms + " ms" : esc(h.err || "failed")}"></span>`).join("")}</div>`;
      let action;
      if (s.state === "needs_key") action = `<button class="ghost" data-configure>Add key</button>`;
      else if (!s.enabled) action = `<button class="ghost" data-configure>Enable</button>`;
      else action = `<button data-check="${s.id}" data-web="${s.probe_costs_credit ? 1 : ""}" ${busy ? "disabled" : ""}>${s.probe_costs_credit ? "Check (1 query)" : "Check"}</button>`;
      html += `<tr class="${s.enabled ? "" : "off"}"><td class="state">${st}</td>
        <td><a href="${esc(s.home)}" target="_blank" rel="noopener">${esc(s.label)}</a>${err ? `<div class="err">${err}</div>` : ""}</td>
        <td>${s.latency != null && s.state === "up" ? Math.round(s.latency * 1000) + " ms" : "—"}</td>
        <td>${s.last_check ? `${ago(s.last_check)} <span class="muted small">(${VIA[s.last_via] || s.last_via || ""})</span>` : '<span class="muted">never</span>'}</td>
        <td>${hist}</td><td>${s.uptime != null ? s.uptime + "%" : "—"}</td><td>${action}</td></tr>`;
    }
  }
  $("#st-table").innerHTML = html + "</tbody></table>";
}

$("#st-table").addEventListener("click", async (e) => {
  if (e.target.closest("[data-configure]")) { $("#status-dlg").close(); return openSettings("sources"); }
  const b = e.target.closest("[data-check]");
  if (!b) return;
  const sid = b.dataset.check;
  stChecking.add(sid); renderStatus(state.status.search);
  try { state.status.search = await api("/api/sources/check", { id: sid, include_web: !!b.dataset.web }); }
  catch (err) { toast("Check failed: " + err.message); }
  finally { stChecking.delete(sid); renderStatus(state.status.search); }
});
$("#st-check-all").addEventListener("click", async (e) => {
  const b = e.currentTarget; b.disabled = true; b.innerHTML = '<span class="spinner"></span>Checking…';
  state.status.search.sources.forEach((s) => { if (s.enabled && !s.probe_costs_credit) stChecking.add(s.id); });
  renderStatus(state.status.search);
  try {
    state.status.search = await api("/api/sources/check", {});
  } catch (err) {
    toast("Check all failed: " + err.message);
  } finally {
    stChecking.clear();
    b.disabled = false;
    b.textContent = "Check all now";
    renderStatus(state.status.search);
    loadStatus();
  }
});

// ---------------------------------------------------------------- diary
async function loadDiary(focusNew = false) {
  const snap = await api("/api/events");
  state.events = snap.events;
  state.sig = snap.events.map((e) => `${e.id}:${e.ts}:${e.step}:${e.status || ""}:${e.confirmation || ""}:${e.title}`).join("|");
  $("#project-name").textContent = snap.project || "Research diary";
  renderTimeline();
  if (focusNew) focusLatestStep();
}

// Who stated it: a short badge, the full sentence (from the server) on hover.
function whoBadge(e) {
  let cls = "prov", txt;
  if (e.pending) { cls += " pending"; txt = "pending"; }
  else if (e.confirmation === "edited" || e.actor === "human") txt = "researcher";
  else if (e.actor === "agent") txt = e.confirmation === "confirmed" ? "agent ✓" : "agent";
  else if (e.actor === "system" || e.provenance === "inferred") { cls += " inferred"; txt = "inferred"; }
  else { cls += " " + (e.provenance || ""); txt = e.provenance || "stated"; }
  if (e.confirmation === "skipped") txt += " · unconfirmed";
  return `<span class="${esc(cls)}" title="${esc(e.who || "")}">${esc(txt)}</span>`;
}

function evCard(e) {
  const fields = [];
  if (e.expectation) fields.push(["Expected", esc(e.expectation)]);
  if (e.detail) fields.push([e.type === "pivot" ? "Why" : "Detail", esc(e.detail)]);
  if (e.quote && e.quote !== e.detail) fields.push(["In their words", `<span class="quote">“${esc(e.quote)}”</span>`]);
  if (e.model_summary) fields.push(["Model's summary", esc(e.model_summary)]);
  if (e.proposed_reason) fields.push(["Proposed", esc(e.proposed_reason)]);
  if (e.who && e.actor) fields.push(["Stated by", esc(e.who)]);
  fields.push(["Recorded via", esc(SOURCE_LABEL[e.source] || e.source)]);
  if (e.classified_by) fields.push(["Classified by", esc(`${e.classified_by.model} · ${e.classified_by.at}`)]);
  if (e.result) fields.push(["Result", esc(e.result)]);
  if (e.status) fields.push(["Status", `<span class="${e.status === "failed" ? "status-failed" : ""}">${esc(e.status)}</span>`]);
  if (e.params) fields.push(["Parameters", esc(Object.entries(e.params).map(([k, v]) => `${k}=${v}`).join(", "))]);
  if (e.data) fields.push(["Data", esc(`${e.data.name} v${e.data.version} (${e.data.hash})`)]);
  if (e.links?.length) {
    const validLinks = e.links.filter((l) => /^[ER]\d+$/i.test(l));
    if (validLinks.length) {
      fields.push(["Linked to", validLinks.map((l) => `<button class="ref" data-ref="${esc(l)}">${esc(l)}</button>`).join(" ")]);
    }
  }
  if (e.raw_ids?.length) {
    const validRawIds = e.raw_ids.filter((id) => /^[ER]\d+$/i.test(id));
    if (validRawIds.length) {
      fields.push(["Raw evidence", `<button class="ref" data-raw="${esc(validRawIds.join(","))}" title="Show what the capture hooks recorded">${esc(validRawIds.join(" "))}</button>`]);
    }
  }
  const time = new Date(e.ts);
  const when = isNaN(time) ? e.ts : time.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  const id = esc(e.id);
  return `<li class="ev t-${esc(e.type)}" id="ev-${id}" data-id="${id}">
    <span class="dot">${esc(e.step)}</span>
    <div class="card">
      <div class="top"><span class="chip">${esc(TYPE_LABEL[e.type] || e.type)}</span><span class="title">${esc(e.title)}</span>
        <button class="del" title="Delete event" data-del="${id}">×</button></div>
      <div class="meta"><span class="eid">${id}</span><span>${esc(when)}</span>
        ${whoBadge(e)}
        ${e.result ? `<span>→ ${esc(e.result.length > 60 ? e.result.slice(0, 58) + "…" : e.result)}</span>` : ""}</div>
      <div class="body"><dl>${fields.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
        ${e.code ? `<pre><code>${esc(e.code)}</code></pre>` : ""}</div>
    </div></li>`;
}

// View switch: all events / decisions only / raw capture grouped into episodes.
const isDecision = (e) => ["plan", "pivot", "surprise", "note", "question"].includes(e.type) || e.status === "failed";
let view = "all";
try { view = localStorage.getItem("diary-view") || "all"; } catch (_) { /* storage blocked: default view */ }

function renderTimeline() {
  const tl = $("#timeline");
  renderAskExamples();
  $$("#view-pick button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  tl.hidden = view === "raw";
  $("#raw-view").hidden = view !== "raw";
  if (view === "raw") return renderRaw();
  const shown = view === "decisions" ? state.events.filter(isDecision) : state.events;
  tl.innerHTML = shown.length ? shown.map(evCard).join("") : state.events.length
    ? `<li class="empty">No decisions yet. Switch to All to see every event.</li>`
    : `<li class="empty">Empty diary. Add a plan above, or stress-test a question in step 1 and start from there.</li>`;
  renderCaptureStatus();
}

function focusLatestStep() {
  let target = null;
  if (view === "raw") {
    const rawCards = $$("#raw-view .card");
    if (rawCards.length) target = rawCards[rawCards.length - 1];
  } else {
    const list = $$("#timeline li.ev");
    if (list.length) target = list[list.length - 1];
  }
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.remove("highlight-pulse");
    void target.offsetWidth;
    target.classList.add("highlight-pulse");
    target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
  }
}

$("#view-pick").addEventListener("click", (e) => {
  const b = e.target.closest("[data-view]");
  if (!b) return;
  view = b.dataset.view;
  try { localStorage.setItem("diary-view", view); } catch (_) { /* fine without it */ }
  renderTimeline();
});

const RAW_KIND = { instruction: "instruction", action: "action", agent_text: "agent says", commit: "commit", stop: "turn ends" };
function rawLine(r) {
  const what = r.kind === "action" ? `${r.tool || ""} ${r.command || (r.files || []).join(", ")}`
    : r.kind === "commit" ? `${(r.commit || "").slice(0, 7)} ${r.text || ""}` : (r.text || "");
  const out = (r.output || "").trim().split("\n").filter(Boolean).slice(-2).join(" ⏎ ");
  return `${r.rid.padEnd(5)} ${(RAW_KIND[r.kind] || r.kind).padEnd(12)} ${what.trim().slice(0, 160)}${r.error ? "  [error]" : ""}${out && r.kind === "action" ? "\n" + " ".repeat(19) + "→ " + out.slice(0, 160) : ""}`;
}

async function renderRaw() {
  const box = $("#raw-view");
  const [{ raw }, { episodes }] = await Promise.all([api("/api/raw"), api("/api/episodes")]);
  state.rawCount = raw.length;
  const byId = Object.fromEntries(raw.map((r) => [r.rid, r]));
  const CLOSE = { result: "closed by a result", error: "closed by a failure", commit: "closed by a commit", cap: "split (too long)",
    next_instruction: "ended by the next instruction", next_activity: "ended by new activity" };
  box.innerHTML = episodes.length ? episodes.map((ep) => `<div class="card">
      <h3>${esc(ep.id)} <span class="muted small">${esc(CLOSE[ep.close_reason] || "still open")}${ep.final ? "" : " · not stitched yet"}</span>
        ${ep.flags.map((f) => `<span class="srcchip">${esc(f.replace("_", " "))}</span>`).join("")}</h3>
      <pre class="snippet">${esc(ep.raw_ids.map((id) => rawLine(byId[id])).join("\n"))}</pre></div>`).join("")
    : `<div class="empty">Nothing captured yet. Switch capture on with <code>python3 capture/install.py &lt;project&gt;</code>.</div>`;
  renderCaptureStatus();
}

function renderCaptureStatus() {
  const s = state.stitch;
  const el = $("#capture-status");
  if (!s || !s.stitched) { el.textContent = ""; return; }
  const parts = [`${s.stitched} episode${s.stitched === 1 ? "" : "s"} captured`];
  if (s.pending) parts.push(`${s.pending} pivot${s.pending === 1 ? "" : "s"} waiting for a model`);
  parts.push(s.model ? `classified by ${s.model}` : "rules only (no model)");
  el.innerHTML = esc(parts.join(" · ")) + (s.last_error ? ` · <span class="warn-note">${esc(s.last_error)}</span>` : "");
}

function flash(id) {
  showTab("diary");
  const el = $("#ev-" + id);
  if (!el) return toast(id + " is not in the diary");
  el.classList.add("open", "flash");
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => el.classList.remove("flash"), 1600);
}

document.addEventListener("click", async (e) => {
  const rawBtn = e.target.closest("[data-raw]");
  if (rawBtn) { // show / hide the captured raw events behind a diary event
    e.stopPropagation();
    const body = rawBtn.closest(".body");
    const shown = $(".raw-out", body);
    if (shown) return shown.remove();
    const ids = (rawBtn.dataset.raw || "").split(",").filter((id) => /^[ER]\d+$/i.test(id));
    if (!ids.length) return;
    const { raw } = await api("/api/raw?ids=" + encodeURIComponent(ids.join(",")));
    body.insertAdjacentHTML("beforeend", `<pre class="raw-out">${esc(raw.map(rawLine).join("\n") || "Not in the raw log (it may have been cleared).")}</pre>`);
    return;
  }
  const ref = e.target.closest(".ref");
  if (ref && ref.dataset.ref) {
    e.stopPropagation();
    const safeRef = ref.dataset.ref.trim();
    if (/^E\d+$/i.test(safeRef)) return flash(safeRef);
    return;
  }
  const del = e.target.closest("[data-del]");
  if (del && del.dataset.del) {
    e.stopPropagation();
    const delId = del.dataset.del.trim();
    if (!/^E\d+$/i.test(delId)) return;
    if (!confirm("Delete " + delId + " from the diary?")) return;
    await api("/api/delete", { id: delId });
    return loadDiary();
  }
  const card = e.target.closest(".ev .card");
  if (card && !e.target.closest("pre, dd, a, button, input, textarea, select, label")) card.parentElement.classList.toggle("open");
});

// add form
const form = $("#add-form");
const syncType = () => { if (form && $("#add-type")) form.dataset.type = $("#add-type").value; };
if (form) {
  $("#add-type")?.addEventListener("change", () => { syncType(); form.classList.add("expanded"); });
  $("#add-title")?.addEventListener("focus", () => form.classList.add("expanded"));
  syncType();
}
let addSubmitting = false;
form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (addSubmitting) return;
  const type = $("#add-type").value;
  const title = $("#add-title").value.trim();
  if (!title) return $("#add-title").focus();
  const submitBtn = $("button[type=submit]", form);
  addSubmitting = true;
  if (submitBtn) submitBtn.disabled = true;
  try {
    const ev = { type, title, detail: $("#add-detail").value.trim(), source: "manual" };
    if (type === "plan") ev.expectation = $("#add-expect").value.trim();
    if (type === "run") { ev.result = $("#add-result").value.trim(); ev.status = $("#add-status").value; }
    const res = await api("/api/events", ev);
    ["#add-title", "#add-detail", "#add-expect", "#add-result"].forEach((s) => ($(s).value = ""));
    form.classList.remove("expanded");
    await loadDiary();
    res.auto.forEach((a) => flash(a.id));
    showPrompts(res.prompts);
    if (!res.auto.length && !res.prompts.some((p) => p.kind === "pivot_why")) flash(res.event.id);
  } catch (err) {
    toast("Error: " + err.message);
  } finally {
    addSubmitting = false;
    if (submitBtn) submitBtn.disabled = false;
  }
});

function showPrompts(prompts) {
  const box = $("#prompts");
  box.innerHTML = "";
  for (const p of prompts) {
    const el = document.createElement("div");
    el.className = "card prompt" + (p.kind === "info" ? " info" : "");
    if (p.kind === "info") {
      el.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
        <div>${md(p.message)}</div>
        <button type="button" class="del" style="opacity:0.6; cursor:pointer;" title="Dismiss">×</button>
      </div>`;
      const delBtn = $(".del", el);
      let timer = setTimeout(() => el.remove(), 7000);
      el.addEventListener("mouseenter", () => clearTimeout(timer));
      el.addEventListener("mouseleave", () => {
        clearTimeout(timer);
        timer = setTimeout(() => el.remove(), 4000);
      });
      if (delBtn) delBtn.addEventListener("click", () => { clearTimeout(timer); el.remove(); });
    } else {
      el.innerHTML = `<h4>Why the change of direction?</h4><div>${md(p.message)}</div>
        <form class="row"><input placeholder="e.g. the OOM showed we can't fit trigram features in memory" autocomplete="off">
        <button class="primary">Record reason</button><button type="button" class="ghost skip">Skip (log as inferred)</button></form>`;
      const send = async (skipped) => {
        const reason = $("input", el).value.trim();
        if (!skipped && !reason) return $("input", el).focus();
        const r = await api("/api/pivot", { plan_id: p.plan_id, links: p.links, reason, skipped });
        el.remove();
        await loadDiary();
        flash(r.event.id);
      };
      $("form", el).addEventListener("submit", (e) => { e.preventDefault(); send(false); });
      $(".skip", el).addEventListener("click", () => send(true));
      setTimeout(() => $("input", el).focus(), 50);
    }
    box.appendChild(el);
  }
}

// one-click confirmation of pivots the agent stated or the rules flagged
function confirmCard(p) {
  const step = esc(p.step), id = esc(p.id);
  const ask = p.pending ? `Why did the approach change at step ${step}?` : `Is this the reason for step ${step}?`;
  const body = p.pending
    ? ""
    : `<p class="quote">“${esc(p.reason)}”</p>${p.model_summary ? `<p class="muted small">Model's summary: ${esc(p.model_summary)}</p>` : ""}`;
  // Pending (rules only): one line of context and one input row with Save + Skip.
  const skip = `<button type="button" class="ghost" data-act="skip">Skip</button>`;
  return `<div class="card prompt${p.pending ? " compact" : ""}" data-confirm="${id}">
    <h4>${ask}</h4>
    <div class="muted small ctx" title="${esc(p.title)}"><button class="ref" data-ref="${id}">${id}</button> ${esc(p.title)}${p.pending ? " · flagged by rules" : " · " + esc(p.who)}</div>
    ${body}
    <form class="row"${p.pending ? "" : " hidden"}><input placeholder="The reason, in your words" autocomplete="off">
      <button class="primary">Save reason</button>${p.pending ? skip : ""}</form>
    ${p.pending ? "" : `<div class="btns">
      ${p.actions.includes("confirm") ? `<button type="button" class="primary" data-act="confirm">✔ Confirm</button>` : ""}
      <button type="button" class="ghost" data-act="edit">✎ Edit</button>
      ${skip}
    </div>`}</div>`;
}

async function loadConfirms() {
  const { prompts } = await api("/api/prompts");
  const box = $("#confirms");
  const key = prompts.map((p) => p.id + (p.pending ? "p" : "")).join(",");
  if (box.dataset.key === key) return; // unchanged: keep whatever is being typed
  const typedValues = {};
  $$("[data-confirm]", box).forEach((card) => {
    const id = card.dataset.confirm;
    const inp = $("input", card);
    if (inp && inp.value) typedValues[id] = inp.value;
  });
  box.dataset.key = key;
  box.innerHTML = prompts.map(confirmCard).join("");
  $$("[data-confirm]", box).forEach((card) => {
    const id = card.dataset.confirm;
    if (typedValues[id]) {
      const inp = $("input", card);
      const f = $("form", card);
      if (inp) {
        inp.value = typedValues[id];
        if (f) f.hidden = false;
      }
    }
  });
}

async function answer(card, action, reason) {
  const id = card.dataset.confirm;
  try {
    await api("/api/confirm", { id, action, reason });
  } catch (err) { return toast("Error: " + err.message); }
  delete $("#confirms").dataset.key;
  await Promise.all([loadDiary(), loadConfirms()]);
  flash(id);
}

$("#confirms").addEventListener("click", (e) => {
  const b = e.target.closest("[data-act]");
  if (!b) return;
  const card = b.closest("[data-confirm]");
  if (b.dataset.act === "edit") {
    const f = $("form", card);
    f.hidden = false;
    $("input", f).value = $("p", card)?.textContent || "";
    return $("input", f).focus();
  }
  answer(card, b.dataset.act);
});
$("#confirms").addEventListener("submit", (e) => {
  e.preventDefault();
  const card = e.target.closest("[data-confirm]");
  const reason = $("input", card).value.trim();
  if (!reason) return $("input", card).focus();
  answer(card, "edit", reason);
});

// ask the log
// Example questions come from the diary on screen, so they never point at a step that isn't there.
function askExamples() {
  const pivot = state.events.find((e) => e.type === "pivot");
  const qs = [];
  if (pivot) qs.push(`Why did they change approach at step ${pivot.step}?`);
  if (state.events.some((e) => e.type === "surprise")) qs.push("Which expectations were contradicted?");
  if (state.events.length) qs.push("What was tried and abandoned?");
  return qs;
}
function renderAskExamples() {
  const qs = askExamples();
  const box = $("#ask-examples");
  if (box.dataset.key === qs.join("|")) return;
  box.dataset.key = qs.join("|");
  box.innerHTML = qs.map((q) => `<button type="button">${esc(q)}</button>`).join("");
  $("#ask-input").placeholder = qs[0] || "Ask about the diary";
}
$("#ask-examples").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  $("#ask-input").value = b.textContent; $("#ask-form").requestSubmit();
});
$("#ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#ask-input").value.trim() || $("#ask-input").placeholder;
  $("#ask-input").value = q;
  const reviewerCard = $(".reviewer-card");
  if (reviewerCard) {
    reviewerCard.scrollIntoView({ behavior: "smooth", block: "center" });
    reviewerCard.classList.remove("highlight-pulse");
    void reviewerCard.offsetWidth;
    reviewerCard.classList.add("highlight-pulse");
  }
  busy($("#ask-form button"), async () => {
    const res = await api("/api/ask", { question: q, use_ai: useAI() });
    $("#ask-out").innerHTML = `<div class="answer">${md(res.answer)}</div>${modeNote(res)}`;
    $("#ask-out").scrollIntoView({ behavior: "smooth", block: "nearest" });
    const ans = $("#ask-out .answer");
    if (ans) {
      ans.classList.add("highlight-pulse");
      ans.setAttribute("tabindex", "-1");
      ans.focus({ preventScroll: true });
    }
  });
});
const goldenBtn = $("#golden-test-btn");
if (goldenBtn) {
  goldenBtn.addEventListener("click", () => {
    $("#ask-input").value = "Why did they change approach at step 4?";
    $("#ask-form").requestSubmit();
  });
}

// ---------------------------------------------------------------- start screen
// Shown once each time Episteme starts (the token changes per start), and from the logo.
const START_SEEN = "episteme-start-seen";
function startSeen() { try { return sessionStorage.getItem(START_SEEN) === TOKEN; } catch { return false; } }
function markStartSeen() { try { sessionStorage.setItem(START_SEEN, TOKEN); } catch { /* private mode: show it again next load */ } }

async function openStart() {
  const [{ demos, current }, snap] = await Promise.all([api("/api/demos"), api("/api/events")]);
  const n = snap.events.length;
  const cont = $("#start-continue");
  cont.hidden = !n;
  cont.innerHTML = n ? `<b>Continue: ${esc(snap.project || "current study")}</b><small>${n} ${n === 1 ? "entry" : "entries"}${current ? " · demo" : ""}</small>` : "";
  $("#start-demos").innerHTML = demos.map((d) => {
    const isFeatured = d.id === "alphafold";
    return `<button type="button" class="start-demo ${isFeatured ? "featured-demo" : ""}" data-demo="${esc(d.id)}" id="start-demo-${esc(d.id)}">
      ${isFeatured ? '<div class="demo-badge-row"><span class="badge featured-badge">⭐ Task 2 Featured Demo</span><span class="badge-sub">Step 4 Pivot</span></div>' : ""}
      <b>${esc(d.title)}</b><span class="muted">${esc(d.summary)}</span></button>`;
  }).join("");
  const warn = $("#start-warn");
  warn.hidden = !n;
  warn.textContent = n ? `Starting a notebook or loading a demo replaces the current diary (${n} ${n === 1 ? "entry" : "entries"}) and its raw capture. Export it first to keep it.` : "";
  $("#start").hidden = false;
  document.body.style.overflow = "hidden";
  (n ? cont : $("#start-project")).focus();
}

function closeStart() {
  markStartSeen();
  $("#start").hidden = true;
  document.body.style.overflow = "";
  showTab("diary");
}

let replayActive = false;
let replayAborted = false;

async function runLiveReplay(demoId = "alphafold") {
  if (replayActive) return;
  replayActive = true;
  replayAborted = false;

  closeStart();
  showTab("diary");

  const banner = $("#replay-banner");
  const bannerText = $("#replay-banner-text");
  const bannerProgress = $("#replay-progress");
  const skipBtn = $("#replay-skip-btn");

  if (banner) {
    banner.hidden = false;
    bannerText.innerHTML = "<strong>Replaying AlphaFold 2 capture session</strong> (15x speed)...";
    bannerProgress.textContent = "initializing...";
  }

  const finishReplay = () => {
    if (bannerText) bannerText.innerHTML = "<strong>Replay complete!</strong> Auditing Step 4 pivot...";
    if (bannerProgress) bannerProgress.textContent = "11 events active";
    toast("AlphaFold 2 replay complete! Notice the pivot at Step 4.");
    setTimeout(() => { if (banner) banner.hidden = true; }, 4500);

    // Switch focus smoothly to the Auditor Station
    const reviewerCard = $(".reviewer-card");
    if (reviewerCard) {
      reviewerCard.scrollIntoView({ behavior: "smooth", block: "center" });
      reviewerCard.classList.remove("highlight-pulse");
      void reviewerCard.offsetWidth;
      reviewerCard.classList.add("highlight-pulse");
      reviewerCard.setAttribute("tabindex", "-1");
      reviewerCard.focus({ preventScroll: true });
    }
    $("#ask-input").value = "Why did they change approach at step 4?";
    $("#ask-form").requestSubmit();
  };

  const onSkip = async () => {
    replayAborted = true;
    if (bannerProgress) bannerProgress.textContent = "fast-forwarding...";
    try {
      await api("/api/demo", { id: demoId });
      await afterNewStudy();
      focusLatestStep();
      finishReplay();
    } catch (err) {
      toast("Error: " + err.message);
    }
  };
  if (skipBtn) skipBtn.onclick = onSkip;

  try {
    const init = await api("/api/demo/step", { id: demoId, step: 0, reset: true });
    await afterNewStudy();
    focusLatestStep();
    const total = init.total || 15;

    for (let i = 0; i < total; i++) {
      if (replayAborted) break;
      const stepNum = i + 1;
      if (bannerProgress) bannerProgress.textContent = `step ${stepNum} of ${total}`;

      const prevCount = state.events ? state.events.length : 0;
      if (i > 0) {
        await api("/api/demo/step", { id: demoId, step: i });
        await Promise.all([loadDiary(), loadConfirms(), refreshCapture()]);
      }

      // Switch screen focus whenever a step is loaded from the demo
      focusLatestStep();

      const newCount = state.events ? state.events.length : 0;
      // Paced replay: 950ms when a new card is emitted, 700ms for internal turn steps
      const delay = newCount > prevCount ? 950 : 700;
      await new Promise((r) => setTimeout(r, delay));
    }

    if (!replayAborted) {
      finishReplay();
    }
  } catch (e) {
    toast("Live replay error: " + e.message);
    if (banner) banner.hidden = true;
  } finally {
    replayActive = false;
  }
}

async function afterNewStudy() { // a different diary: drop what the page showed for the old one
  $("#prompts").innerHTML = ""; $("#ask-out").innerHTML = "";
  if ($("#c-out")) $("#c-out").innerHTML = "";
  if ($("#c-input")) $("#c-input").value = "";
  delete $("#confirms").dataset.key;
  await Promise.all([loadDiary(), loadConfirms(), refreshCapture()]);
  closeStart();
}

$("#start-new").addEventListener("submit", (e) => {
  e.preventDefault();
  const project = $("#start-project").value.trim();
  if (!project) return $("#start-project").focus();
  busy($("#start-new button"), async () => {
    await api("/api/clear", { project });
    $("#start-project").value = "";
    await afterNewStudy();
    toast("New notebook started. Add a plan with an expectation to begin.");
    $("#add-title").focus();
  });
});
$("#start-demos").addEventListener("click", (e) => {
  const b = e.target.closest("[data-demo]");
  if (!b) return;
  const demoId = b.dataset.demo;
  busy(b, async () => {
    const r = await api("/api/demo", { id: demoId });
    await afterNewStudy();
    focusLatestStep();
    toast(`Demo loaded: ${r.events} entries.`);
    if (demoId === "alphafold") {
      $("#ask-input").value = "Why did they change approach at step 4?";
      $("#ask-form").requestSubmit();
    }
  });
});

const startReplayBtn = $("#start-replay-btn");
if (startReplayBtn) {
  startReplayBtn.addEventListener("click", () => runLiveReplay("alphafold"));
}

const replayCodeBtn = $("#replay-code-btn");
if (replayCodeBtn) {
  replayCodeBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText("python3 tools/replay.py demo/alphafold.jsonl --speed 15");
      toast("Replay command copied! Running live in webpage...");
    } catch {}
    runLiveReplay("alphafold");
  });
  replayCodeBtn.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      runLiveReplay("alphafold");
    }
  });
}

const copyReplayBtn = $("#copy-replay-btn");
if (copyReplayBtn) {
  copyReplayBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText("python3 tools/replay.py demo/alphafold.jsonl --speed 15");
      toast("Copied: python3 tools/replay.py demo/alphafold.jsonl --speed 15");
    } catch {
      toast("Command: python3 tools/replay.py demo/alphafold.jsonl --speed 15");
    }
  });
}

const quickDemoBtn = $("#quick-demo-btn");
if (quickDemoBtn) {
  quickDemoBtn.addEventListener("click", () => {
    closeStart();
    busy(quickDemoBtn, async () => {
      const r = await api("/api/demo", { id: "alphafold" });
      await afterNewStudy();
      focusLatestStep();
      toast(`AlphaFold 2 demo loaded: ${r.events} entries. Auditing step 4 pivot...`);
      $("#ask-input").value = "Why did they change approach at step 4?";
      $("#ask-form").requestSubmit();
    });
  });
}
$("#start-continue").addEventListener("click", closeStart);
$("#open-start").addEventListener("click", () => openStart().catch((e) => toast("Error: " + e.message)));
$("#new-study").addEventListener("click", () => openStart().catch((e) => toast("Error: " + e.message)));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#start").hidden && !$("#start-continue").hidden) closeStart(); });

async function refreshCapture() {
  state.stitch = await api("/api/stitch").catch(() => null);
  renderCaptureStatus();
  if (view === "raw" && !$("#tab-diary").hidden) {
    const n = await api("/api/raw").then((r) => r.raw.length).catch(() => state.rawCount);
    if (n !== state.rawCount) renderRaw();
  }
}

// global hotkey: Cmd/Ctrl+Shift+E -> drop a thought
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "e") {
    e.preventDefault(); showTab("diary"); $("#add-type").value = "note"; syncType(); $("#add-title").focus();
  }
});

// ---------------------------------------------------------------- task 1: question (staged pipeline)
const Q_EXAMPLES = [
  "How does social media engagement impact adolescent wellbeing?",
  "Does AI improve the productivity of software workers?",
  "Among adult inpatients in MIMIC-IV, do discharge-note features predict 30-day readmission?",
  "Should AI systems replace human peer reviewers?",
];
if ($("#q-input")) {
  $("#q-examples").innerHTML = Q_EXAMPLES.map((q) => `<button type="button">${esc(q)}</button>`).join("");
  $$("#q-examples button").forEach((b) => b.addEventListener("click", () => { $("#q-input").value = b.textContent; $("#q-run").click(); }));
  $("#q-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("#q-run").click();
    }
  });
}

// [P3] [D1] [W2] -> clickable chips that jump to the item in the results; [E4] -> diary
function rich(text) {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/\[([PDW]\d+(?:\s*,\s*[PDW]\d+)*)\]/g, (_, ids) => ids.split(/\s*,\s*/).map((id) => `<button class="ref p" data-item="${id}">${id}</button>`).join(" "))
    .replace(/\[(E\d+)\]/g, (_, id) => `<button class="ref" data-ref="${id}">${id}</button>`);
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-item]");
  if (!b) return;
  const el = document.getElementById("item-" + b.dataset.item);
  if (!el) return toast(b.dataset.item + " is not in the result list");
  const det = el.closest("details"); if (det) det.open = true;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600);
});
const originTag = (o) => o ? `<span class="origin o-${o}" title="${{ rule: "From local rules", search: "From literature search", ai: "From the AI model" }[o] || ""}">${o === "ai" ? "AI" : o}</span>` : "";

let qPoll = null;
if ($("#q-run")) {
  $("#q-run").addEventListener("click", async () => {
    const q = $("#q-input").value.trim();
    if (!q) return $("#q-input").focus();
    clearTimeout(qPoll);
    qPoll = null;
    const btn = $("#q-run");
    btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>Running…`;
    try {
      const { job } = await api("/api/question/start", { question: q, use_search: useSearch(), use_ai: useAI() });
      const tick = async () => {
        const j = await api("/api/jobs/" + job);
        renderJob(q, j);
        if (j.status === "done") {
          btn.disabled = false;
          btn.textContent = "Stress-test";
          clearTimeout(qPoll);
          qPoll = null;
        } else {
          qPoll = setTimeout(tick, 600);
        }
      };
      await tick();
    } catch (e) {
      toast("Error: " + e.message);
      btn.disabled = false;
      btn.textContent = "Stress-test";
      clearTimeout(qPoll);
      qPoll = null;
    }
  });
}

const ICON = { pending: "○", running: '<span class="spinner"></span>', done: "✓", skipped: "–", failed: "!" };
function stageCard(key, title, st) {
  let extra = "";
  if (key === "search" && st.report) {
    extra = `<details><summary>Sources (${st.report.filter((r) => r.state === "ok").length} answered)</summary>
      ${st.report.map((r) => `<div class="src-row"><span class="dotc ${r.state}"></span><span>${esc(r.label)}: ${r.state === "ok" ? r.count + " results" + (r.cached ? " (cached)" : "") : esc(r.state)}${r.error ? ` <span class="muted">· ${esc(r.error)}</span>` : ""}</span></div>`).join("")}
      ${st.keywords ? `<div class="muted" style="margin-top:4px">Sent keywords: <code>${esc(st.keywords.join(" "))}</code></div>` : ""}</details>`;
  }
  if (key === "ai" && st.queries?.length) {
    extra = `<details><summary>${st.queries.length} refined searches</summary>${st.queries.map((x) => `<div class="src-row"><span>🔎</span><span><code>${esc(x.query)}</code> <span class="muted">· ${esc(x.purpose)}</span></span></div>`).join("")}</details>`;
  }
  return `<div class="stage ${st.state}"><div class="head"><span class="ico">${ICON[st.state] || ""}</span>${title}</div><div class="note">${esc(st.note || st.state)}</div>${extra}</div>`;
}

function paperItem(p) {
  const meta = [p.authors, p.year, p.venue, p.citations != null ? `${p.citations} ${p.kind === "dataset" ? "downloads/cites" : "citations"}` : ""].filter(Boolean).map(esc).join(" · ");
  return `<li id="item-${p.id}"><button class="ref p" data-item="${p.id}">${p.id}</button>
    <a class="ptitle" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>
    ${p.kind === "systematic_review" ? '<span class="kind">systematic review</span>' : p.kind === "review" ? '<span class="kind minor">review</span>' : ""}
    ${p.via_ai ? originTag("ai") : ""}
    <div class="pmeta">${meta}</div>
    <div class="pmeta">${(p.found_in || [p.source]).map((s) => `<span class="srcchip">${esc(s.replace("_", " "))}</span>`).join("")}</div></li>`;
}

function renderJob(q, j) {
  const r = j.analysis;
  const S = j.stages;
  let html = `<div class="pipeline">${stageCard("local", "1 · Local rules", S.local)}${stageCard("search", "2 · Literature search", S.search)}${stageCard("ai", "3 · AI refinement", S.ai)}</div>`;
  if (!r) { $("#q-out").innerHTML = html; return; }

  const terms = r.terms.length ? r.terms.map((t) => {
    const ev = t.evidence ? Object.fromEntries(t.evidence.map((e) => [e.sense, e])) : {};
    return `<div class="term"><b>“${esc(t.term)}”</b> is used in ${t.senses.length} senses:${originTag(t.origin)}
      <ol>${t.senses.map((s) => { const e = ev[s]; return `<li>${rich(s)}${e ? ` <span class="sensecount">· in ${e.count} paper${e.count === 1 ? "" : "s"}</span> ${e.papers.map((id) => `<button class="ref p" data-item="${id}">${id}</button>`).join(" ")}` : ""}</li>`; }).join("")}</ol>
      <span class="muted small">${rich(t.note)}</span></div>`;
  }).join("") : `<p class="muted">No known ambiguous constructs detected${r.mode !== "ai" ? " by the local lexicon. AI refinement does open-vocabulary term analysis" : ""}.</p>`;
  const assumptions = r.assumptions.map((a) => `<li><span class="risk ${a.risk}" title="${a.risk} risk"></span><b>${rich(a.text)}</b>${originTag(a.origin)}<br><span class="muted">${rich(a.check)}</span></li>`).join("");
  const data = r.data_needs.map((d) => `<li><span class="avail ${d.availability}">${d.availability}</span> ${rich(d.need)}${originTag(d.origin)}<br><span class="muted small">${rich(d.where)}</span></li>`).join("");
  const ladder = r.rewrites.map((w, i) => `<li><span><b>${i + 1}.</b> ${esc(w)}</span><button data-rq="${esc(w)}">Start diary with this →</button></li>`).join("");
  const key = (r.key_papers || []).map((k) => `<li><button class="ref p" data-item="${k.id}">${k.id}</button> ${esc((j.papers.concat(j.datasets).find((p) => p.id === k.id) || {}).title || "")}<br><span class="muted small">${rich(k.why)}</span></li>`).join("");

  html += `
    <div class="verdict v-${r.verdict}"><div class="word">${r.verdict}</div><div>${rich(r.verdict_reason)} ${originTag(r.verdict_origin)}</div></div>
    <div class="grid2">
      <div class="card"><h3>Ambiguous terms</h3>${terms}</div>
      <div class="card"><h3>Implicit assumptions</h3><ul class="plain">${assumptions || "<li class='muted'>None detected.</li>"}</ul></div>
      <div class="card"><h3>Evidence needed, and can you get it?</h3><ul class="plain">${data || "<li class='muted'>—</li>"}</ul></div>
      <div class="card"><h3>Already answered?</h3><p style="margin-top:0">${rich(r.already_answered)} ${originTag(r.already_answered_origin)}</p>
        <h3>Narrowing ladder</h3><ul class="plain ladder">${ladder}</ul></div>
      ${key ? `<div class="card"><h3>Read these first ${originTag("ai")}</h3><ul class="plain">${key}</ul></div>` : ""}
    </div>`;
  if (j.papers.length || j.datasets.length || j.web.length) {
    html += `<div class="grid2">
      <div class="card"><h3>Literature found (${j.papers.length}) ${originTag("search")}</h3>
        <ul class="plain papers">${j.papers.slice(0, 10).map(paperItem).join("")}</ul>
        ${j.papers.length > 10 ? `<details><summary class="muted">Show all ${j.papers.length}</summary><ul class="plain papers">${j.papers.slice(10).map(paperItem).join("")}</ul></details>` : ""}</div>
      <div class="card"><h3>Datasets found (${j.datasets.length}) ${originTag("search")}</h3>
        <ul class="plain papers">${j.datasets.map(paperItem).join("") || "<li class='muted'>None matched.</li>"}</ul>
        ${j.web.length ? `<h3 style="margin-top:14px">Web (${j.web.length})</h3><ul class="plain papers">${j.web.map(paperItem).join("")}</ul>` : ""}</div>
    </div>`;
  }
  const aiLabel = state.status?.ai?.label || "AI";
  const aiModel = state.status?.ai?.model ? " · " + state.status.ai.model : "";
  html += `<div class="mode">${r.mode === "ai" ? "Final critique written by " + esc(aiLabel) + esc(aiModel) + (j.papers.length ? `, grounded in ${j.papers.length} retrieved papers` : ", not grounded in search results") : "Rules" + (j.papers.length ? " + literature search" : "") + " (no model call)"}</div>`;
  $("#q-out").innerHTML = html;
  $$("[data-rq]", $("#q-out")).forEach((b) => b.addEventListener("click", async () => {
    const cites = (j.papers.filter((p) => p.kind === "systematic_review").slice(0, 3)).map((p) => `${p.title} (${p.url})`).join("; ");
    await api("/api/events", { type: "question", source: "episteme", title: b.dataset.rq,
      detail: `Vetted from: "${q}". Verdict: ${r.verdict.toUpperCase()}. ${r.verdict_reason.replace(/\[[PDW]\d+\]/g, "")}` + (cites ? ` Key reviews: ${cites}` : "") });
    await loadDiary();
    flash(state.events[state.events.length - 1].id);
    toast("Question added to the diary. Next: add a plan with an expectation.");
  }));
}

// ---------------------------------------------------------------- task 3: claims
if ($("#c-demo")) {
  $("#c-demo").addEventListener("click", async () => {
    const { text } = await api("/api/demo-paper");
    if (!text) return toast("This study has no demo paper. Load the hospital-readmission demo from the start screen (click the logo).");
    $("#c-input").value = text;
  });
}
if ($("#c-run")) {
  $("#c-run").addEventListener("click", () => {
    const text = $("#c-input").value.trim();
    if (!text) return toast("Paste some paper text, or load the demo paper");
    $("#c-out").innerHTML = `<div class="empty"><span class="spinner"></span>Analysing claims and cross-referencing with diary...</div>`;
    busy($("#c-run"), async () => renderClaims(await api("/api/claims", { text, use_ai: useAI() })));
  });
}

function renderClaims(r) {
  const counts = { supported: 0, weak: 0, overclaimed: 0, unsupported: 0 };
  r.claims.forEach((c) => (counts[c.status] = (counts[c.status] || 0) + 1));
  const label = { supported: "supported", weak: "weak evidence", overclaimed: "overclaimed", unsupported: "no evidence" };
  const rows = r.claims.map((c) => `<tr>
      <td><span class="section-lbl">${esc(c.id)} · ${esc(c.section)}</span><span class="cert-${c.certainty}">${esc(c.text)}</span></td>
      <td>${c.anchors.length ? c.anchors.map((a) => `<span class="anchor"><span class="lbl ${a.found_in_paper ? "" : "missing"}">${esc(a.ref)}</span>${a.excerpt ? `<span class="ex">“${esc(a.excerpt.length > 140 ? a.excerpt.slice(0, 138) + "…" : a.excerpt)}”</span>` : ""}</span>`).join("") : '<span class="muted">none</span>'}</td>
      <td>${c.diary_links.length ? c.diary_links.map((d) => `<button class="ref" data-ref="${esc(d.id)}" title="${esc(d.title)}">${esc(d.id)}</button>`).join(" ") : '<span class="muted">—</span>'}</td>
      <td><span class="pill s-${c.status}">${label[c.status] || c.status}</span><span class="section-lbl" style="margin-top:4px">wording: ${esc(c.certainty)}</span></td>
      <td>${c.issues.length ? `<ul class="issues">${c.issues.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : '<span class="muted">—</span>'}</td>
    </tr>`).join("");
  $("#c-out").innerHTML = `
    <div class="summary">${Object.entries(counts).map(([k, v]) => `<div class="stat s-${k}"><b>${v}</b>${label[k]}</div>`).join("")}</div>
    <table class="claims"><thead><tr><th style="width:34%">Claim</th><th style="width:26%">Evidence in paper</th><th>Diary</th><th>Status</th><th style="width:22%">Why</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="5" class="empty">No claims detected.</td></tr>`}</tbody></table>
    <div class="grid2" style="margin-top:16px">
      <div class="card"><h3>✓ Checked</h3><ul class="plain">${r.ledger.checked.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div class="card"><h3>? Not verified</h3><ul class="plain">${r.ledger.unverified.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    </div>${modeNote(r)}`;
}

// ---------------------------------------------------------------- boot
(async function boot() {
  $("#curl-snippet").textContent =
    `curl -s ${location.origin}/api/events \\\n  -H 'content-type: application/json' \\\n  -d '{"type":"run","source":"agent",\n       "title":"train v2","result":"AUROC 0.83"}'`;
  await loadStatus();
  await loadDiary();
  await Promise.all([loadConfirms().catch(() => {}), refreshCapture().catch(() => {})]);
  const tab = location.hash.slice(1);
  if (["question", "diary", "claims"].includes(tab)) showTab(tab);
  await openStart().catch(() => {});
  setInterval(async () => { // pick up events from capture hooks, the stitcher and other tools
    const snap = await api("/api/events").catch(() => null);
    if (snap && snap.events) {
      const sig = snap.events.map((e) => `${e.id}:${e.ts}:${e.step}:${e.status || ""}:${e.confirmation || ""}:${e.title}`).join("|");
      if (sig !== state.sig) {
        state.events = snap.events;
        state.sig = sig;
        const open = $$(".ev.open").map((el) => el.dataset.id); // keep expanded cards expanded
        const scrollY = window.scrollY;
        renderTimeline();
        open.forEach((id) => $("#ev-" + id)?.classList.add("open"));
        window.scrollTo(window.scrollX, scrollY);
      }
    }
    loadConfirms().catch(() => {});
    refreshCapture();
  }, 4000);
})();
