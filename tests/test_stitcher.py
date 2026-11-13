"""Stitcher tests. They never call a real model: llm is replaced by a fake."""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "episteme"))

import llm  # noqa: E402
import stitcher  # noqa: E402
from store import Diary, RawLog  # noqa: E402

from test_episodes import STOP, act, instr, say  # noqa: E402

SESSION = [
    instr("Train a baseline to predict thermostability from sequence"),
    act("Write", files=["train.py"]),
    act(command="python train.py", output="RESULT spearman=0.71 split=random"),
    say("Baseline reaches 0.71 on a random split."),
    {"kind": "commit", "commit": "a1b2c3d4e5f6", "text": "baseline", "source": "git", "actor": "agent"},
    STOP,
    instr("Check for homology leakage, re-split by sequence similarity"),
    act("Write", files=["split.py"]),
    act(command="python train.py --split cluster", output="RESULT spearman=0.38 split=cluster"),
    say("The random split leaked similar proteins, so 0.71 was inflated."),
    STOP,
]


class Fake:
    """Stands in for llm.structured; records what it was sent."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.prompts = reply, error, []

    def __call__(self, system, user, schema, model=None):
        self.prompts.append(user)
        if self.error:
            raise llm.LLMError(self.error)
        return dict(self.reply)


HUMAN_PIVOT = {"pivot": True, "from": "random split", "to": "cluster split",
               "title": "Switch from random split to cluster split",
               "reason": "The researcher suspected homology leakage.", "reason_source": "human",
               "reason_quote": "Check for homology leakage"}


class StitcherTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.store = Diary(os.path.join(d, "diary.json"))
        self.store.clear()
        self.raw = RawLog(os.path.join(d, "raw.jsonl"))
        self.st = stitcher.Stitcher(self.store, self.raw, d)

    def feed(self, events):
        for ev in events:
            self.raw.add(dict(ev))

    def run_with(self, fake=None, available=True):
        with mock.patch.object(llm, "available", return_value=available), \
                mock.patch.object(llm, "structured", fake or Fake(HUMAN_PIVOT)), \
                mock.patch.object(llm, "stitch_model", return_value="zai-org/GLM-5.3-Flash"):
            self.st.run_once()

    def events(self):
        return self.store.events()

    def types(self):
        return [e["type"] for e in self.events()]

    def test_rules_only_gives_pending_pivot(self):
        self.feed(SESSION)
        self.run_with(available=False)
        self.assertEqual(self.types(), ["plan", "run", "artifact", "pivot", "plan", "run", "surprise"])
        pv = self.events()[3]
        self.assertTrue(pv["pending"])
        self.assertEqual((pv["actor"], pv["provenance"]), ("system", "inferred"))
        self.assertEqual(self.st.status()["pending"], 1)

    def test_rule_events(self):
        self.feed(SESSION)
        self.run_with(available=False)
        ev = {e["type"] + str(i): e for i, e in enumerate(self.events())}
        plan, run, commit = ev["plan0"], ev["run1"], ev["artifact2"]
        self.assertEqual((plan["actor"], plan["provenance"]), ("human", "stated"))
        self.assertEqual(run["result"], "spearman 0.71 (split=random)")
        self.assertEqual(run["detail"], "Agent: Baseline reaches 0.71 on a random split.")
        self.assertEqual(run["raw_ids"], ["R3"])
        self.assertEqual(commit["actor"], "agent")
        drop = ev["surprise6"]
        self.assertEqual(drop["title"], "spearman dropped from 0.71 to 0.38")
        self.assertIn("split=random", drop["detail"])
        self.assertEqual(drop["links"], [run["id"], ev["run5"]["id"]])

    def test_human_quote_accepted(self):
        self.feed(SESSION)
        self.run_with(Fake(HUMAN_PIVOT))
        pv = next(e for e in self.events() if e["type"] == "pivot")
        self.assertEqual((pv["actor"], pv["provenance"]), ("human", "stated"))
        self.assertFalse(pv["needs_confirmation"])
        self.assertEqual(pv["classified_by"]["model"], "zai-org/GLM-5.3-Flash")
        self.assertNotIn("pending", pv)

    def test_agent_quote_needs_confirmation(self):
        self.feed(SESSION)
        reply = dict(HUMAN_PIVOT, reason_source="agent", reason_quote="the random split leaked similar proteins")
        self.run_with(Fake(reply))
        pv = next(e for e in self.events() if e["type"] == "pivot")
        self.assertEqual((pv["actor"], pv["provenance"]), ("agent", "stated"))
        self.assertTrue(pv["needs_confirmation"])

    def test_invented_quote_is_downgraded(self):
        self.feed(SESSION)
        reply = dict(HUMAN_PIVOT, reason_quote="because the reviewer demanded it")
        self.run_with(Fake(reply))
        pv = next(e for e in self.events() if e["type"] == "pivot")
        self.assertEqual((pv["actor"], pv["provenance"]), ("system", "inferred"))
        self.assertTrue(pv["detail"].startswith("Inferred:"))
        self.assertNotIn("quote", pv)

    def test_not_a_pivot_creates_none(self):
        self.feed(SESSION)
        self.run_with(Fake({"pivot": False, "reason_source": "none"}))
        self.assertNotIn("pivot", self.types())

    def test_error_then_retry_updates_in_place(self):
        self.feed(SESSION)
        self.run_with(Fake(error="Rate limited"))
        pending = next(e for e in self.events() if e["type"] == "pivot")
        self.assertTrue(pending["pending"])
        self.assertEqual(self.st.status()["last_error"], "Rate limited")
        self.st.retry_at = 0
        self.run_with(Fake(HUMAN_PIVOT))
        pivots = [e for e in self.events() if e["type"] == "pivot"]
        self.assertEqual(len(pivots), 1)
        self.assertEqual(pivots[0]["id"], pending["id"])
        self.assertNotIn("pending", pivots[0])
        self.assertEqual(self.st.status()["pending"], 0)

    def test_pending_then_not_a_pivot_is_removed(self):
        self.feed(SESSION)
        self.run_with(available=False)
        self.run_with(Fake({"pivot": False}))
        self.assertNotIn("pivot", self.types())

    def test_idempotent(self):
        self.feed(SESSION)
        self.run_with()
        n = len(self.events())
        self.run_with()
        self.assertEqual(len(self.events()), n)

    def test_open_episode_not_stitched(self):
        self.feed(SESSION[:3])  # no stop yet
        self.run_with()
        self.assertEqual(self.events(), [])

    def test_ledger_replaces_drop_surprise(self):
        session = list(SESSION)
        session[6] = instr("Check for homology leakage, re-split by similarity. Expect spearman >= 0.6")
        self.feed(session)
        self.run_with(available=False)
        surprises = [e for e in self.events() if e["type"] == "surprise"]
        self.assertEqual(len(surprises), 1)
        self.assertIn("Expectation contradicted", surprises[0]["title"])

    def test_secrets_not_sent_to_model(self):
        session = list(SESSION)
        session[9] = say("Done. I used OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz to fetch data.")
        self.feed(session)
        fake = Fake(HUMAN_PIVOT)
        self.run_with(fake)
        self.assertTrue(fake.prompts)
        self.assertNotIn("abcdefghijklmnop", fake.prompts[0])

    # -- audit fixes: L1, L4/L5, L6 ------------------------------------------------
    def test_malformed_raw_events_do_not_break_anything(self):
        self.raw.add({"kind": "instruction", "text": 123})
        self.raw.add({"kind": "action", "command": ["python", "a.py"], "output": {"x": 1}, "files": "a.py", "error": "true"})
        self.raw.add({"kind": "stop"})
        evs = self.raw.all()
        self.assertEqual(evs[0]["text"], "123")
        self.assertEqual(evs[1]["files"], ["a.py"])
        self.assertIs(evs[1]["error"], True)
        self.run_with(available=False)  # must not raise
        self.assertEqual(self.st.status()["last_error"], "")

    def test_one_broken_episode_does_not_stop_the_rest(self):
        self.feed(SESSION)
        real = stitcher.Stitcher._stitch
        calls = []

        def flaky(this, ep, prev, raw_by):
            calls.append(ep["id"])
            if len(calls) == 1:
                raise RuntimeError("boom")
            return real(this, ep, prev, raw_by)
        with mock.patch.object(stitcher.Stitcher, "_stitch", flaky):
            self.run_with(available=False)
            self.run_with(available=False)  # a failed episode is not retried (no duplicates)
        self.assertEqual(len(calls), 2)
        self.assertIn("boom", self.st.status()["last_error"])
        self.assertIn("plan", self.types())  # the second episode still made it

    def test_slow_model_does_not_block_confirm_or_status(self):
        import threading
        import time as _time
        self.feed(SESSION)
        started, release = threading.Event(), threading.Event()

        def slow(system, user, schema, model=None):
            started.set()
            release.wait(5)
            return dict(HUMAN_PIVOT)
        t = threading.Thread(target=self.run_with, args=(slow,))
        t.start()
        self.assertTrue(started.wait(5))
        t0 = _time.time()
        self.st.status()
        pv = next(e for e in self.events() if e["type"] == "pivot")  # pending pivot is already visible
        self.assertTrue(pv["pending"])
        self.st.human_handled(dict(pv, confirmation="skipped"))
        self.assertLess(_time.time() - t0, 1.0)
        release.set()
        t.join(5)

    def test_clear_during_model_call_drops_the_answer(self):
        import threading
        self.feed(SESSION)
        started, release = threading.Event(), threading.Event()

        def slow(system, user, schema, model=None):
            started.set()
            release.wait(5)
            return dict(HUMAN_PIVOT)
        t = threading.Thread(target=self.run_with, args=(slow,))
        t.start()
        self.assertTrue(started.wait(5))
        self.st.reset(also=lambda: (self.store.clear(), self.raw.clear()))
        release.set()
        t.join(5)
        self.assertEqual(self.events(), [])

    def test_stated_reason_is_the_source_text_verbatim(self):
        self.feed(SESSION)
        self.run_with(Fake(dict(HUMAN_PIVOT, reason_quote="check for HOMOLOGY   leakage")))
        pv = next(e for e in self.events() if e["type"] == "pivot")
        self.assertEqual(pv["detail"], "Check for homology leakage")  # as the researcher typed it
        self.assertEqual(pv["quote"], "Check for homology leakage")
        self.assertEqual(pv["model_summary"], HUMAN_PIVOT["reason"])

    def test_two_word_quote_is_not_enough(self):
        self.feed(SESSION)
        self.run_with(Fake(dict(HUMAN_PIVOT, reason_quote="homology leakage")))
        pv = next(e for e in self.events() if e["type"] == "pivot")
        self.assertEqual(pv["actor"], "system")

    def test_no_ai_flag_never_calls_model(self):
        self.st.use_ai = False
        self.feed(SESSION)
        fake = Fake(HUMAN_PIVOT)
        self.run_with(fake)
        self.assertEqual(fake.prompts, [])
        self.assertEqual(self.st.status()["pending"], 1)


if __name__ == "__main__":
    unittest.main()
