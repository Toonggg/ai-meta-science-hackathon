"""Turn finished episodes into diary events, in the background.

Design decision 2: rules propose, the model confirms. For every final episode:

  1. Rules, instantly, no model:
       plan      from the human instruction (actor human, stated)
       run       for each run that produced a RESULT, or the failure that closed it
                 (actor agent); the hypothesis ledger in diary.py checks it against
                 the plan's expectation, as for manually logged runs
       surprise  when a metric dropped against the previous result (actor system, inferred)
       artifact  for each commit
  2. Model, only for episodes the rules flagged as a possible change of approach
     (change_words / new_direction): is it a pivot, from what to what, and why?
     The model must quote the reason verbatim from the instruction (human) or the
     agent's message (agent). A quote that is not found downgrades the reason to
     inferred, so the model cannot put words in anyone's mouth.

Every flagged episode first gets a pending pivot built from the rules, shown at once.
The model then classifies it in place, without holding the stitcher's lock, so a slow
model never blocks the researcher's Confirm or a Clear. If there is no model, or the
call fails, the pivot stays pending and is retried. The reviewer never waits for the
model: the stitcher runs while the research happens, and reading the diary never calls it.

A stated reason is always the person's own words, verbatim (`detail` = `quote`); the
model's paraphrase is kept in `model_summary` and labelled as the model's.

State (which episodes were stitched into which events) lives in .episteme/stitch.json.
"""

import json
import os
import re
import threading
import time

import diary
import episodes
import llm
import redact
from store import now_iso

POLL_SECONDS = 10       # also re-checks pending episodes
DEBOUNCE_SECONDS = 1.0  # let a burst of hook calls land before segmenting
RETRY_SECONDS = 60      # after a failed model call
PIVOT_FLAGS = ("change_words", "new_direction")

SYSTEM = """You classify one episode of an AI-assisted research session for a provenance log.
An episode starts with the researcher's instruction to an AI agent and holds what the agent ran,
the results, any errors, and the agent's own final message. You also get the previous episode.

Decide whether THIS episode changes the approach compared with the previous one: a different method,
model, data split, dataset, metric or hypothesis. Fixing a bug, retrying, small parameter tuning or
continuing the same plan is NOT a pivot.

Rules:
- Use only the text given. Never invent reasons, numbers or events.
- reason_source: "human" if the researcher's instruction states why; "agent" if only the agent's
  message states why; "none" if nobody stated a reason.
- reason_quote: the exact words, copied verbatim, from the instruction (human) or the agent's
  message (agent) that state the reason. Empty string if reason_source is "none".
- reason: one sentence. If reason_source is "none", give your best inference and start it with "Inferred:".
- title: short, in the form "Switch from <from> to <to>".
- If it is not a pivot, set pivot to false and leave the other fields empty."""

SCHEMA = llm.obj({
    "pivot": {"type": "boolean"},
    "from": llm.STR,
    "to": llm.STR,
    "title": llm.STR,
    "reason": llm.STR,
    "reason_source": llm.enum("human", "agent", "none"),
    "reason_quote": llm.STR,
})


def first_line(text, n=120):
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return line if len(line) <= n else line[:n - 3].rstrip() + "..."


def fmt_result(res):
    parts = ["%s %g" % (k, v) for k, v in (res.get("metrics") or {}).items()]
    ctx = ", ".join("%s=%s" % kv for kv in (res.get("context") or {}).items())
    return " ".join(parts) + (" (%s)" % ctx if ctx else "")


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip(" .\"'")


def find_quote(quote, sources):
    """Return the passage exactly as the person wrote it, or None. The model's quote must be a
    real phrase (3+ words) found in a source, ignoring case and spacing; what is stored is the
    source's own text, never the model's copy of it."""
    words = _norm(quote).split()
    if len(words) < 3 or len(" ".join(words)) < 8:
        return None
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words), re.I)
    for s in sources:
        m = pattern.search(s or "")
        if m:
            return m.group(0)
    return None


def quote_found(quote, sources):
    return find_quote(quote, sources) is not None


def _truthy(v):
    return v is True or (isinstance(v, str) and v.strip().lower() in ("true", "yes"))


class Stitcher:
    def __init__(self, store, raw, state_dir, use_ai=True):
        self.store, self.raw = store, raw
        self.path = os.path.join(state_dir, "stitch.json")
        self.use_ai = use_ai
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.state = self._load()
        self.retry_at = 0.0
        self.last_error = ""
        self.last_run = ""
        self.generation = 0    # bumped by reset(); a model answer from an older generation is dropped
        self.inflight = set()  # episode ids with a model call running, so two passes never ask twice

    # -- state ------------------------------------------------------------------
    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"episodes": {}, "runs": {}}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, self.path)

    def reset(self, also=None):
        """Forget all stitching. `also` (e.g. clearing the diary and raw log) runs under the same
        lock, so a stitching pass can never write into a half-cleared diary. A model answer that
        arrives afterwards sees the new generation and is dropped."""
        with self.lock:
            if also:
                also()
            self.generation += 1
            self.state = {"episodes": {}, "runs": {}}
            self._save()

    def status(self):
        with self.lock:
            eps = list(self.state["episodes"].values())
        return {"stitched": len(eps),
                "pending": sum(1 for s in eps if s.get("status") == "pending"),
                "pivots": sum(1 for s in eps if s.get("pivot")),
                "model": llm.model_name(llm.stitch_model()) if self._ai_ready(ignore_retry=True) else "",
                "last_error": self.last_error, "last_run": self.last_run}

    # -- background loop --------------------------------------------------------
    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="stitcher").start()

    def poke(self):
        self.wake.set()

    def _loop(self):
        while True:
            self.wake.wait(timeout=POLL_SECONDS)
            self.wake.clear()
            time.sleep(DEBOUNCE_SECONDS)
            try:
                self.run_once()
            except Exception as e:  # never let the thread die
                self.last_error = "stitcher: %r" % e

    def human_handled(self, event):
        """The researcher answered a pivot's prompt: never let a later model pass overwrite it."""
        with self.lock:
            st = self.state["episodes"].get(event.get("episode_id") or "")
            if st and st.get("pivot") == event["id"]:
                st["status"] = "done"
                st["human"] = event.get("confirmation")
                self._save()

    def _ai_ready(self, ignore_retry=False):
        return self.use_ai and llm.available() and (ignore_retry or time.time() >= self.retry_at)

    # -- one pass ---------------------------------------------------------------
    def run_once(self):
        """Phase 1 (locked): rules for every new final episode; flagged ones get a pending pivot.
        Phase 2 (no lock): ask the model about pending pivots, so a slow model call never blocks
        Confirm, Clear or status. Phase 3 (locked): apply each answer if it is still wanted."""
        todo = []
        with self.lock:
            gen = self.generation
            raw = self.raw.all()
            raw_by = {e["rid"]: e for e in raw}
            eps = episodes.segment(raw)
            for i, ep in enumerate(eps):
                if not ep["final"]:
                    continue
                prev = eps[i - 1] if i > 0 else None
                st = self.state["episodes"].get(ep["id"])
                if st is None:
                    try:
                        st = self._stitch(ep, prev, raw_by)
                    except Exception as e:  # one broken episode must not stop the others
                        self.state["episodes"][ep["id"]] = {"status": "failed", "error": repr(e)[:300],
                                                            "events": [], "at": now_iso()}
                        self.last_error = "stitching %s: %r" % (ep["id"], e)
                        self._save()
                        continue
                    self._save()  # after every episode, so a crash never re-stitches (duplicates) it
                if st.get("status") == "pending" and ep["id"] not in self.inflight and self._ai_ready():
                    self.inflight.add(ep["id"])
                    todo.append((ep, prev))
            self.last_run = now_iso()

        for ep, prev in todo:
            try:
                answer = self._ask(ep, prev)
            except Exception as e:  # LLMError or anything unexpected: stay pending, retry later
                self.last_error = str(e) if isinstance(e, llm.LLMError) else "model call: %r" % e
                self.retry_at = time.time() + RETRY_SECONDS
                answer = None
            with self.lock:
                self.inflight.discard(ep["id"])
                st = self.state["episodes"].get(ep["id"])
                if answer is None or gen != self.generation or not st or st.get("status") != "pending":
                    continue  # failed, diary cleared meanwhile, or the researcher already answered
                try:
                    self._apply(ep, prev, st, *answer)
                except Exception as e:
                    self.last_error = "applying %s: %r" % (ep["id"], e)
                self._save()

    def _add(self, ev, st, before_id=None):
        added = self.store.add(ev, before_id=before_id)
        st["events"].append({"id": added["id"], "type": added["type"], "status": added.get("status", "")})
        auto = []
        if before_id is None:
            auto, _prompts = diary.after_add(self.store, added)  # hypothesis ledger
            for a in auto:
                st["events"].append({"id": a["id"], "type": a["type"], "status": ""})
        return added, auto

    def _stitch(self, ep, prev, raw_by):
        st = {"status": "done", "events": [], "plan": None, "pivot": None, "at": now_iso()}
        self.state["episodes"][ep["id"]] = st
        base = {"source": "agent", "episode_id": ep["id"]}

        if ep["instruction"]:
            text = ep["instruction"]["text"]
            rid = ep["instruction"]["rid"]
            ev = dict(base, type="plan", title=first_line(text), actor="human", provenance="stated",
                      raw_ids=[rid], ts=raw_by.get(rid, {}).get("ts"))
            if len(text.strip()) > len(ev["title"]):
                ev["detail"] = text.strip()
            expectation = diary.extract_expectation(text)
            if expectation:
                ev["expectation"] = expectation
            plan, _ = self._add(ev, st)
            st["plan"] = plan["id"]

        ledger_hit = set()
        last_run_id = None
        for run in ep["runs"]:
            closing_failure = run["error"] and ep["close_reason"] == "error" and run["rid"] == ep["closed_at"]
            if not run["result"] and not closing_failure:
                continue
            raw_ev = raw_by.get(run["rid"], {})
            ev = dict(base, type="run", title=first_line(raw_ev.get("intent") or run["command"], 100), actor="agent",
                      provenance="stated", raw_ids=[run["rid"]], ts=raw_ev.get("ts"), code=run["command"][:500])
            if run["result"]:
                ev["result"] = fmt_result(run["result"])
                ev["status"] = "ok"
                if run["result"].get("context"):
                    ev["params"] = run["result"]["context"]
            else:
                lines = [l for l in (run["output_tail"] or "").strip().splitlines() if l.strip()]
                ev["result"] = "failed: " + (lines[-1][:200] if lines else "error")
                ev["status"] = "failed"
            added, auto = self._add(ev, st)
            self.state["runs"][run["rid"]] = added["id"]
            last_run_id = added["id"]
            if any(a["type"] == "surprise" for a in auto):
                ledger_hit.add(run["rid"])

        if ep["agent_text"] and last_run_id:
            self.store.update(last_run_id, {"detail": "Agent: " + ep["agent_text"][-1]["text"][:800]})

        for d in ep.get("drops", []):
            if d["after_rid"] in ledger_hit:
                continue  # the plan's own expectation already flagged it
            before_ctx = ", ".join("%s=%s" % kv for kv in d["before_context"].items())
            after_ctx = ", ".join("%s=%s" % kv for kv in d["after_context"].items())
            links = [x for x in (self.state["runs"].get(d["before_rid"]), self.state["runs"].get(d["after_rid"])) if x]
            self._add(dict(base, source="episteme", type="surprise", actor="system", provenance="inferred",
                           title="%s dropped from %g to %g" % (d["metric"], d["before"], d["after"]),
                           detail="Compared with the previous %s result%s. Auto-detected from RESULT lines." % (
                               d["metric"], " (before: %s; now: %s)" % (before_ctx or "-", after_ctx or "-")
                               if (before_ctx or after_ctx) else ""),
                           links=links, raw_ids=[d["before_rid"], d["after_rid"]],
                           ts=raw_by.get(d["after_rid"], {}).get("ts")), st)

        for c in ep["commits"]:
            raw_ev = raw_by.get(c["rid"], {})
            self._add(dict(base, source="git", type="artifact", title="Commit %s: %s" % (c["hash"][:7], first_line(c["text"], 90)),
                           actor=raw_ev.get("actor") if raw_ev.get("actor") in ("human", "agent") else "agent",
                           provenance="stated", raw_ids=[c["rid"]], ts=raw_ev.get("ts"),
                           params={"commit": c["hash"], "files": c["files"][:50]}), st)

        if ep["instruction"] and any(f in ep["flags"] for f in PIVOT_FLAGS):
            self._pending_pivot(ep, prev, st)  # shown at once; the model (if any) classifies it next
        return st

    # -- pivots -----------------------------------------------------------------
    def _trouble(self, prev):
        """Events of the previous episode that a pivot could be reacting to."""
        if not prev:
            return []
        pst = self.state["episodes"].get(prev["id"]) or {}
        return [e["id"] for e in pst.get("events", []) if e["type"] == "surprise" or e.get("status") == "failed"]

    def _pending_pivot(self, ep, prev, st):
        st["status"] = "pending"
        if st.get("pivot"):
            return
        fields = {"type": "pivot", "source": "episteme", "actor": "system", "provenance": "inferred", "pending": True,
                  "title": "Possible change of approach: " + first_line(ep["instruction"]["text"], 80),
                  "detail": "Flagged by rules (%s). Not classified yet; no reason has been checked." % ", ".join(ep["flags"]),
                  "links": self._trouble(prev) + ([st["plan"]] if st.get("plan") else []),
                  "episode_id": ep["id"], "raw_ids": [ep["instruction"]["rid"]]}
        if st.get("plan"):
            fields["ts"] = self.store_event_ts(st["plan"])
        added, _ = self._add(fields, st, before_id=st.get("plan"))
        st["pivot"] = added["id"]

    def store_event_ts(self, eid):
        for e in self.store.events():
            if e["id"] == eid:
                return e.get("ts")
        return None

    def _context(self, ep, prev):
        def side(e):
            if not e:
                return None
            return {
                "instruction": " / ".join(x["text"] for x in e["instructions"] if not x["trivial"]) or None,
                "results": [fmt_result(r["result"]) for r in e["runs"] if r["result"]],
                "failures": [first_line(r["output_tail"].strip().splitlines()[-1] if r["output_tail"].strip() else "error", 200)
                             for r in e["runs"] if r["error"] and not r["result"]],
                "agent_message": e["agent_text"][-1]["text"][:1500] if e["agent_text"] else None,
                "commits": [first_line(c["text"], 100) for c in e["commits"]],
            }
        payload = {"previous_episode": side(prev), "this_episode": side(ep),
                   "rule_flags": ep["flags"], "metric_drops": ep.get("drops", [])}
        return redact.redact_obj(payload)

    def _ask(self, ep, prev):
        """The model call. Runs without the lock. Returns (answer, classified_by)."""
        model = llm.stitch_model()
        out = llm.structured(SYSTEM, json.dumps(self._context(ep, prev), ensure_ascii=False, indent=1), SCHEMA,
                             model=model)
        self.last_error = ""
        return out, {"model": llm.model_name(model), "at": now_iso()}

    def _apply(self, ep, prev, st, out, classified_by):
        """Write the model's answer into the diary. Runs under the lock."""
        if st.get("pivot"):
            current = next((e for e in self.store.events() if e["id"] == st["pivot"]), None)
            if current is None or current.get("confirmation"):
                st["status"] = "done"  # the researcher answered (or deleted it) while the model was working
                return

        human_src = [x["text"] for x in ep["instructions"]]
        agent_src = [a["text"] for a in ep["agent_text"]] + ([a["text"] for a in prev["agent_text"]] if prev else [])
        source = out.get("reason_source") or "none"
        quote = ""
        if source in ("human", "agent"):
            quote = find_quote(out.get("reason_quote") or "", human_src if source == "human" else agent_src) or ""
            if not quote:
                source = "none"  # not found verbatim: nobody is credited with it
        reason = (out.get("reason") or "").strip()[:600]
        if source == "none" and reason and not reason.lower().startswith("inferred"):
            reason = "Inferred: " + reason

        st["decision"] = {"pivot": _truthy(out.get("pivot")), "reason_source": source, "quote": quote[:300] if source != "none" else "",
                          "classified_by": classified_by}
        if not st["decision"]["pivot"]:
            if st.get("pivot"):
                self.store.delete(st["pivot"])
                st["events"] = [e for e in st["events"] if e["id"] != st["pivot"]]
                st["pivot"] = None
            st["status"] = "done"
            return

        actor = {"human": "human", "agent": "agent"}.get(source, "system")
        title = first_line(out.get("title") or "Switch from %s to %s" % (out.get("from") or "?", out.get("to") or "?"), 120)
        # A stated reason is the person's (or agent's) own words, verbatim. The model's paraphrase is
        # kept apart and labelled as the model's, so nobody is credited with words they did not write.
        detail = quote.strip()[:600] if source != "none" else (reason or "(no reason given)")
        fields = {"type": "pivot", "source": "agent" if actor != "system" else "episteme", "actor": actor,
                  "provenance": "stated" if actor != "system" else "inferred",
                  "title": title, "detail": detail,
                  "links": self._trouble(prev) + ([st["plan"]] if st.get("plan") else []),
                  "episode_id": ep["id"], "raw_ids": [x["rid"] for x in ep["instructions"]] +
                  ([ep["agent_text"][-1]["rid"]] if source == "agent" and ep["agent_text"] else []),
                  "classified_by": classified_by, "needs_confirmation": actor != "human"}
        if source != "none":
            fields["quote"] = quote[:300]
            if reason:
                fields["model_summary"] = reason
        if st.get("pivot"):
            self.store.update(st["pivot"], fields, remove=("pending",) if source != "none" else ("pending", "model_summary"))
        else:
            if st.get("plan"):
                fields["ts"] = self.store_event_ts(st["plan"])
            added, _ = self._add(fields, st, before_id=st.get("plan"))
            st["pivot"] = added["id"]
        st["status"] = "done"
