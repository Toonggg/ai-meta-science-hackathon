"""Saved studies: every study notebook keeps its own folder, so starting a new one or loading a
demo never deletes another.

    .episteme/studies/<id>/diary.json   the diary (store.Diary)
    .episteme/studies/<id>/raw.jsonl    its raw capture (store.RawLog)
    .episteme/studies/<id>/stitch.json  its stitcher state (stitcher.Stitcher)
    .episteme/current                   the id of the open study

One study is open at a time; capture hooks and the UI read and write the open one. The server
switches studies by pointing its Diary, RawLog and Stitcher at another folder (server.open_study).
"""

import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime

FILES = ("diary.json", "raw.jsonl", "stitch.json")
ID_RE = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")


class Studies:
    def __init__(self, root):
        self.root = root
        self.dir = os.path.join(root, "studies")
        self.current_file = os.path.join(root, "current")
        self.lock = threading.Lock()
        os.makedirs(self.dir, exist_ok=True)
        self._migrate()

    # -- paths ------------------------------------------------------------------
    def path(self, sid):
        if not isinstance(sid, str) or not ID_RE.match(sid):
            raise KeyError(sid)
        return os.path.join(self.dir, sid)

    def exists(self, sid):
        try:
            return os.path.isfile(os.path.join(self.path(sid), "diary.json"))
        except KeyError:
            return False

    # -- the open study ---------------------------------------------------------
    def current(self):
        try:
            with open(self.current_file, encoding="utf-8") as f:
                sid = f.read().strip()
        except OSError:
            return None
        return sid if self.exists(sid) else None

    def set_current(self, sid):
        self.path(sid)
        tmp = self.current_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(sid)
        os.replace(tmp, self.current_file)

    def ensure_current(self):
        """The open study, else the most recently used one, else a new empty one."""
        sid = self.current()
        if not sid:
            listed = self.list(include_blank=True)
            sid = listed[0]["id"] if listed else self.create()
            self.set_current(sid)
        return sid

    # -- create / list / delete -------------------------------------------------
    def create(self, project="", demo=None):
        with self.lock:
            while True:
                sid = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
                if not os.path.exists(self.path(sid)):
                    break
            os.makedirs(self.path(sid))
        _write_json(os.path.join(self.path(sid), "diary.json"),
                    {"project": (project or "").strip()[:120], "demo": demo, "next_id": 1, "events": []})
        return sid

    def info(self, sid):
        path = self.path(sid)
        try:
            with open(os.path.join(path, "diary.json"), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        mtimes = [os.path.getmtime(os.path.join(path, n)) for n in FILES if os.path.exists(os.path.join(path, n))]
        raw = os.path.join(path, "raw.jsonl")
        return {"id": sid, "project": data.get("project") or "", "demo": data.get("demo"),
                "events": len(data.get("events") or []),
                "has_raw": os.path.exists(raw) and os.path.getsize(raw) > 0,
                "created": datetime.strptime(sid[:15], "%Y%m%d-%H%M%S").isoformat(timespec="minutes"),
                "modified": datetime.fromtimestamp(max(mtimes)).isoformat(timespec="minutes") if mtimes else ""}

    def is_blank(self, sid):
        i = self.info(sid)
        return bool(i) and not (i["project"] or i["events"] or i["has_raw"] or i["demo"])

    def list(self, include_blank=False):
        """Saved studies, most recently changed first. Blank ones (no name, no entries, no
        capture) are left out: they are the empty notebook a fresh install opens with."""
        out = []
        for name in os.listdir(self.dir):
            if ID_RE.match(name):
                i = self.info(name)
                if i and (include_blank or i["project"] or i["events"] or i["has_raw"] or i["demo"]):
                    out.append(i)
        return sorted(out, key=lambda i: (i["modified"], i["id"]), reverse=True)

    def find_demo(self, demo_id):
        """The most recent saved copy of a demo, if there is one."""
        return next((i["id"] for i in self.list() if i["demo"] == demo_id), None)

    def delete(self, sid):
        if sid == self.current():
            raise ValueError("the open study cannot be deleted; open another one first")
        if not self.exists(sid):
            raise KeyError(sid)
        shutil.rmtree(self.path(sid))

    # -- older layout -----------------------------------------------------------
    def _migrate(self):
        """Before saved studies, the one diary lived directly in .episteme/. Move it into a study."""
        legacy = [n for n in FILES if os.path.exists(os.path.join(self.root, n))]
        if "diary.json" not in legacy:
            return
        sid = self.create()
        for n in legacy:
            os.replace(os.path.join(self.root, n), os.path.join(self.path(sid), n))
        if self.is_blank(sid):
            shutil.rmtree(self.path(sid))
            return
        self.set_current(sid)


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
