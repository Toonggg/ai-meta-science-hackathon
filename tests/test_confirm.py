"""Confirm / edit / skip for pivots, attribution labels, and exports. No real model calls."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "episteme"))

import diary  # noqa: E402
import export  # noqa: E402
import llm  # noqa: E402
import stitcher  # noqa: E402
from store import Diary, RawLog  # noqa: E402

from test_stitcher import HUMAN_PIVOT, SESSION, Fake  # noqa: E402

AGENT_PIVOT = dict(HUMAN_PIVOT, reason_source="agent", reason="The random split leaked similar proteins.",
                   reason_quote="the random split leaked similar proteins")


class ConfirmTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.store = Diary(os.path.join(d, "diary.json"))
        self.store.clear()
        self.raw = RawLog(os.path.join(d, "raw.jsonl"))
        self.st = stitcher.Stitcher(self.store, self.raw, d)
        for ev in SESSION:
            self.raw.add(dict(ev))

    def stitch(self, reply=None, available=True):
        with mock.patch.object(llm, "available", return_value=available), \
                mock.patch.object(llm, "structured", Fake(reply or AGENT_PIVOT)), \
                mock.patch.object(llm, "stitch_model", return_value="flash"):
            self.st.run_once()

    def pivot(self):
        return next(e for e in self.store.events() if e["type"] == "pivot")

    def test_agent_pivot_is_prompted(self):
        self.stitch()
        p = diary.prompts(self.store.snapshot()["events"])
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]["actions"], ["confirm", "edit", "skip"])
        self.assertEqual(p[0]["who"], "stated by the AI agent")

    def test_human_pivot_is_not_prompted(self):
        self.stitch(HUMAN_PIVOT)
        self.assertEqual(diary.prompts(self.store.snapshot()["events"]), [])

    def test_confirm(self):
        self.stitch()
        ev = diary.confirm(self.store, self.pivot()["id"], "confirm")
        self.assertEqual((ev["actor"], ev["confirmation"], ev["confirmed_by"]), ("agent", "confirmed", "human"))
        self.assertEqual(diary.who(ev), "stated by the AI agent, confirmed by the researcher")
        self.assertEqual(diary.prompts(self.store.events()), [])

    def test_edit_keeps_proposal(self):
        self.stitch()
        ev = diary.confirm(self.store, self.pivot()["id"], "edit", "Reviewer 2 asked for a homology-aware split.")
        self.assertEqual((ev["actor"], ev["provenance"]), ("human", "stated"))
        self.assertEqual(ev["detail"], "Reviewer 2 asked for a homology-aware split.")
        self.assertEqual(ev["proposed_reason"], "The random split leaked similar proteins")  # source text, verbatim
        self.assertNotIn("quote", ev)

    def test_skip(self):
        self.stitch()
        ev = diary.confirm(self.store, self.pivot()["id"], "skip")
        self.assertEqual(diary.who(ev), "stated by the AI agent, not confirmed (researcher skipped)")
        self.assertEqual(diary.prompts(self.store.events()), [])

    def test_pending_cannot_be_confirmed_but_can_be_edited(self):
        self.stitch(available=False)
        pid = self.pivot()["id"]
        self.assertEqual(diary.prompts(self.store.snapshot()["events"])[0]["actions"], ["edit", "skip"])
        with self.assertRaises(ValueError):
            diary.confirm(self.store, pid, "confirm")
        ev = diary.confirm(self.store, pid, "edit", "Suspected leakage.")
        self.assertNotIn("pending", ev)
        self.assertNotIn("proposed_reason", ev)  # the rules' placeholder is not a proposal
        self.assertTrue(ev["title"].startswith("Change of approach"))

    def test_model_never_overwrites_human_edit(self):
        self.stitch(available=False)
        ev = diary.confirm(self.store, self.pivot()["id"], "edit", "Suspected leakage.")
        self.st.human_handled(ev)
        self.stitch(AGENT_PIVOT)
        self.assertEqual(self.pivot()["detail"], "Suspected leakage.")

    def test_model_racing_an_edit_does_not_overwrite(self):
        self.stitch(available=False)
        diary.confirm(self.store, self.pivot()["id"], "edit", "Suspected leakage.")
        # human_handled not called yet: the model pass is already running
        self.stitch(AGENT_PIVOT)
        self.assertEqual(self.pivot()["detail"], "Suspected leakage.")

    def test_bad_requests(self):
        self.stitch()
        with self.assertRaises(ValueError):
            diary.confirm(self.store, self.pivot()["id"], "edit", "   ")
        with self.assertRaises(ValueError):
            diary.confirm(self.store, self.pivot()["id"], "approve")
        with self.assertRaises(KeyError):
            diary.confirm(self.store, "E999", "skip")
        plan = next(e for e in self.store.events() if e["type"] == "plan")
        with self.assertRaises(ValueError):
            diary.confirm(self.store, plan["id"], "skip")

    def test_ask_heuristic_names_the_agent(self):
        self.stitch()
        diary.confirm(self.store, self.pivot()["id"], "confirm")
        events = self.store.snapshot()["events"]
        ans = diary.ask_heuristic("why step %d?" % self.pivot()["step"], events)
        self.assertIn("stated by the AI agent, confirmed by the researcher", ans)

    def test_exports_keep_attribution(self):
        self.stitch()
        diary.confirm(self.store, self.pivot()["id"], "confirm")
        snap = self.store.snapshot()
        md = export.to_markdown(snap)
        self.assertIn("**Stated by:** stated by the AI agent, confirmed by the researcher", md)
        self.assertIn("**Classified by:** flash", md)
        self.assertIn("**Raw evidence:** R", md)
        self.assertIn("```bash", md)
        prov = json.loads(export.to_prov(snap))
        roles = {(r["prov:agent"], r["prov:role"]) for r in prov["wasAttributedTo"].values()}
        self.assertIn(("ep:researcher", "ep:confirmer"), roles)
        self.assertIn(("ep:model_flash", "ep:classifier"), roles)
        self.assertIn(("ep:ai_assistant", "ep:author"), roles)


if __name__ == "__main__":
    unittest.main()


class ExpectationTest(unittest.TestCase):
    """Audit fix L10: only cued comparisons are expectations, and metric names match whole words."""

    def test_extract(self):
        cases = {
            "Train with lr=0.001 and batch 32. I expect auroc >= 0.75.": "auroc >= 0.75",
            "Report whether it is significant at p<0.05": None,
            "Use lr=0.001": None,
            "Target: spearman > 0.6 on the family split": "spearman > 0.6",
            "This should beat rmse < 2.5": "rmse < 2.5",
        }
        for text, want in cases.items():
            self.assertEqual(diary.extract_expectation(text), want, text)

    def test_whole_word_metric(self):
        self.assertIsNone(diary.check_expectation("p<0.05", "spearman 0.71"))
        self.assertEqual(diary.check_expectation("auroc >= 0.75", "AUROC 0.54 (5-fold CV)")[4], False)
