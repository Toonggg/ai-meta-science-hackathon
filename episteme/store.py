"""Local-first diary storage: one JSON file in .episteme/, guarded by a lock.

Event shape (all fields optional except id/type/title/ts):
    id          "E7" - stable, never reused
    ts          ISO timestamp
    type        plan | run | surprise | pivot | note | artifact | question
    title       one line
    detail      free text (the "why", the error, the context)
    source      chat | colab | github | manual | agent | episteme
    provenance  stated (a human/agent said it at the time) | inferred (reconstructed later)
    expectation pre-stated expectation, e.g. "AUROC >= 0.75" (plans only)
    result      observed outcome, e.g. "AUROC 0.54 (5-fold CV)" (runs only)
    status      ok | failed
    code, params, data {name, version, hash}, links [event ids]

Fields added for automatic capture:
    actor        who stated it: human | agent | system (episteme's own rules)
    confirmed_by "human" when a person confirmed an agent-stated reason with one click
    episode_id   the episode (see episodes.py) this event was stitched from
    raw_ids      raw events (raw.jsonl) that are the evidence for this event
    classified_by {"model": ..., "at": ...} when a model wrote or classified it

Raw capture lives in a separate append-only file (raw.jsonl, see RawLog) so the
diary itself stays small: it holds decisions, raw.jsonl holds everything.
"""

import json
import os
import threading
from datetime import datetime, timezone

from demo_data import demo_events

VALID_TYPES = {"plan", "run", "surprise", "pivot", "note", "artifact", "question"}
VALID_ACTORS = {"human", "agent", "system"}
ACTOR_FOR_SOURCE = {"manual": "human", "episteme": "system", "agent": "agent"}
RAW_KINDS = {"instruction", "action", "agent_text", "commit", "stop"}


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Diary:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        if not os.path.exists(path):
            self._write({"project": "Readmission prediction from clinical notes", "next_id": 1, "events": []})
            self.reset_demo()

    # -- low level -------------------------------------------------------
    def _read(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    # -- public ----------------------------------------------------------
    def snapshot(self):
        with self.lock:
            data = self._read()
        for i, ev in enumerate(data["events"]):
            ev["step"] = i + 1
        return data

    def events(self):
        return self.snapshot()["events"]

    def add(self, ev, before_id=None):
        with self.lock:
            data = self._read()
            ev = {k: v for k, v in ev.items() if v not in (None, "", [], {})}
            ev["id"] = "E%d" % data["next_id"]
            data["next_id"] += 1
            ev.setdefault("ts", now_iso())
            ev.setdefault("source", "manual")
            ev.setdefault("provenance", "stated")
            if ev.get("actor") not in VALID_ACTORS:
                ev.pop("actor", None)
                if ev["source"] in ACTOR_FOR_SOURCE:
                    ev["actor"] = ACTOR_FOR_SOURCE[ev["source"]]
            if ev.get("type") not in VALID_TYPES:
                ev["type"] = "note"
            ev["title"] = (ev.get("title") or "(untitled)").strip()
            idx = len(data["events"])
            if before_id:
                for i, e in enumerate(data["events"]):
                    if e["id"] == before_id:
                        idx = i
                        break
            data["events"].insert(idx, ev)
            self._write(data)
        return ev

    def update(self, event_id, fields, remove=()):
        """Change fields of one event in place (keeps its id and position)."""
        with self.lock:
            data = self._read()
            for e in data["events"]:
                if e["id"] == event_id:
                    e.update({k: v for k, v in fields.items() if k not in ("id", "step")})
                    for k in remove:
                        e.pop(k, None)
                    self._write(data)
                    return e
        raise KeyError(event_id)

    def delete(self, event_id):
        with self.lock:
            data = self._read()
            data["events"] = [e for e in data["events"] if e["id"] != event_id]
            self._write(data)

    def clear(self, project=None):
        with self.lock:
            data = self._read()
            data["events"] = []
            data["next_id"] = 1
            if project and project.strip():
                data["project"] = project.strip()[:120]
            self._write(data)

    def reset_demo(self):
        events = demo_events()
        for e in events:  # the demo was logged by hand: everything is the researcher's except Episteme's own flags
            e.setdefault("actor", "system" if e.get("source") == "episteme" else "human")
        with self.lock:
            data = self._read()
            data["project"] = "Readmission prediction from clinical notes"
            data["events"] = events
            data["next_id"] = len(events) + 1
            self._write(data)


class RawLog:
    """Append-only raw capture log: one JSON object per line in raw.jsonl.

    Never rewritten, so a crash can at worst lose the line being written.
    Raw ids ("R1", "R2", ...) are stable and never reused.
    """

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self._next = self._count() + 1

    def _count(self):
        if not os.path.exists(self.path):
            return 0
        n = 0
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    n += 1
        return n

    def add(self, ev):
        ev = {k: v for k, v in ev.items() if v not in (None, "", [], {})}
        if ev.get("kind") not in RAW_KINDS:
            raise ValueError("raw event kind must be one of: %s" % ", ".join(sorted(RAW_KINDS)))
        ev.pop("rid", None)
        ev.setdefault("ts", now_iso())
        ev.setdefault("source", "agent")
        with self.lock:
            ev["rid"] = "R%d" % self._next
            self._next += 1
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    def all(self):
        with self.lock:
            if not os.path.exists(self.path):
                return []
            out = []
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue  # a torn last line from a crash: skip it
            return out

    def get(self, rids):
        want = set(rids)
        return [e for e in self.all() if e["rid"] in want]

    def clear(self):
        with self.lock:
            if os.path.exists(self.path):
                os.remove(self.path)
            self._next = 1
