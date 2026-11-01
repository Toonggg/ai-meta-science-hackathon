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
"""

import json
import os
import threading
from datetime import datetime, timezone

from demo_data import demo_events

VALID_TYPES = {"plan", "run", "surprise", "pivot", "note", "artifact", "question"}


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

    def delete(self, event_id):
        with self.lock:
            data = self._read()
            data["events"] = [e for e in data["events"] if e["id"] != event_id]
            self._write(data)

    def clear(self):
        with self.lock:
            data = self._read()
            data["events"] = []
            data["next_id"] = 1
            self._write(data)

    def reset_demo(self):
        events = demo_events()
        with self.lock:
            data = self._read()
            data["project"] = "Readmission prediction from clinical notes"
            data["events"] = events
            data["next_id"] = len(events) + 1
            self._write(data)
