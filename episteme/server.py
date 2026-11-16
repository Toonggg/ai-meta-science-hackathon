"""Episteme local server: static UI + JSON API on 127.0.0.1. Stdlib only.

Started by ./run. Writes its URL to <state>/url once it is listening.
External tools (a Claude Code hook, a notebook, curl) can stream events in:

    curl -s localhost:8765/api/events -H 'content-type: application/json' \
         -d '{"type":"run","title":"train v2","result":"AUROC 0.83","source":"agent"}'
"""

import argparse
import json
import mimetypes
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import claims  # noqa: E402
import demos  # noqa: E402
import diary  # noqa: E402
import episodes  # noqa: E402
import export  # noqa: E402
import llm  # noqa: E402
import pipeline  # noqa: E402
import question  # noqa: E402
import search  # noqa: E402
import stitcher  # noqa: E402
from store import RAW_KINDS, Diary, RawLog  # noqa: E402

STATIC = os.path.join(HERE, "static")
STORE = None
RAW = None
STITCHER = None
MAX_RAW_BATCH = 500
MAX_BODY = 5 * 1024 * 1024

# A random token per server start, embedded in the page. Actions only a person at the page should
# take need it; capture hooks and the Task 1/3 routes do not. Written to .episteme/token for local
# tools (tools/replay.py). It stops other web pages and naive scripts; anything that can read the
# user's files can read it too.
TOKEN = secrets.token_urlsafe(24)
NEEDS_TOKEN = {"/api/confirm", "/api/pivot", "/api/delete", "/api/demo", "/api/demo/step", "/api/clear", "/api/settings", "/api/sources"}
# Attribution is decided by Episteme (stitcher, confirm flow), never taken from a posted event.
ATTRIBUTION_FIELDS = ("actor", "confirmation", "confirmed_by", "confirmed_at", "skipped_at", "classified_by",
                      "needs_confirmation", "quote", "model_summary", "proposed_reason", "pending", "episode_id",
                      "raw_ids")


def wipe(reset_diary):
    """Reset the diary and empty the raw log under the stitcher's lock, so a stitching pass
    can never write into a half-cleared diary."""
    def both():
        reset_diary()
        RAW.clear()
    if STITCHER:
        STITCHER.reset(also=both)
    else:
        both()


def load_demo(demo_id):
    """Replace the diary with a demo. Every demo goes through the same path as live capture:
    raw events into the raw log, then the stitcher's rules; researcher notes are added once
    the events before them are stitched. The background stitcher asks the model about any
    pending pivots afterwards, so loading never waits on a model."""
    d = demos.get(demo_id)
    lines = demos.session(demo_id)
    wipe(lambda: STORE.clear(d["project"], demo=demo_id))
    for kind, batch in demos.chunks(lines):
        if kind == "raw":
            for ev in batch:
                RAW.add(ev)
            if STITCHER:
                STITCHER.run_once(ask_model=False)
        else:
            for line in batch:
                ev = STORE.add(demos.note_event(line, STORE.events()))
                diary.after_add(STORE, ev)
    if STITCHER:
        STITCHER.poke()


class Handler(BaseHTTPRequestHandler):
    server_version = "Episteme/0.1"

    def log_message(self, fmt, *args):  # quiet: goes to .episteme/server.log via stderr
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    # -- helpers -----------------------------------------------------------
    def send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else (
            body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode())
        self.send_response(code)
        self.send_header("content-type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
        self.send_header("content-length", str(len(data)))
        self.send_header("cache-control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("content-length") or 0)
        if n > MAX_BODY:
            raise ValueError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode() or "{}")

    def own_hosts(self):
        port = self.server.server_address[1]
        return {"127.0.0.1:%d" % port, "localhost:%d" % port}

    def host_ok(self):
        # DNS rebinding: a foreign site that resolves its name to 127.0.0.1 still sends its own Host.
        return (self.headers.get("host") or "").lower() in self.own_hosts()

    def same_origin(self):
        # Block writes from other web pages, including other local apps on other ports (no CORS is offered).
        origin = self.headers.get("origin")
        return not origin or origin.lower() in {"http://" + h for h in self.own_hosts()}

    def has_token(self):
        return secrets.compare_digest(self.headers.get("x-episteme-token") or "", TOKEN)

    # -- routes ------------------------------------------------------------
    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {"error": "unexpected Host header"})
        u = urlparse(self.path)
        p = u.path
        if p == "/api/sources":
            return self.send(200, search.status())
        if p == "/api/status":
            return self.send(200, {"ai": llm.status(), "search": search.status(), "events": len(STORE.events()),
                                   "stitch": STITCHER.status() if STITCHER else None})
        if p.startswith("/api/jobs/"):
            job = pipeline.get(p.rsplit("/", 1)[-1])
            return self.send(200, job) if job else self.send(404, {"error": "unknown job"})
        if p == "/api/events":
            snap = STORE.snapshot()
            for e in snap["events"]:
                e["who"] = diary.who(e)  # display only, never stored
            return self.send(200, snap)
        if p == "/api/raw":  # ?ids=R1,R2  or  ?since=R10  or everything
            q = parse_qs(u.query)
            if q.get("ids"):
                return self.send(200, {"raw": RAW.get(q["ids"][0].split(","))})
            evs = RAW.all()
            if q.get("since"):
                n = int(q["since"][0].lstrip("Rr") or 0)
                evs = [e for e in evs if int(e["rid"][1:]) > n]
            return self.send(200, {"raw": evs})
        if p == "/api/episodes":
            return self.send(200, {"episodes": episodes.segment(RAW.all())})
        if p == "/api/stitch":
            return self.send(200, STITCHER.status())
        if p == "/api/prompts":  # pivots waiting for the researcher's confirm / edit / skip
            return self.send(200, {"prompts": diary.prompts(STORE.snapshot()["events"])})
        if p == "/api/demos":
            return self.send(200, {"demos": demos.list_demos(), "current": STORE.snapshot().get("demo")})
        if p == "/api/demo-lines":
            demo_id = parse_qs(u.query).get("id", ["alphafold"])[0]
            try:
                return self.send(200, {"lines": demos.session(demo_id)})
            except KeyError:
                return self.send(404, {"error": "unknown demo"})
        if p == "/api/demo-paper":  # the paper of the demo that is loaded, if it has one
            demo_id = STORE.snapshot().get("demo")
            text = demos.paper(demo_id) if demo_id else ""
            return self.send(200, {"text": text, "demo": demo_id})
        if p == "/api/export":
            fmt = parse_qs(u.query).get("format", ["md"])[0]
            snap = STORE.snapshot()
            if fmt == "json":
                return self.send(200, export.to_json(snap), "application/json",
                                 {"content-disposition": "attachment; filename=episteme-diary.json"})
            if fmt == "prov":
                return self.send(200, export.to_prov(snap), "application/json",
                                 {"content-disposition": "attachment; filename=episteme-prov.json"})
            return self.send(200, export.to_markdown(snap), "text/markdown",
                             {"content-disposition": "attachment; filename=decision-appendix.md"})
        return self.static(p)

    def do_POST(self):
        if not self.host_ok():
            return self.send(403, {"error": "unexpected Host header"})
        if not self.same_origin():
            return self.send(403, {"error": "cross-origin request refused"})
        p = urlparse(self.path).path
        if p in NEEDS_TOKEN and not self.has_token():
            return self.send(403, {"error": "this action is only available from the Episteme page"})
        try:
            b = self.body()
        except ValueError as e:
            return self.send(400, {"error": str(e)})
        if not isinstance(b, dict):
            return self.send(400, {"error": "expected a JSON object"})
        use_ai = bool(b.get("use_ai", True))
        try:
            if p == "/api/events":
                ev = b.get("event", b)
                if not isinstance(ev, dict):
                    return self.send(400, {"error": "expected a JSON object"})
                ev = {k: v for k, v in ev.items() if k not in ATTRIBUTION_FIELDS}
                src = ev.get("source")
                if not self.has_token() and (src in ("manual", "episteme") or not isinstance(src, str)
                                             or not re.fullmatch(r"[a-z_]{1,20}", src)):
                    ev["source"] = "tool"  # an outside script: not the researcher at the page, not Episteme
                ev = STORE.add(ev)
                auto, prompts = diary.after_add(STORE, ev)
                return self.send(200, {"event": ev, "auto": auto, "prompts": prompts})
            if p == "/api/raw":  # capture tools: {"events": [...]} or a single event
                batch = b.get("events") if isinstance(b.get("events"), list) else [b]
                if len(batch) > MAX_RAW_BATCH:
                    return self.send(400, {"error": "at most %d raw events per request" % MAX_RAW_BATCH})
                batch = [ev for ev in batch if isinstance(ev, dict)]
                bad = [ev.get("kind") for ev in batch if ev.get("kind") not in RAW_KINDS]
                if bad:  # all or nothing, so a batch is never half-stored
                    return self.send(400, {"error": "unknown raw event kind: %s" % bad[0]})
                saved = [RAW.add(ev) for ev in batch]
                if STITCHER:
                    STITCHER.poke()
                return self.send(200, {"raw": [e["rid"] for e in saved]})
            if p == "/api/confirm":  # {"id": "E8", "action": "confirm" | "edit" | "skip", "reason": "..."}
                try:
                    ev = diary.confirm(STORE, b["id"], b.get("action", ""), b.get("reason", ""))
                except ValueError as e:
                    return self.send(400, {"error": str(e)})
                if STITCHER:
                    STITCHER.human_handled(ev)
                return self.send(200, {"event": ev})
            if p == "/api/pivot":
                ev = diary.record_pivot(STORE, b["plan_id"], b.get("links", []), b.get("reason", ""), bool(b.get("skipped")))
                return self.send(200, {"event": ev})
            if p == "/api/delete":
                STORE.delete(b["id"])
                return self.send(200, {"ok": True})
            if p == "/api/demo":  # {"id": "alphafold"}: replace the diary with a demo study
                try:
                    load_demo(b["id"])
                except ValueError as e:
                    return self.send(400, {"error": str(e)})
                return self.send(200, {"ok": True, "events": len(STORE.events())})
            if p == "/api/demo/step":  # {"id": "alphafold", "step": i, "reset": true}: step through demo session
                demo_id = b.get("id", "alphafold")
                step_idx = int(b.get("step", 0))
                try:
                    d = demos.get(demo_id)
                    lines = demos.session(demo_id)
                except KeyError:
                    return self.send(404, {"error": "unknown demo"})
                if b.get("reset") or step_idx == 0:
                    wipe(lambda: STORE.clear(d["project"], demo=demo_id))
                if 0 <= step_idx < len(lines):
                    line = lines[step_idx]
                    kind = line.get("kind")
                    if kind in ("note", "question"):
                        if STITCHER:
                            STITCHER.run_once(ask_model=False)
                        ev = STORE.add(demos.note_event(line, STORE.events()))
                        diary.after_add(STORE, ev)
                    else:
                        ev = dict(line)
                        ev.pop("rid", None)
                        RAW.add(ev)
                        if STITCHER:
                            STITCHER.run_once(ask_model=False)
                if step_idx >= len(lines) - 1 and STITCHER:
                    STITCHER.poke()
                return self.send(200, {
                    "ok": True,
                    "step": step_idx,
                    "total": len(lines),
                    "events": len(STORE.events()),
                    "line": lines[step_idx] if 0 <= step_idx < len(lines) else None,
                    "done": step_idx >= len(lines) - 1
                })
            if p == "/api/clear":  # fresh project: empty diary and raw log, optionally {"project": "name"}
                wipe(lambda: STORE.clear(b.get("project")))
                return self.send(200, {"ok": True})
            if p == "/api/stitch":  # run the stitcher now instead of waiting for the next tick
                STITCHER.run_once()
                return self.send(200, STITCHER.status())
            if p == "/api/question":  # synchronous, rules/AI only (kept for scripts)
                return self.send(200, question.analyse(b.get("question", ""), use_ai))
            if p == "/api/question/start":  # the staged pipeline the UI uses
                q = (b.get("question") or "").strip()
                if not q:
                    return self.send(400, {"error": "empty question"})
                return self.send(200, {"job": pipeline.start(q, bool(b.get("use_search", True)), use_ai)})
            if p == "/api/sources":
                return self.send(200, search.save(b))
            if p == "/api/sources/check":  # {"id": "arxiv"} for one source, {} for all
                if b.get("id"):
                    search.check_one(b["id"], "manual", include_web=bool(b.get("include_web")))
                    return self.send(200, search.status())
                return self.send(200, search.check_all(include_web=bool(b.get("include_web"))))
            if p == "/api/ask":
                return self.send(200, diary.ask(b.get("question", ""), STORE.snapshot()["events"], use_ai))
            if p == "/api/claims":
                return self.send(200, claims.analyse(b.get("text", ""), STORE.snapshot()["events"], use_ai))
            if p == "/api/settings":
                return self.send(200, llm.save(b))
        except KeyError as e:
            return self.send(400, {"error": "missing or unknown field: %s" % e})
        return self.send(404, {"error": "not found"})

    def static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        full = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not full.startswith(STATIC + os.sep) or not os.path.isfile(full):
            return self.send(404, "not found", "text/plain")
        with open(full, "rb") as f:
            data = f.read()
        if full == os.path.join(STATIC, "index.html"):
            data = data.replace(b"__EPISTEME_TOKEN__", TOKEN.encode())
        return self.send(200, data, mimetypes.guess_type(full)[0] or "application/octet-stream")


def main():
    global STORE, RAW, STITCHER
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(os.path.dirname(HERE), ".episteme"))
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    os.makedirs(a.state, exist_ok=True)
    STORE = Diary(os.path.join(a.state, "diary.json"))
    RAW = RawLog(os.path.join(a.state, "raw.jsonl"))
    llm.init(a.state)  # also initialises the shared config file; before the stitcher, which needs it
    # EPISTEME_STITCH_AI=0 keeps the stitcher on rules only (no model calls, no API spend).
    STITCHER = stitcher.Stitcher(STORE, RAW, a.state, use_ai=os.environ.get("EPISTEME_STITCH_AI", "1") != "0")
    STITCHER.start()
    search.start_poller()

    httpd = None
    for port in range(a.port, a.port + 30):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit("no free port between %d and %d" % (a.port, a.port + 29))
    url = "http://127.0.0.1:%d" % httpd.server_address[1]
    with open(os.path.join(a.state, "url"), "w") as f:
        f.write(url)
    fd = os.open(os.path.join(a.state, "token"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:  # for local tools such as tools/replay.py
        f.write(TOKEN)
    sys.stderr.write("Episteme listening on %s (AI: %s)\n" % (url, llm.status()["label"]))
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            os.remove(os.path.join(a.state, "url"))
        except OSError:
            pass


if __name__ == "__main__":
    main()
