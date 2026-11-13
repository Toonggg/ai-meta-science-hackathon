import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "episteme"))
sys.path.insert(0, os.path.join(ROOT, "capture"))

import claude_hook  # noqa: E402
import episodes  # noqa: E402
import redact  # noqa: E402
import send  # noqa: E402
import server  # noqa: E402
from store import Diary, RawLog  # noqa: E402

CWD = "/Users/someone/proj"
BASE = {"session_id": "5b6b160a-3b90-4067", "cwd": CWD}

# Shapes recorded from a real Claude Code session (paths shortened).
PROMPT = dict(BASE, hook_event_name="UserPromptSubmit", prompt="Train a baseline")
WRITE = dict(BASE, hook_event_name="PostToolUse", tool_name="Write",
             tool_input={"file_path": CWD + "/train.py", "content": "print('secret code body')"},
             tool_response={"type": "create", "filePath": CWD + "/train.py"})
BASH_OK = dict(BASE, hook_event_name="PostToolUse", tool_name="Bash",
               tool_input={"command": "python3 " + CWD + "/train.py", "description": "Run train.py"},
               tool_response={"stdout": "RESULT spearman=0.71 split=random", "stderr": "", "interrupted": False})
BASH_FAIL = dict(BASE, hook_event_name="PostToolUseFailure", tool_name="Bash",
                 tool_input={"command": "python3 missing.py", "description": "Run missing.py"},
                 error="Exit code 2\npython3: can't open file '" + CWD + "/missing.py'", is_interrupt=False)
STOP = dict(BASE, hook_event_name="Stop", stop_hook_active=False,
            last_assistant_message="The random split leaked similar proteins.")


class HookMappingTest(unittest.TestCase):
    def test_instruction(self):
        self.assertEqual(claude_hook.to_raw(PROMPT),
                         [{"source": "agent", "session": "5b6b160a", "kind": "instruction", "text": "Train a baseline"}])

    def test_write_keeps_name_not_content(self):
        ev = claude_hook.to_raw(WRITE)[0]
        self.assertEqual(ev["files"], ["train.py"])
        self.assertNotIn("secret code body", json.dumps(ev))

    def test_bash_ok_is_a_run_with_result(self):
        ev = dict(claude_hook.to_raw(BASH_OK)[0], rid="R1")
        self.assertEqual(ev["command"], "python3 train.py")
        self.assertEqual(ev["intent"], "Run train.py")
        self.assertTrue(episodes.is_run(ev))
        self.assertEqual(episodes.parse_results(ev["output"])["metrics"], {"spearman": 0.71})

    def test_failure_event(self):
        ev = claude_hook.to_raw(BASH_FAIL)[0]
        self.assertTrue(ev["error"])
        self.assertIn("can't open file 'missing.py'", ev["output"])

    def test_stop_gives_agent_text_then_stop(self):
        evs = claude_hook.to_raw(STOP)
        self.assertEqual([e["kind"] for e in evs], ["agent_text", "stop"])

    def test_unknown_event_ignored(self):
        self.assertEqual(claude_hook.to_raw(dict(BASE, hook_event_name="Notification")), [])

    def test_long_output_keeps_result_lines(self):
        out = "RESULT auroc=0.81\n" + "x" * 10000
        clipped = claude_hook.clip_output(out)
        self.assertLess(len(clipped), 4000)
        self.assertIn("RESULT auroc=0.81", clipped)

    def test_quick_fix_with_absolute_and_relative_paths(self):
        a = {"rid": "R2", "kind": "action", "command": "python3 /a/b/train.py", "error": True}
        b = {"rid": "R3", "kind": "action", "command": "python3 train.py"}
        self.assertEqual(episodes.run_key(a), episodes.run_key(b))


class RedactTest(unittest.TestCase):
    def test_patterns(self):
        cases = {
            "export OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuv": "abcdefghijklmnop",
            "curl -H 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz'": "abcdefghijklmnopqrst",
            "git clone https://user:hunter2pass@github.com/x/y": "hunter2pass",
            "python train.py --api-key 12345678abcd": "12345678abcd",
            "token: ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaa": "ghp_aaaa",
            "password=letmein99": "letmein99",
        }
        for text, secret in cases.items():
            self.assertNotIn(secret, redact.redact(text, env=False), text)

    def test_env_values(self):
        os.environ["MY_SERVICE_TOKEN"] = "plainvalue123"
        try:
            self.assertEqual(redact.redact("echo plainvalue123"), "echo [REDACTED]")
        finally:
            del os.environ["MY_SERVICE_TOKEN"]

    def test_leaves_normal_text(self):
        t = "RESULT spearman=0.71 split=random\npython3 train.py --epochs 10"
        self.assertEqual(redact.redact(t, env=False), t)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        server.STORE = Diary(os.path.join(cls.dir, "diary.json"))
        server.RAW = RawLog(os.path.join(cls.dir, "raw.jsonl"))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.url = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        server.RAW.clear()

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_batch_then_episodes(self):
        evs = []
        for p in (PROMPT, WRITE, BASH_OK, STOP):
            evs += claude_hook.to_raw(p)
        st, r = self.call("/api/raw", {"events": evs})
        self.assertEqual((st, r["raw"]), (200, ["R1", "R2", "R3", "R4", "R5"]))
        st, r = self.call("/api/episodes")
        ep = r["episodes"][0]
        self.assertEqual((ep["id"], ep["close_reason"], ep["final"]), ("EP-R1", "result", True))
        self.assertEqual(self.call("/api/raw?since=R3")[1]["raw"][0]["rid"], "R4")
        self.assertEqual([e["rid"] for e in self.call("/api/raw?ids=R2,R5")[1]["raw"]], ["R2", "R5"])

    def test_bad_kind_rejected(self):
        st, r = self.call("/api/raw", {"kind": "banana"})
        self.assertEqual(st, 400)


class SpoolTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        send.STATE = self.dir
        send.SPOOL = os.path.join(self.dir, "spool.jsonl")
        os.environ["EPISTEME_URL"] = "http://127.0.0.1:9"  # nothing listens on port 9
        send.TIMEOUT = 0.3

    def tearDown(self):
        os.environ.pop("EPISTEME_URL", None)

    def test_spools_when_down_and_flushes_in_order(self):
        self.assertFalse(send.send([{"kind": "instruction", "text": "first"}]))
        self.assertFalse(send.send([{"kind": "stop"}]))
        self.assertEqual(len(send._read_spool()), 2)
        d = tempfile.mkdtemp()
        server.STORE = Diary(os.path.join(d, "diary.json"))
        server.RAW = RawLog(os.path.join(d, "raw.jsonl"))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            os.environ["EPISTEME_URL"] = "http://127.0.0.1:%d" % httpd.server_address[1]
            self.assertTrue(send.send([{"kind": "instruction", "text": "third"}]))
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertEqual([e.get("text") for e in server.RAW.all()], ["first", None, "third"])
        self.assertFalse(os.path.exists(send.SPOOL))

    def test_secrets_never_reach_spool(self):
        send.send([{"kind": "action", "command": "export X_API_KEY=abcdef123456"}])
        with open(send.SPOOL) as f:
            self.assertNotIn("abcdef123456", f.read())


if __name__ == "__main__":
    unittest.main()
