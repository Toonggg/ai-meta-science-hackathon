"""Saved studies: a new notebook or a demo never deletes another study."""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "episteme"))

import server  # noqa: E402
import studies  # noqa: E402


class StudiesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        server.open_state(self.dir, use_ai=False)

    def tearDown(self):
        server.STITCHER = server.STUDIES = None
        shutil.rmtree(self.dir, ignore_errors=True)

    def add_run(self, title):
        return server.STORE.add({"type": "run", "title": title, "source": "manual"})

    def test_fresh_install_opens_one_blank_study_that_is_not_listed(self):
        self.assertTrue(server.STUDIES.current())
        self.assertEqual(server.STUDIES.list(), [])
        self.assertEqual(server.STORE.events(), [])

    def test_new_study_keeps_the_old_one(self):
        first = server.new_study("First")
        self.add_run("first run")
        server.RAW.add({"kind": "instruction", "text": "first study capture"})
        second = server.new_study("Second")
        self.assertNotEqual(first, second)
        self.assertEqual((server.STORE.events(), server.RAW.all()), ([], []))
        self.add_run("second run")
        server.open_study(first)
        self.assertEqual([e["title"] for e in server.STORE.events()], ["first run"])
        self.assertEqual([r["text"] for r in server.RAW.all()], ["first study capture"])
        self.assertEqual(server.STUDIES.current(), first)
        self.assertEqual(sorted(i["project"] for i in server.STUDIES.list()), ["First", "Second"])

    def test_blank_study_is_reused(self):
        blank = server.STUDIES.current()
        self.assertEqual(server.new_study("Named"), blank)
        self.assertEqual(server.STORE.snapshot()["project"], "Named")
        self.assertEqual(len(os.listdir(server.STUDIES.dir)), 1)

    def test_demo_opens_its_saved_copy(self):
        server.new_study("Mine")
        self.add_run("my run")
        server.open_demo("alphafold")
        demo_sid = server.STUDIES.current()
        n = len(server.STORE.events())
        server.STORE.add({"type": "note", "title": "my note on the demo", "source": "manual"})
        server.new_study("Other")
        server.open_demo("alphafold")
        self.assertEqual(server.STUDIES.current(), demo_sid)  # same copy, not a fresh load
        self.assertEqual(len(server.STORE.events()), n + 1)
        self.assertIn("Mine", [i["project"] for i in server.STUDIES.list()])

    def test_stitch_state_follows_the_study(self):
        server.open_demo("hospital-readmission")
        stitched = server.STITCHER.status()["stitched"]
        self.assertTrue(stitched)
        server.new_study("Empty")
        self.assertEqual(server.STITCHER.status()["stitched"], 0)
        server.STITCHER.run_once(ask_model=False)
        self.assertEqual(server.STORE.events(), [])
        server.open_demo("hospital-readmission")
        server.STITCHER.run_once(ask_model=False)  # must not stitch the demo a second time
        self.assertEqual(server.STITCHER.status()["stitched"], stitched)
        self.assertEqual(len([e for e in server.STORE.events() if e["type"] == "plan"]), 2)

    def test_delete(self):
        first = server.new_study("First")
        server.new_study("Second")
        with self.assertRaises(ValueError):
            server.STUDIES.delete(server.STUDIES.current())  # never the open one
        server.STUDIES.delete(first)
        self.assertEqual([i["project"] for i in server.STUDIES.list()], ["Second"])
        with self.assertRaises(KeyError):
            server.STUDIES.delete("../../etc")

    def test_diary_from_before_saved_studies_is_kept(self):
        server.STITCHER = server.STUDIES = None
        old = tempfile.mkdtemp()
        with open(os.path.join(old, "diary.json"), "w") as f:
            json.dump({"project": "Old one", "next_id": 2, "events": [{"id": "E1", "type": "plan", "title": "p"}]}, f)
        with open(os.path.join(old, "raw.jsonl"), "w") as f:
            f.write('{"kind": "instruction", "text": "x", "rid": "R1"}\n')
        server.open_state(old, use_ai=False)
        self.assertFalse(os.path.exists(os.path.join(old, "diary.json")))
        self.assertEqual(server.STORE.snapshot()["project"], "Old one")
        self.assertEqual(len(server.RAW.all()), 1)
        shutil.rmtree(old, ignore_errors=True)


class StudiesApiTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        server.open_state(self.dir, use_ai=False)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.STITCHER = server.STUDIES = None
        shutil.rmtree(self.dir, ignore_errors=True)

    def call(self, path, body=None, token=True):
        headers = {"content-type": "application/json"}
        if token:
            headers["x-episteme-token"] = server.TOKEN
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_flow(self):
        self.assertEqual(self.call("/api/studies")[1]["studies"], [])
        self.assertEqual(self.call("/api/studies/new", {"project": "A"}, token=False)[0], 403)
        self.assertEqual(self.call("/api/studies/new", {})[0], 400)
        a = self.call("/api/studies/new", {"project": "A"})[1]["id"]
        self.assertEqual(self.call("/api/demo", {"id": "alphafold"})[0], 200)
        listed = self.call("/api/studies")[1]
        self.assertEqual(len(listed["studies"]), 2)
        self.assertNotEqual(listed["current"], a)
        self.assertTrue([d for d in self.call("/api/demos")[1]["demos"] if d["id"] == "alphafold"][0]["saved"])
        self.assertEqual(self.call("/api/studies/delete", {"id": listed["current"]})[0], 400)
        self.assertEqual(self.call("/api/studies/open", {"id": a})[1]["events"], 0)
        self.assertEqual(self.call("/api/studies/open", {"id": "nope"})[0], 400)
        self.assertEqual(self.call("/api/studies/delete", {"id": listed["current"]})[0], 200)
        self.assertEqual([s["project"] for s in self.call("/api/studies")[1]["studies"]], ["A"])


if __name__ == "__main__":
    unittest.main()
