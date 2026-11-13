#!/usr/bin/env python3
"""Replay a recorded capture session into a running Episteme.

Every session Episteme captures is already recorded in .episteme/raw.jsonl.
Copy that file somewhere safe, then replay it to show a session without
running the agent live:

    python3 tools/replay.py demo/session.jsonl --clear --project "Thermostability"
    python3 tools/replay.py demo/session.jsonl --speed 20     # 20x faster than real time
    python3 tools/replay.py demo/session.jsonl --instant      # everything at once

Events keep their original timestamps, so the diary shows when things really
happened. Gaps between events are replayed scaled by --speed and capped at
--max-gap seconds, so the timeline fills in on screen like a live run.

Python 3.8 compatible, stdlib only.
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime

KINDS = {"instruction", "action", "agent_text", "commit", "stop"}


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


def post(url, path, body):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


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
    a = ap.parse_args(argv)
    url = a.url.rstrip("/")

    events = load(a.file)
    if a.clear:
        post(url, "/api/clear", {"project": a.project} if a.project else {})
    if a.instant:
        post(url, "/api/raw", {"events": events})
    else:
        for ev, wait in zip(events, gaps(events, max(a.speed, 0.01), a.max_gap)):
            time.sleep(wait)
            post(url, "/api/raw", {"events": [ev]})
            print("%-11s %s" % (ev["kind"], (ev.get("command") or ev.get("text") or "")[:70].replace("\n", " ")))
    status = post(url, "/api/stitch", {})  # stitch now rather than on the next background tick
    print("replayed %d events: %d episodes stitched, %d pivots pending" % (len(events), status["stitched"], status["pending"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
