"""Group raw captured activity into episodes, and flag the ones worth a closer look.

Raw events come from capture tools (agent hook, git hook) via POST /api/raw and are
stored append-only in .episteme/raw.jsonl. A raw event looks like:

    rid        "R12"            assigned by the store, never reused
    ts         ISO timestamp
    source     agent | git | notebook | manual
    session    capture session id (one agent session, one repo, ...)
    kind       instruction      a human message to the agent        (actor human)
               action           a tool call by the agent             (actor agent)
               agent_text       the agent's own words, e.g. its explanation (actor agent)
               commit           a git commit                         (actor human or agent)
               stop             the agent finished its turn
    text       instruction / agent text / commit message
    tool       tool name for actions (Bash, Edit, Write, Read, ...)
    command    shell command for Bash actions
    files      files touched
    output     tail of the tool output (already redacted by the hook)
    error      true if the action failed
    commit     commit hash (commits only)

Segmentation rules (design decision 1, "A + D"):

  * A non-trivial human instruction opens a new episode.
  * Trivial instructions ("yes", "continue", "fix that") join the open episode.
  * A run that prints RESULT lines, a real run error, or a commit closes the
    episode's activity. Agent text, commits, stops and reads/searches right after
    it still belong to it (the agent usually inspects and explains a result after
    printing it). The next run or edit starts a new episode.
  * A run error followed within RETRY_WINDOW actions by a re-run of the same
    command is a quick fix, not a boundary.
  * MAX_SIGNIFICANT runs/edits without any boundary split the episode ("cap").

An episode is final once something after it has started a new episode, or once
the agent stopped after its closing event. Only final episodes are stitched.
segment() is a pure function of the raw list, and boundaries need at most
RETRY_WINDOW events of look-ahead, so earlier episodes and their ids do not
change as more raw events arrive.

Flags (design decision 2, rules propose): failure, metric_drop, change_words,
new_direction. The stitcher sends only flagged episodes to the model.
"""

import re

RETRY_WINDOW = 2
MAX_SIGNIFICANT = 30

RESULT_LINE = re.compile(r"^\s*RESULT\b(.*)$", re.M)
KV = re.compile(r"([A-Za-z_][\w.\-@]*)\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)")

ACK = re.compile(r"^\s*(yes|yep|yeah|ok|okay|sure|continue|go on|go ahead|proceed|do it|do that|sounds good|"
                 r"looks good|lgtm|thanks|thank you|great|perfect|fix (it|that|this|the error|the bug)|try again|"
                 r"retry|again)\b", re.I)
MAX_ACK_WORDS = 8

CHANGE_WORDS = re.compile(r"\b(instead|switch(ing)?|replace|abandon|drop|rather than|alternative|pivot|"
                          r"change (the )?(approach|method|model|plan|split)|re-?split|re-?do|start over|"
                          r"different (approach|method|model)|stop using|no longer)\b", re.I)

SCRIPT = re.compile(r"(^|[\s;&|(])(python[\d.]*|Rscript|julia|bash|sh|uv run|poetry run|jupyter nbconvert)\s+"
                    r"(-m\s+\S+|\S+\.(py|R|r|jl|sh|ipynb))")
NOT_RUN = re.compile(r"^\s*(pip|pip3|conda|mamba|brew|apt|apt-get|npm|uv pip|python[\d.]* -m pip)\b")

LOWER_IS_BETTER = re.compile(r"(loss|error|err|rmse|mse|mae|mape|perplexity|ppl|time|latency|fpr|fdr|brier|nll)",
                             re.I)


# -- classifying single raw events ---------------------------------------------

def parse_results(output):
    """RESULT spearman=0.71 split=random -> {"metrics": {"spearman": 0.71}, "context": {"split": "random"}}."""
    metrics, context = {}, {}
    for line in RESULT_LINE.findall(output or ""):
        for k, v in KV.findall(line):
            v = v.strip("\"'")
            try:
                metrics[k] = float(v.rstrip("%"))
            except ValueError:
                context[k] = v
    return {"metrics": metrics, "context": context} if (metrics or context) else None


def is_trivial(text):
    t = (text or "").strip()
    if not t:
        return True
    return len(t.split()) <= MAX_ACK_WORDS and bool(ACK.match(t)) and not CHANGE_WORDS.search(t)


def is_run(ev):
    if ev.get("kind") != "action":
        return False
    if parse_results(ev.get("output")):
        return True
    cmd = ev.get("command") or ""
    return bool(cmd) and not NOT_RUN.match(cmd) and bool(SCRIPT.search(cmd))


def is_significant(ev):
    """Counts toward the cap: runs and file changes, not reads or searches."""
    return is_run(ev) or (ev.get("kind") == "action" and (ev.get("tool") in ("Edit", "Write", "MultiEdit", "NotebookEdit")))


def run_key(ev):
    """What makes two runs 'the same command' for the quick-fix rule."""
    m = SCRIPT.search(ev.get("command") or "")
    return m.group(3) if m else (ev.get("command") or "").strip()


# -- segmentation --------------------------------------------------------------

def _quick_fix(raw, i):
    """True if the failed run at raw[i] is re-run within RETRY_WINDOW later actions."""
    key = run_key(raw[i])
    seen = 0
    for ev in raw[i + 1:]:
        if ev.get("kind") == "stop" or (ev.get("kind") == "instruction" and not is_trivial(ev.get("text"))):
            return False  # the agent handed back, or the human moved on: the failure stands
        if ev.get("kind") != "action":
            continue
        seen += 1
        if is_run(ev) and run_key(ev) == key:
            return True
        if seen >= RETRY_WINDOW:
            return False
    return None  # not enough look-ahead yet


def _new(raw_ev, opened_by):
    return {"id": "EP-" + raw_ev["rid"], "raw_ids": [], "opened_by": opened_by, "instruction": None,
            "instructions": [], "runs": [], "commits": [], "agent_text": [], "files": [], "actions": 0,
            "significant": 0, "close_reason": None, "closed_at": None, "stopped_after_close": False,
            "final": False, "start_ts": raw_ev.get("ts"), "end_ts": raw_ev.get("ts"),
            "sessions": [], "flags": []}


def _add(ep, ev):
    ep["raw_ids"].append(ev["rid"])
    ep["end_ts"] = ev.get("ts") or ep["end_ts"]
    if ev.get("session") and ev["session"] not in ep["sessions"]:
        ep["sessions"].append(ev["session"])
    k = ev.get("kind")
    if k == "instruction":
        ep["instructions"].append({"rid": ev["rid"], "text": ev.get("text", ""), "trivial": is_trivial(ev.get("text"))})
        if ep["instruction"] is None and not is_trivial(ev.get("text")):
            ep["instruction"] = {"rid": ev["rid"], "text": ev.get("text", "")}
    elif k == "action":
        ep["actions"] += 1
        if is_significant(ev):
            ep["significant"] += 1
        for f in ev.get("files") or []:
            if f not in ep["files"]:
                ep["files"].append(f)
        if is_run(ev):
            ep["runs"].append({"rid": ev["rid"], "command": ev.get("command", ""), "error": bool(ev.get("error")),
                               "result": parse_results(ev.get("output")),
                               "output_tail": (ev.get("output") or "")[-600:]})
    elif k == "agent_text":
        ep["agent_text"].append({"rid": ev["rid"], "text": ev.get("text", "")})
    elif k == "commit":
        ep["commits"].append({"rid": ev["rid"], "hash": ev.get("commit", ""), "text": ev.get("text", ""),
                              "files": ev.get("files") or []})


def segment(raw):
    """Pure function: list of raw events (in arrival order) -> list of episodes."""
    episodes = []
    cur = None
    for i, ev in enumerate(raw):
        k = ev.get("kind")
        opens = k == "instruction" and not is_trivial(ev.get("text"))
        # After a closing event, agent text, commits, stops and reads/searches (the agent looking at
        # what happened) still belong to it. The next run or edit starts a new episode.
        tail_ok = k in ("agent_text", "commit", "stop") or (k == "instruction" and not opens) or \
            (k == "action" and not is_significant(ev))
        if cur is None or opens or (cur["close_reason"] and not tail_ok) or \
                (cur["close_reason"] and k == "instruction" and not opens and cur["stopped_after_close"]):
            if cur is not None:
                if not cur["close_reason"]:
                    cur["close_reason"] = "next_instruction" if opens else "next_activity"
                cur["final"] = True
                episodes.append(cur)
            cur = _new(ev, "instruction" if opens else ("continuation" if k == "instruction" else "activity"))
        _add(cur, ev)

        if cur["close_reason"]:
            if k == "stop":
                cur["stopped_after_close"] = True
                cur["final"] = True
            continue
        if k == "commit":
            cur["close_reason"], cur["closed_at"] = "commit", ev["rid"]
        elif is_run(ev) and parse_results(ev.get("output")):
            cur["close_reason"], cur["closed_at"] = "result", ev["rid"]
        elif is_run(ev) and ev.get("error"):
            if _quick_fix(raw, i) is False:
                cur["close_reason"], cur["closed_at"] = "error", ev["rid"]
        elif cur["significant"] >= MAX_SIGNIFICANT and is_significant(ev):
            cur["close_reason"], cur["closed_at"] = "cap", ev["rid"]
    if cur is not None:
        episodes.append(cur)
    _flag(episodes)
    return episodes


# -- flags (rules propose candidates; the stitcher's model decides) --------------

def _higher_is_better(metric):
    return not LOWER_IS_BETTER.search(metric)


def _flag(episodes):
    last_metric = {}   # metric name -> (value, episode id)
    for ep in episodes:
        flags = []
        if ep["close_reason"] == "error":
            flags.append("failure")
        instr = " ".join(x["text"] for x in ep["instructions"])
        if CHANGE_WORDS.search(instr):
            flags.append("change_words")
        drops = []
        for run in ep["runs"]:
            res = run.get("result") or {}
            for name, val in (res.get("metrics") or {}).items():
                prev = last_metric.get(name)
                if prev is not None:
                    worse = val < prev[0] if _higher_is_better(name) else val > prev[0]
                    if worse:
                        drops.append({"metric": name, "before": prev[0], "after": val, "before_episode": prev[1]})
                last_metric[name] = (val, ep["id"])
        if drops:
            flags.append("metric_drop")
            ep["drops"] = drops
        # A fresh instruction right after a flagged episode may be a change of direction.
        if ep["opened_by"] == "instruction" and episodes.index(ep) > 0:
            prev_ep = episodes[episodes.index(ep) - 1]
            if any(f in prev_ep["flags"] for f in ("failure", "metric_drop")):
                flags.append("new_direction")
        ep["flags"] = flags
