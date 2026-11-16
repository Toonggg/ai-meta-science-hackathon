"""Audit fixes S1-S4: Host and Origin checks, page token, forged attribution, field validation, key safety."""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "episteme"))

import config  # noqa: E402
import llm  # noqa: E402
import server  # noqa: E402
import stitcher  # noqa: E402
from store import Diary, RawLog  # noqa: E402


class ServerSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        server.STORE = Diary(os.path.join(cls.dir, "diary.json"))
        server.RAW = RawLog(os.path.join(cls.dir, "raw.jsonl"))
        server.STITCHER = stitcher.Stitcher(server.STORE, server.RAW, cls.dir, use_ai=False)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.url = "http://127.0.0.1:%d" % cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.STITCHER = None

    def setUp(self):
        server.STORE.clear()

    def call(self, path, body=None, **headers):
        data = None if body is None else json.dumps(body).encode()
        h = {"content-type": "application/json"}
        h.update({k.replace("_", "-"): v for k, v in headers.items()})
        req = urllib.request.Request(self.url + path, data=data, headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read()
                try:
                    return r.status, json.loads(raw)
                except ValueError:
                    return r.status, raw.decode()
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    # S2: DNS rebinding
    def test_foreign_host_refused(self):
        self.assertEqual(self.call("/api/events", Host="evil.example:%d" % self.port)[0], 403)
        self.assertEqual(self.call("/api/raw", {"kind": "stop"}, Host="evil.example:%d" % self.port)[0], 403)
        self.assertEqual(self.call("/api/events", Host="localhost:%d" % self.port)[0], 200)

    # S1: other local pages
    def test_other_local_origin_refused(self):
        self.assertEqual(self.call("/api/raw", {"kind": "stop"}, Origin="http://localhost:3000")[0], 403)
        self.assertEqual(self.call("/api/raw", {"kind": "stop"}, Origin="http://127.0.0.1:%d" % self.port)[0], 200)

    def test_page_actions_need_the_token(self):
        for path in ("/api/settings", "/api/clear", "/api/demo", "/api/confirm", "/api/delete", "/api/pivot"):
            self.assertEqual(self.call(path, {})[0], 403, path)
        self.assertEqual(self.call("/api/clear", {}, x_episteme_token=server.TOKEN)[0], 200)
        self.assertEqual(self.call("/api/clear", {}, x_episteme_token="wrong")[0], 403)

    def test_page_carries_the_token(self):
        st, html = self.call("/")
        self.assertIn(server.TOKEN, html)
        self.assertNotIn("__EPISTEME_TOKEN__", html)

    # S4: forged attribution
    def test_external_event_cannot_claim_the_researcher(self):
        forged = {"type": "pivot", "title": "Switch", "detail": "x", "source": "manual", "actor": "human",
                  "confirmation": "edited", "confirmed_by": "human", "classified_by": {"model": "m"}, "quote": "q"}
        st, r = self.call("/api/events", forged)
        ev = r["event"]
        self.assertEqual(ev["source"], "tool")
        for k in ("actor", "confirmation", "confirmed_by", "classified_by", "quote"):
            self.assertNotIn(k, ev)
        # the page itself still records manual entries as the researcher's
        st, r = self.call("/api/events", {"type": "note", "title": "mine", "source": "manual"}, x_episteme_token=server.TOKEN)
        self.assertEqual((r["event"]["source"], r["event"]["actor"]), ("manual", "human"))

    # S3: fields that end up in markup
    def test_fields_validated(self):
        st, r = self.call("/api/events", {"type": "note", "title": "x", "provenance": "<img src=x onerror=alert(1)>",
                                          "links": ["E1", "<svg onload=alert(2)>", 5], "source": "<b>"})
        ev = r["event"]
        self.assertEqual(ev["provenance"], "stated")
        self.assertEqual(ev["links"], ["E1"])
        # an invalid source must not fall back to "manual" (which would mean "the researcher")
        self.assertEqual(ev["source"], "tool")
        self.assertNotIn("actor", ev)

    def test_bad_bodies_are_400(self):
        req = urllib.request.Request(self.url + "/api/events", data=b"[1]", headers={"content-type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)


class KeySafetyTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        llm.init(self.dir)

    def tearDown(self):
        llm.init(tempfile.mkdtemp())  # leave no key configured for other tests

    def test_key_kept_only_for_the_same_endpoint(self):
        llm.save({"provider": "openai", "base_url": "https://api.berget.ai/v1", "model": "m", "api_key": "sk-test-123"})
        self.assertTrue(llm.status()["has_key"])
        llm.save({"provider": "openai", "base_url": "https://api.berget.ai/v1", "model": "m2"})  # blank key: keep
        self.assertTrue(llm.status()["has_key"])
        llm.save({"provider": "openai", "base_url": "https://evil.example/v1", "model": "m2"})   # new address: drop
        self.assertFalse(llm.status()["has_key"])
        self.assertNotIn("sk-test-123", json.dumps(config.load()))


if __name__ == "__main__":
    unittest.main()
