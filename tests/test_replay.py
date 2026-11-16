import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "episteme"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import replay  # noqa: E402
import server  # noqa: E402
import stitcher  # noqa: E402
from store import Diary, RawLog  # noqa: E402

from test_stitcher import SESSION  # noqa: E402


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        server.STORE = Diary(os.path.join(self.dir, "diary.json"))
        server.RAW = RawLog(os.path.join(self.dir, "raw.jsonl"))
        server.STITCHER = stitcher.Stitcher(server.STORE, server.RAW, self.dir, use_ai=False)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.file = os.path.join(self.dir, "session.jsonl")
        with open(self.file, "w") as f:
            for i, ev in enumerate(SESSION):
                f.write(json.dumps(dict(ev, rid="R%d" % (i + 50), ts="2026-11-14T10:%02d:00+01:00" % i)) + "\n")

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.STITCHER = None

    def test_replay_instant_with_project(self):
        server.load_demo("alphafold")  # --clear replaces whatever study was open
        replay.main([self.file, "--url", self.url, "--instant", "--clear", "--project", "Thermostability", "--token", server.TOKEN])
        snap = server.STORE.snapshot()
        self.assertEqual(snap["project"], "Thermostability")
        self.assertEqual([e["type"] for e in snap["events"]],
                         ["plan", "run", "artifact", "pivot", "plan", "run", "surprise"])
        self.assertEqual(server.RAW.all()[0]["rid"], "R1")  # ids reassigned, not copied
        self.assertEqual(snap["events"][0]["ts"], "2026-11-14T10:00:00+01:00")  # original time kept

    def test_replay_paced(self):
        replay.main([self.file, "--url", self.url, "--clear", "--speed", "100000", "--token", server.TOKEN])
        self.assertEqual(len(server.RAW.all()), len(SESSION))

    def test_gaps_scaled_and_capped(self):
        evs = [{"ts": "2026-11-14T10:00:00+01:00"}, {"ts": "2026-11-14T10:00:20+01:00"}, {"ts": "2026-11-14T11:00:00+01:00"}]
        self.assertEqual(replay.gaps(evs, speed=10, max_gap=3), [0.0, 2.0, 3.0])

    def test_rejects_unknown_kind(self):
        bad = os.path.join(self.dir, "bad.jsonl")
        with open(bad, "w") as f:
            f.write('{"kind": "banana"}\n')
        with self.assertRaises(SystemExit):
            replay.load(bad)

    def test_clear_without_project_keeps_name(self):
        server.load_demo("alphafold")
        name = server.STORE.snapshot()["project"]
        server.STORE.clear()
        self.assertEqual(server.STORE.snapshot()["project"], name)


if __name__ == "__main__":
    unittest.main()
