"""Send raw capture events to Episteme. Shared by the Claude Code hook and the git hook.

Rules every capture tool follows:
  * Never block or break the tool being captured: short timeout, swallow all errors,
    print nothing (a UserPromptSubmit hook's stdout would be fed back to the agent).
  * Never lose an event: if Episteme is not reachable, append to a local spool file
    and flush it, in order, on the next successful send.
  * Redact secrets before anything is written or sent.

Where to send: $EPISTEME_URL, else the url file a running Episteme writes
(<repo>/.episteme/url), else http://127.0.0.1:8765.

Python 3.8 compatible on purpose (hooks run under the researcher's `python3`).
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATE = os.environ.get("EPISTEME_STATE") or os.path.join(REPO, ".episteme")
SPOOL = os.path.join(STATE, "spool.jsonl")
TIMEOUT = float(os.environ.get("EPISTEME_CAPTURE_TIMEOUT", "1.5"))

sys.path.insert(0, os.path.join(REPO, "episteme"))
from redact import redact_obj  # noqa: E402


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def base_url():
    if os.environ.get("EPISTEME_URL"):
        return os.environ["EPISTEME_URL"].rstrip("/")
    try:
        with open(os.path.join(STATE, "url"), encoding="utf-8") as f:
            return f.read().strip().rstrip("/")
    except OSError:
        return "http://127.0.0.1:8765"


def _post(events):
    body = json.dumps({"events": events}).encode()
    req = urllib.request.Request(base_url() + "/api/raw", data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status == 200


def _read_spool():
    try:
        with open(SPOOL, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return []


def _spool(events):
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(SPOOL, "a", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        pass


def send(events):
    """Redact, timestamp and send; spool on failure. Returns True if delivered now."""
    events = [redact_obj(dict(ev, ts=ev.get("ts") or now_iso())) for ev in events if ev]
    if not events:
        return True
    pending = _read_spool()
    try:
        ok = _post(pending + events)
    except Exception:
        ok = False
    if ok:
        if pending:
            try:
                os.remove(SPOOL)
            except OSError:
                pass
        return True
    _spool(events)
    return False
