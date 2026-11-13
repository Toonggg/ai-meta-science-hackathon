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
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import claims  # noqa: E402
import diary  # noqa: E402
import episodes  # noqa: E402
import export  # noqa: E402
import llm  # noqa: E402
import pipeline  # noqa: E402
import question  # noqa: E402
import search  # noqa: E402
from demo_data import DEMO_PAPER  # noqa: E402
from store import Diary, RawLog  # noqa: E402

STATIC = os.path.join(HERE, "static")
STORE = None
RAW = None
MAX_RAW_BATCH = 500
MAX_BODY = 5 * 1024 * 1024


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

    def same_origin(self):
        # Block cross-site writes from other web pages (no CORS is offered).
        origin = self.headers.get("origin")
        return not origin or origin.startswith(("http://127.0.0.1:", "http://localhost:"))

    # -- routes ------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p == "/api/sources":
            return self.send(200, search.status())
        if p == "/api/status":
            return self.send(200, {"ai": llm.status(), "search": search.status(), "events": len(STORE.events())})
        if p.startswith("/api/jobs/"):
            job = pipeline.get(p.rsplit("/", 1)[-1])
            return self.send(200, job) if job else self.send(404, {"error": "unknown job"})
        if p == "/api/events":
            return self.send(200, STORE.snapshot())
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
        if p == "/api/demo-paper":
            return self.send(200, {"text": DEMO_PAPER})
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
        if not self.same_origin():
            return self.send(403, {"error": "cross-origin request refused"})
        p = urlparse(self.path).path
        try:
            b = self.body()
        except ValueError as e:
            return self.send(400, {"error": str(e)})
        use_ai = bool(b.get("use_ai", True))
        try:
            if p == "/api/events":
                ev = STORE.add(b.get("event", b))
                auto, prompts = diary.after_add(STORE, ev)
                return self.send(200, {"event": ev, "auto": auto, "prompts": prompts})
            if p == "/api/raw":  # capture tools: {"events": [...]} or a single event
                batch = b.get("events") if isinstance(b.get("events"), list) else [b]
                if len(batch) > MAX_RAW_BATCH:
                    return self.send(400, {"error": "at most %d raw events per request" % MAX_RAW_BATCH})
                try:
                    saved = [RAW.add(ev) for ev in batch if isinstance(ev, dict)]
                except ValueError as e:
                    return self.send(400, {"error": str(e)})
                return self.send(200, {"raw": [e["rid"] for e in saved]})
            if p == "/api/pivot":
                ev = diary.record_pivot(STORE, b["plan_id"], b.get("links", []), b.get("reason", ""), bool(b.get("skipped")))
                return self.send(200, {"event": ev})
            if p == "/api/delete":
                STORE.delete(b["id"])
                return self.send(200, {"ok": True})
            if p == "/api/reset":  # the demo diary has no raw capture behind it
                STORE.reset_demo()
                RAW.clear()
                return self.send(200, {"ok": True})
            if p == "/api/clear":  # fresh project: empty diary and raw log
                STORE.clear()
                RAW.clear()
                return self.send(200, {"ok": True})
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
        return self.send(200, data, mimetypes.guess_type(full)[0] or "application/octet-stream")


def main():
    global STORE, RAW
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(os.path.dirname(HERE), ".episteme"))
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    os.makedirs(a.state, exist_ok=True)
    STORE = Diary(os.path.join(a.state, "diary.json"))
    RAW = RawLog(os.path.join(a.state, "raw.jsonl"))
    llm.init(a.state)  # also initialises the shared config file
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
