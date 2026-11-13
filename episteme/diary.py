"""Task 2: the provenance diary's logic.

- Hypothesis ledger: a plan's pre-stated expectation is checked against the next
  run's result; contradictions become first-class Surprise events.
- Pivot micro-prompts: a new plan after a surprise/failure asks "why?" in the
  moment, so the rationale is *stated*, not reconstructed later.
- Ask the log: answers reviewer questions citing only diary events.
"""

import json
import math
import re

import llm

OPS = {">=": lambda a, b: a >= b, "≥": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "≤": lambda a, b: a <= b,
       ">": lambda a, b: a > b, "<": lambda a, b: a < b, "=": lambda a, b: abs(a - b) < 1e-9}
EXPECT = re.compile(r"(?P<metric>[A-Za-z][\w@\-]*)\s*(?P<op>>=|<=|≥|≤|>|<|=)\s*(?P<val>-?\d*\.?\d+)")


EXPECT_CUE = re.compile(r"\b(expect\w*|target|aim(ing)? for|hypothes\w+|predict\w*|goal|hope|should (reach|get|"
                        r"be|beat|exceed|hit)|at least|success means)\b", re.I)


def extract_expectation(text):
    """The expectation stated in free text (e.g. a captured instruction), or None.
    Only a comparison after a cue word counts, and never a plain "=": "lr=0.001" or
    "significant at p<0.05" in a sentence without a cue are settings, not expectations."""
    for cue in EXPECT_CUE.finditer(text or ""):
        window = text[cue.end():cue.end() + 80]
        for m in EXPECT.finditer(window):
            if m.group("op") != "=":
                return m.group(0)
    return None


def check_expectation(expectation, result):
    """Return (metric, op, expected, observed, holds) or None if not comparable."""
    m = EXPECT.search(expectation or "")
    if not m:
        return None
    metric = m.group("metric")
    # Whole-word match, so an expectation on "p" never reads the number after "spearman".
    r = re.search(r"(?<![\w@\-])" + re.escape(metric) + r"(?![\w@\-])\D{0,20}?(-?\d*\.\d+|-?\d+)", result or "", re.I)
    if not r:
        return None
    expected, observed = float(m.group("val")), float(r.group(1))
    return metric, m.group("op"), expected, observed, OPS[m.group("op")](observed, expected)


def last(events, pred):
    for ev in reversed(events):
        if pred(ev):
            return ev
    return None


def after_add(store, ev):
    """Side effects of adding an event. Returns (auto_events, prompts)."""
    events = store.events()
    auto, prompts = [], []
    idx = next(i for i, e in enumerate(events) if e["id"] == ev["id"])
    before = events[:idx]

    if ev["type"] == "run" and ev.get("result"):
        plan = last(before, lambda e: e["type"] in ("plan", "pivot") and e.get("expectation"))
        if plan:
            chk = check_expectation(plan["expectation"], ev["result"])
            if chk and not chk[4]:
                metric, op, exp, obs, _ = chk
                auto.append(store.add({
                    "type": "surprise", "source": "episteme", "provenance": "inferred",
                    "title": "Expectation contradicted: expected %s %s %g, observed %g" % (metric, op, exp, obs),
                    "detail": "Auto-detected by the hypothesis ledger: the result of %s falls short of the expectation stated in %s."
                              % (ev["id"], plan["id"]),
                    "links": [plan["id"], ev["id"]],
                }))
            elif chk:
                prompts.append({"kind": "info", "message": "Expectation in %s held (%s %s %g, observed %g)."
                                % (plan["id"], chk[0], chk[1], chk[2], chk[3])})
    if ev["type"] == "run" and ev.get("status") == "failed" and not auto:
        prompts.append({"kind": "info", "message": "Run marked as failed. If you change approach next, Episteme will ask why."})

    if ev["type"] == "plan":
        # Was there trouble since the last plan/pivot, without a pivot explaining it?
        since = []
        for e in reversed(before):
            if e["type"] in ("plan", "pivot"):
                break
            since.append(e)
        trouble = [e for e in since if e["type"] == "surprise" or e.get("status") == "failed"]
        if trouble:
            prompts.append({
                "kind": "pivot_why",
                "plan_id": ev["id"],
                "links": [e["id"] for e in reversed(trouble)],
                "message": "This new plan follows %s. That looks like a change of direction. Why? One line is enough; "
                           "it will be recorded as a stated rationale." % ", ".join(
                               "%s (%s)" % (e["id"], e["title"] if len(e["title"]) <= 90 else e["title"][:88] + "...")
                               for e in reversed(trouble)),
            })
    return auto, prompts


def who(e):
    """Plain-language attribution of an event's statement, used by ask, exports and the UI.

    actor human / agent / system and provenance stated / inferred, plus the
    researcher's one-click answer to a confirmation prompt (design decision 3).
    """
    actor, prov, conf = e.get("actor"), e.get("provenance"), e.get("confirmation")
    if conf == "edited":
        return "stated by the researcher" + (" (rewritten from a proposal)" if e.get("proposed_reason") else "")
    if actor == "human":
        base = "stated by the researcher"
    elif actor == "agent":
        base = "stated by the AI agent"
    elif actor == "system" or prov == "inferred":
        base = "inferred by Episteme"
    else:
        base = "stated at the time" if prov == "stated" else "inferred afterwards"
    if conf == "confirmed":
        return base + ", confirmed by the researcher"
    if conf == "skipped":
        return base + ", not confirmed (researcher skipped)"
    if e.get("pending"):
        return base + ", not classified yet"
    return base


def needs_answer(e):
    """Pivots the researcher should confirm, edit or skip."""
    return e.get("type") == "pivot" and not e.get("confirmation") and \
        bool(e.get("needs_confirmation") or e.get("pending"))


def prompts(events):
    out = []
    for e in events:
        if needs_answer(e):
            out.append({"id": e["id"], "step": e.get("step"), "title": e["title"], "reason": e.get("detail", ""),
                        "quote": e.get("quote", ""), "model_summary": e.get("model_summary", ""),
                        "who": who(e), "pending": bool(e.get("pending")),
                        # A pending pivot has no checked reason yet, so there is nothing to confirm.
                        "actions": ["edit", "skip"] if e.get("pending") else ["confirm", "edit", "skip"]})
    return out


def confirm(store, event_id, action, reason=""):
    """The researcher's one-click answer: confirm keeps the agent's reason and records approval,
    edit replaces it with the researcher's own words, skip records that nobody confirmed it."""
    ev = next((e for e in store.events() if e["id"] == event_id), None)
    if ev is None:
        raise KeyError(event_id)
    if ev.get("type") != "pivot":
        raise ValueError("only pivots can be confirmed")
    from store import now_iso
    stamp = {"confirmed_by": "human", "confirmed_at": now_iso(), "needs_confirmation": False}
    if action == "confirm":
        if ev.get("pending"):
            raise ValueError("this pivot has no checked reason yet; edit or skip it")
        return store.update(event_id, dict(stamp, confirmation="confirmed"))
    if action == "edit":
        reason = (reason or "").strip()
        if not reason:
            raise ValueError("an edited reason cannot be empty")
        fields = dict(stamp, confirmation="edited", detail=reason, actor="human", provenance="stated")
        if ev.get("detail") and not ev.get("pending"):  # a pending pivot's detail is only the rules' placeholder
            fields["proposed_reason"] = ev["detail"]  # keep what was proposed, for the audit trail
        if ev.get("title", "").startswith("Possible change of approach"):
            fields["title"] = ev["title"].replace("Possible change of approach", "Change of approach", 1)
        return store.update(event_id, fields, remove=("pending", "quote"))
    if action == "skip":
        return store.update(event_id, {"confirmation": "skipped", "needs_confirmation": False,
                                       "skipped_at": now_iso()})
    raise ValueError("action must be confirm, edit or skip")


def record_pivot(store, plan_id, links, reason, skipped):
    events = store.events()
    plan = next((e for e in events if e["id"] == plan_id), None)
    if plan is None:
        raise KeyError(plan_id)
    if skipped:
        trouble = [e for e in events if e["id"] in links]
        reason = "No rationale given. Inferred from the log only: the change followed %s." % "; ".join(
            "%s: %s" % (e["id"], e["title"]) for e in trouble)
    return store.add({
        "type": "pivot", "source": "episteme" if skipped else "manual",
        "provenance": "inferred" if skipped else "stated",
        "title": "Switch to: " + plan["title"],
        "detail": reason,
        "links": list(links),
        "ts": plan["ts"],
    }, before_id=plan_id)


# -- Ask the log ------------------------------------------------------------

STOP = set("the a an of to in on at and or for why what did they we was were is are how this that with from by it "
           "change changed approach step steps do does switch switched drop dropped move moved use used try tried go went "
           "abandon abandoned pick picked decide decided".split())


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP and len(w) > 1}


def ev_text(e):
    data = e.get("data") or {}
    extra = (" dataset data version %s %s %s" % (data.get("name", ""), data.get("version", ""), data.get("hash", ""))) if data else ""
    return " ".join(str(e.get(k, "")) for k in ("type", "title", "detail", "result", "expectation", "code", "source")) + \
        " " + json.dumps(e.get("params", {})) + extra


def cite(e):
    return "[%s]" % e["id"]


def explain_pivot(pv, events):
    by_id = {e["id"]: e for e in events}
    lines = ["**Step %d (%s) is a pivot: %s.**" % (pv["step"], pv["id"], pv["title"])]
    tag = who(pv)
    if pv.get("provenance") == "inferred" and pv.get("confirmation") != "edited":
        tag = "**%s**: nobody stated it at the time. Treat it with caution" % tag
    lines.append("Reason (%s) %s: %s" % (tag, cite(pv), pv.get("detail", "(none recorded)")))
    trig = [by_id[i] for i in pv.get("links", []) if i in by_id]
    if trig:
        lines.append("What triggered it:")
        for t in trig:
            extra = (": " + t["result"]) if t.get("result") else ""
            lines.append("- %s %s%s" % (cite(t), t["title"], extra))
    after = [e for e in events if pv["id"] in e.get("links", [])]
    if after:
        lines.append("What happened next:")
        for a in after:
            extra = (": " + a["result"]) if a.get("result") else ""
            lines.append("- %s %s%s" % (cite(a), a["title"], extra))
    return "\n".join(lines)


def ask_heuristic(question, events):
    m = re.search(r"\bstep\s*(\d+)", question, re.I) or re.search(r"\bE(\d+)\b", question)
    if m:
        n = int(m.group(1))
        target = None
        if m.group(0).lower().startswith("step"):
            target = events[n - 1] if 0 < n <= len(events) else None
        else:
            target = next((e for e in events if e["id"] == "E%d" % n), None)
        if not target:
            return "The log has no %s. It has %d steps." % (m.group(0), len(events))
        if target["type"] == "pivot":
            return explain_pivot(target, events)
        # A plan or run: find the pivot that explains it.
        pv = next((e for e in events if e["type"] == "pivot" and (target["id"] in e.get("links", []) or
                                                                  e["id"] in target.get("links", []))), None)
        head = "Step %d %s is a %s: %s." % (target["step"], cite(target), target["type"], target["title"])
        if pv:
            return head + "\n\n" + explain_pivot(pv, events)
        detail = target.get("detail") or target.get("result") or ""
        return head + ("\n\n" + detail if detail else "") + "\n\nNo pivot is linked to this step in the log."

    q = words(question)
    docs = [words(ev_text(e)) for e in events]
    idf = {w: math.log((1 + len(events)) / (1 + sum(w in d for d in docs))) + 1 for w in q}
    scored = sorted(((sum(idf[w] for w in q & d), e) for d, e in zip(docs, events)), key=lambda x: -x[0])
    scored = [(s, e) for s, e in scored if s > 0]
    if not scored:
        return "The log contains nothing about that. (Episteme only answers from recorded events.)"
    best = scored[0][1]
    pivots = [e for _, e in scored if e["type"] == "pivot"]
    if re.search(r"\b(why|reason|rationale)\b", question, re.I) and pivots:
        return explain_pivot(pivots[0], events)
    if best["type"] == "pivot":
        pv = best if best["type"] == "pivot" else next(
            (e for e in events if e["type"] == "pivot" and (best["id"] in e.get("links", []) or e["id"] in best.get("links", []))), None)
        if pv:
            return explain_pivot(pv, events)
    lines = ["Most relevant events in the log:"]
    for s, e in scored[:3]:
        d = e.get("data")
        lines.append("- %s step %d, %s: %s%s%s" % (cite(e), e["step"], e["type"], e["title"],
                                                 ("; result: " + e["result"]) if e.get("result") else "",
                                                 ("; data: %s v%s (%s)" % (d.get("name"), d.get("version"), d.get("hash")))
                                                 if d else ""))
    return "\n".join(lines)


ASK_SYSTEM = """You answer a reviewer's questions about a research project using ONLY the provenance log provided.
Rules:
- Cite every factual statement with the event id in square brackets, e.g. [E4]. Refer to steps by number when useful.
- Each event has a "who" field saying who stated it: the researcher, the AI agent (possibly confirmed by the researcher), or inferred by Episteme. Say whose statement your answer rests on. Keep the researcher's decisions apart from the agent's proposals, and flag inferred rationale as less reliable.
- If the log does not contain the answer, say so plainly. Do not speculate beyond the log.
- Be concise: a short paragraph or a few bullets, in Markdown."""


def ask(question, events, use_ai):
    if use_ai and llm.available():
        drop = ("code", "raw_ids", "classified_by", "needs_confirmation", "confirmed_at", "skipped_at", "episode_id")
        compact = [dict({k: v for k, v in e.items() if k not in drop}, who=who(e)) for e in events]
        try:
            return {"mode": "ai", "answer": llm.text(ASK_SYSTEM, "LOG:\n%s\n\nQUESTION: %s" % (
                json.dumps(compact, indent=1, ensure_ascii=False), question))}
        except llm.LLMError as e:
            return {"mode": "heuristic", "answer": ask_heuristic(question, events), "ai_error": str(e)}
    return {"mode": "heuristic", "answer": ask_heuristic(question, events)}
