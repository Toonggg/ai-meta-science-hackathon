"""Demo studies: recorded sessions in demo/, listed in demo/demos.json.

Every demo is stored and loaded the same way, as a real capture would arrive:
one JSON object per line in a .jsonl session file.

  * Raw capture events ({"kind": "instruction" | "action" | "agent_text" | "commit" | "stop", ...},
    the shape described in episodes.py) go through the raw log, episodes and the stitcher,
    exactly like events from the Claude Code and git hooks.
  * Researcher notes ({"kind": "note", "title": ..., "detail": ..., "about": "last_run"}) are
    what a person types into the diary while the capture runs. They are added once the raw
    events before them have been stitched; "about": "last_run" links the note to the latest run.

demos.json gives each demo an id, a title, a project name, a one-line summary, its session
file and, optionally, a paper (plain text) for Check claims.
"""

import json
import os

from store import RAW_KINDS

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo")
PUBLIC = ("id", "title", "project", "summary")


def _index():
    with open(os.path.join(DEMO_DIR, "demos.json"), encoding="utf-8") as f:
        return json.load(f)


def list_demos():
    return [dict({k: d.get(k, "") for k in PUBLIC}, has_paper=bool(d.get("paper"))) for d in _index()]


def get(demo_id):
    for d in _index():
        if d["id"] == demo_id:
            return d
    raise KeyError(demo_id)


def _read(name):
    with open(os.path.join(DEMO_DIR, os.path.basename(name)), encoding="utf-8") as f:
        return f.read()


def session(demo_id):
    """The demo's lines, in order."""
    lines = []
    for n, line in enumerate(_read(get(demo_id)["session"]).splitlines(), 1):
        if line.strip():
            try:
                lines.append(json.loads(line))
            except ValueError:
                raise ValueError("%s line %d is not valid JSON" % (demo_id, n))
            if lines[-1].get("kind") not in RAW_KINDS | {"note", "question"}:
                raise ValueError("%s line %d has an unknown kind: %r" % (demo_id, n, lines[-1].get("kind")))
    return lines


def chunks(lines):
    """Split a session into ("raw", [...]) and ("notes", [...]) runs, keeping their order."""
    out = []
    for line in lines:
        kind = "notes" if line.get("kind") in ("note", "question") else "raw"
        if out and out[-1][0] == kind:
            out[-1][1].append(line)
        else:
            out.append((kind, [line]))
    return out


def note_event(line, events):
    """The diary event for a note or question line, given the diary as it stands when it is added."""
    t = line.get("kind") or "note"
    ev = {"type": t, "source": "manual" if t == "note" else "episteme", "title": line.get("title", ""), "detail": line.get("detail", "")}
    if line.get("actor"):
        ev["actor"] = line["actor"]
    elif t in ("note", "question"):
        ev["actor"] = "human"
        ev["provenance"] = "stated"
    if line.get("ts"):
        ev["ts"] = line["ts"]
    if line.get("about") == "last_run":
        run = next((e for e in reversed(events) if e.get("type") == "run"), None)
        if run:
            ev["links"] = [run["id"]]
    return ev


def paper(demo_id):
    d = get(demo_id)
    return _read(d["paper"]) if d.get("paper") else ""
