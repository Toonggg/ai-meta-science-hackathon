"""The demo studies in demo/: every demo loads through the same path as live capture."""

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
sys.path.insert(0, os.path.join(ROOT, "tools"))

import demos  # noqa: E402
import diary  # noqa: E402
import replay  # noqa: E402
import server  # noqa: E402
import stitcher  # noqa: E402
from store import Diary, RawLog  # noqa: E402

IDS = ["hospital-readmission", "alphafold"]
# Same story shape for both: plan, run, surprise, pivot at step 4, new plan, run, commit.
SHAPE = ["plan", "run", "surprise", "pivot", "plan", "run", "artifact"]


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        server.STORE = Diary(os.path.join(self.dir, "diary.json"))
        server.RAW = RawLog(os.path.join(self.dir, "raw.jsonl"))
        server.STITCHER = stitcher.Stitcher(server.STORE, server.RAW, self.dir, use_ai=False)

    def tearDown(self):
        server.STITCHER = None

    def types(self):
        return [e["type"] for e in server.STORE.events()]

    def test_registry(self):
        self.assertEqual([d["id"] for d in demos.list_demos()], IDS)
        for d in demos.list_demos():
            self.assertTrue(d["title"] and d["project"] and d["summary"])
            self.assertTrue(demos.session(d["id"]))  # file exists and every line has a known kind

    def test_new_diary_is_empty(self):
        snap = server.STORE.snapshot()
        self.assertEqual((snap["events"], snap["project"], snap.get("demo")), ([], "", None))

    def test_both_demos_load_the_same_way(self):
        for demo_id in IDS:
            server.load_demo(demo_id)
            snap = server.STORE.snapshot()
            self.assertEqual(snap["demo"], demo_id)
            self.assertEqual(snap["project"], demos.get(demo_id)["project"])
            self.assertEqual(self.types()[:len(SHAPE)], SHAPE, demo_id)
            self.assertTrue(server.RAW.all(), demo_id)  # stitched from raw capture, with evidence
            for e in snap["events"]:
                self.assertTrue(e.get("actor"), e)
                if e["type"] in ("plan", "run", "artifact"):
                    self.assertTrue(e.get("raw_ids"), e)
            answer = diary.ask_heuristic("Why did they change approach at step 4?", snap["events"])
            self.assertIn("Step 4", answer)

    def test_loading_replaces_the_previous_study(self):
        server.load_demo("hospital-readmission")
        server.load_demo("alphafold")
        raw_lines = [l for l in demos.session("alphafold") if l.get("kind") not in ("note", "question")]
        self.assertEqual(len(server.RAW.all()), len(raw_lines))
        self.assertEqual(self.types()[:len(SHAPE)], SHAPE)

    def test_readmission_note_links_the_run(self):
        server.load_demo("hospital-readmission")
        evs = server.STORE.events()
        note = next((e for e in reversed(evs) if e["type"] == "note"), None)
        self.assertIsNotNone(note)
        self.assertEqual((note["type"], note["actor"]), ("note", "human"))
        run = next((e for e in evs if e["type"] == "run" and "0.81" in e.get("result", "")), None)
        self.assertIsNotNone(run)
        self.assertEqual(note["links"], [run["id"]])
        self.assertIn("0.81", run["result"])

    def test_paper_follows_the_loaded_demo(self):
        self.assertIn("AUROC 0.81 vs 0.54", demos.paper("hospital-readmission"))
        self.assertEqual(demos.paper("alphafold"), "")

    def test_unknown_demo(self):
        with self.assertRaises(KeyError):
            server.load_demo("nope")


class DemoReplayTest(unittest.TestCase):
    """tools/replay.py plays the same files and ends with the same diary."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        server.STORE = Diary(os.path.join(self.dir, "diary.json"))
        server.RAW = RawLog(os.path.join(self.dir, "raw.jsonl"))
        server.STITCHER = stitcher.Stitcher(server.STORE, server.RAW, self.dir, use_ai=False)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.STITCHER = None

    def summary(self):
        return [(e["type"], e["title"], e.get("links", []), e.get("actor")) for e in server.STORE.events()]

    def test_replay_matches_load(self):
        for demo_id in IDS:
            server.load_demo(demo_id)
            loaded = self.summary()
            path = os.path.join(demos.DEMO_DIR, demos.get(demo_id)["session"])
            replay.main([path, "--url", self.url, "--instant", "--clear", "--token", server.TOKEN])
            self.assertEqual(self.summary(), loaded, demo_id)

    def test_api(self):
        def req(p):
            with urllib.request.urlopen(self.url + p) as r:
                return json.loads(r.read())
        self.assertEqual([d["id"] for d in req("/api/demos")["demos"]], IDS)
        self.assertEqual(req("/api/demo-paper")["text"], "")
        old = replay.TOKEN
        replay.TOKEN = server.TOKEN
        try:
            self.assertTrue(replay.post(self.url, "/api/demo", {"id": "hospital-readmission"})["ok"])
        finally:
            replay.TOKEN = old
        self.assertIn("Abstract", req("/api/demo-paper")["text"])


if __name__ == "__main__":
    unittest.main()
