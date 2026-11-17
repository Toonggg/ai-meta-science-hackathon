#!/usr/bin/env python3
"""Replay a recorded capture session into a running Episteme.

Every session Episteme captures is already recorded in .episteme/raw.jsonl.
Copy that file somewhere safe, then replay it to show a session without
running the agent live:

    python3 tools/replay.py demo/session.jsonl --clear --project "Thermostability"
    python3 tools/replay.py demo/session.jsonl --speed 20     # 20x faster than real time
    python3 tools/replay.py demo/session.jsonl --instant      # everything at once

The demo studies in demo/ use the same format (the start screen loads them in one go);
replay one to watch its timeline fill in:

    python3 tools/replay.py demo/alphafold.jsonl --clear --project "AlphaFold 2" --speed 15

Lines with "kind": "note" are researcher notes (see episteme/demos.py). They are added
to the diary once everything before them is stitched, as if typed in at that moment.

Events keep their original timestamps, so the diary shows when things really
happened. Gaps between events are replayed scaled by --speed and capped at
--max-gap seconds, so the timeline fills in on screen like a live run.

Python 3.8 compatible, stdlib only.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

KINDS = {"instruction", "action", "agent_text", "commit", "stop", "note", "question"}


def load(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                sys.exit("%s line %d is not valid JSON" % (path, n))
            if ev.get("kind") not in KINDS:
                sys.exit("%s line %d has an unknown kind: %r" % (path, n, ev.get("kind")))
            ev.pop("rid", None)  # the server assigns new ids
            events.append(ev)
    return events


TOKEN = ""  # set from --token / --token-file; needed only for --clear


def post(url, path, body=None, timeout=30):
    """POST body as JSON, or GET when body is None."""
    headers = {"content-type": "application/json"}
    if TOKEN:
        headers["x-episteme-token"] = TOKEN
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def add_note(url, line):
    """A researcher note or question: stitch what came before it, then add it to the diary (linked to the
    latest run when it says "about": "last_run"), as episteme/demos.py does."""
    post(url, "/api/stitch", {}, timeout=600)
    t = line.get("kind") or "note"
    ev = {"type": t, "source": "manual", "title": line.get("title", ""), "detail": line.get("detail", ""), "actor": "human", "provenance": "stated"}
    if line.get("ts"):
        ev["ts"] = line["ts"]
    if line.get("about") == "last_run":
        runs = [e for e in post(url, "/api/events")["events"] if e.get("type") == "run"]
        if runs:
            ev["links"] = [runs[-1]["id"]]
    post(url, "/api/events", ev)


def send(url, batch):
    """Raw events go to the raw log in one request; notes/questions one at a time, in order."""
    raw = []
    for ev in batch:
        if ev["kind"] in ("note", "question"):
            if raw:
                post(url, "/api/raw", {"events": raw})
                raw = []
            add_note(url, ev)
        else:
            raw.append(ev)
    if raw:
        post(url, "/api/raw", {"events": raw})


def ts(ev):
    try:
        return datetime.fromisoformat(ev.get("ts", "")).timestamp()
    except ValueError:
        return None


def gaps(events, speed, max_gap):
    """Seconds to wait before each event: real gap / speed, capped."""
    out, prev = [], None
    for ev in events:
        t = ts(ev)
        out.append(0.0 if prev is None or t is None else max(0.0, min(max_gap, (t - prev) / speed)))
        prev = t if t is not None else prev
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file", help="a recorded raw.jsonl")
    ap.add_argument("--url", default="http://127.0.0.1:8765", help="Episteme address (default %(default)s)")
    ap.add_argument("--speed", type=float, default=10.0, help="times faster than real time (default %(default)s)")
    ap.add_argument("--max-gap", type=float, default=3.0, help="longest pause between events, seconds (default %(default)s)")
    ap.add_argument("--instant", action="store_true", help="send everything at once")
    ap.add_argument("--clear", action="store_true", help="empty the diary and raw log first")
    ap.add_argument("--project", help="project name to set when clearing")
    ap.add_argument("--token", help="Episteme's page token (default: read from --token-file)")
    ap.add_argument("--token-file", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                         ".episteme", "token"),
                    help="file the running Episteme writes its token to (default %(default)s)")
    a = ap.parse_args(argv)
    url = a.url.rstrip("/")
    global TOKEN
    TOKEN = a.token or ""
    if not TOKEN:  # needed for --clear; without it, notes are labelled as coming from a script
        try:
            with open(a.token_file, encoding="utf-8") as f:
                TOKEN = f.read().strip()
        except OSError:
            if a.clear:
                sys.exit("--clear needs Episteme's token: start Episteme first, or pass --token / --token-file")

    events = load(a.file)
    if a.clear:
        post(url, "/api/clear", {"project": a.project} if a.project else {})
    if a.instant:
        send(url, events)
    else:
        for ev, wait in zip(events, gaps(events, max(a.speed, 0.01), a.max_gap)):
            time.sleep(wait)
            send(url, [ev])
            text = ev.get("command") or ev.get("text") or ev.get("title") or ""
            print("%-11s %s" % (ev["kind"], text[:70].replace("\n", " ")))
    status = post(url, "/api/stitch", {}, timeout=600)  # stitch now; a model call can take minutes
    print("replayed %d events: %d episodes stitched, %d pivots pending" % (len(events), status["stitched"], status["pending"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
