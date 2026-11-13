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

    def test_no_ai_flag_never_calls_model(self):
        self.st.use_ai = False
        self.feed(SESSION)
        fake = Fake(HUMAN_PIVOT)
        self.run_with(fake)
        self.assertEqual(fake.prompts, [])
        self.assertEqual(self.st.status()["pending"], 1)


if __name__ == "__main__":
    unittest.main()
