import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "episteme"))

import episodes  # noqa: E402
from store import Diary, RawLog  # noqa: E402


def raw(*events):
    """Give each event an rid in order, like RawLog would."""
    out = []
    for i, ev in enumerate(events, 1):
        ev = dict(ev)
        ev["rid"] = "R%d" % i
        ev.setdefault("ts", "2026-11-14T14:%02d:00+01:00" % i)
        out.append(ev)
    return out


def instr(text):
    return {"kind": "instruction", "text": text}


def act(tool="Bash", command="", output="", error=False, files=None):
    return {"kind": "action", "tool": tool, "command": command, "output": output, "error": error, "files": files or []}


def say(text):
    return {"kind": "agent_text", "text": text}


STOP = {"kind": "stop"}


# The example session from the design discussion: baseline, leakage check, pivot.
SESSION = raw(
    instr("Train a baseline to predict thermostability from sequence"),          # R1  opens EP-R1
    act("Read", files=["data.csv"]),                                              # R2
    act("Write", files=["train.py"]),                                             # R3
    act(command="python train.py", output="KeyError: 'tm'", error=True),         # R4  error, quick fix
    act("Edit", files=["train.py"]),                                              # R5
    act(command="python train.py", output="RESULT spearman=0.71 split=random"),  # R6  closes (result)
    say("Baseline reaches 0.71 on a random split."),                              # R7  tail
    {"kind": "commit", "commit": "a1b2c3d", "text": "baseline", "source": "git"},  # R8  tail
    STOP,                                                                          # R9  final
    instr("Check for homology leakage, re-split by sequence similarity"),         # R10 opens EP-R10
    act(command="pip install mmseqs2"),                                           # R11 not a run
    act("Write", files=["split.py"]),                                             # R12
    act(command="python train.py --split cluster",
        output="RESULT spearman=0.38 split=cluster"),                             # R13 closes (result)
    say("The random split leaked similar proteins; real performance is much lower."),  # R14
    STOP,                                                                          # R15
    instr("Switch to protein language model embeddings"),                         # R16 opens EP-R16
    act("Write", files=["embed.py"]),                                             # R17
)


class SegmentTest(unittest.TestCase):
    def setUp(self):
        self.eps = episodes.segment(SESSION)

    def test_three_episodes_one_per_instruction(self):
        self.assertEqual([e["id"] for e in self.eps], ["EP-R1", "EP-R10", "EP-R16"])

    def test_quick_fix_does_not_split(self):
        ep = self.eps[0]
        self.assertEqual(ep["close_reason"], "result")
        self.assertEqual(ep["closed_at"], "R6")
        self.assertEqual(len(ep["runs"]), 2)

    def test_tail_belongs_to_episode(self):
        ep = self.eps[0]
        self.assertIn("R7", ep["raw_ids"])        # agent's explanation after the result
        self.assertEqual(ep["commits"][0]["hash"], "a1b2c3d")
        self.assertTrue(ep["final"])

    def test_install_is_not_a_run(self):
        self.assertEqual([r["rid"] for r in self.eps[1]["runs"]], ["R13"])

    def test_metric_drop_flagged(self):
        ep = self.eps[1]
        self.assertIn("metric_drop", ep["flags"])
        self.assertEqual(ep["drops"][0]["before"], 0.71)
        self.assertEqual(ep["drops"][0]["after"], 0.38)
        self.assertIn("change_words", ep["flags"])  # "re-split"

    def test_new_direction_after_drop(self):
        self.assertIn("new_direction", self.eps[2]["flags"])
        self.assertIn("change_words", self.eps[2]["flags"])  # "Switch"

    def test_last_episode_open(self):
        self.assertFalse(self.eps[2]["final"])
        self.assertIsNone(self.eps[2]["close_reason"])

    def test_ids_stable_as_log_grows(self):
        for n in range(1, len(SESSION) + 1):
            prefix = episodes.segment(SESSION[:n])
            for ep in prefix:
                if ep["final"]:
                    full = next(e for e in self.eps if e["id"] == ep["id"])
                    self.assertEqual(ep["raw_ids"], full["raw_ids"][:len(ep["raw_ids"])])


class RuleTest(unittest.TestCase):
    def test_trivial_instructions(self):
        for t in ["yes", "ok", "continue", "go ahead", "fix that", "Sounds good, thanks"]:
            self.assertTrue(episodes.is_trivial(t), t)
        for t in ["Train a baseline", "ok, switch to embeddings instead", "Use a cluster split"]:
            self.assertFalse(episodes.is_trivial(t), t)

    def test_trivial_instruction_joins_episode(self):
        eps = episodes.segment(raw(instr("Train a model"), act(command="python a.py", output="x"), instr("continue"),
                                   act(command="python a.py", output="RESULT acc=0.9")))
        self.assertEqual(len(eps), 1)

    def test_continuation_after_stop(self):
        eps = episodes.segment(raw(instr("Train a model"), act(command="python a.py", output="RESULT acc=0.9"), STOP,
                                   instr("ok go on"), act("Edit", files=["a.py"])))
        self.assertEqual([e["opened_by"] for e in eps], ["instruction", "continuation"])

    def test_real_error_closes(self):
        eps = episodes.segment(raw(instr("Train"), act(command="python a.py", output="Traceback", error=True),
                                   act("Read"), act("Read"), instr("Try a smaller batch instead")))
        self.assertEqual(eps[0]["close_reason"], "error")
        self.assertIn("failure", eps[0]["flags"])
        self.assertIn("new_direction", eps[1]["flags"])

    def test_error_then_stop_closes(self):
        eps = episodes.segment(raw(instr("Train"), act(command="python a.py", error=True), STOP))
        self.assertEqual(eps[0]["close_reason"], "error")
        self.assertTrue(eps[0]["final"])

    def test_error_undecided_without_lookahead(self):
        eps = episodes.segment(raw(instr("Train"), act(command="python a.py", error=True)))
        self.assertIsNone(eps[0]["close_reason"])

    def test_commit_closes(self):
        eps = episodes.segment(raw(instr("Clean data"), act("Edit", files=["c.py"]),
                                   {"kind": "commit", "commit": "abc", "text": "clean"}, act("Edit")))
        self.assertEqual(eps[0]["close_reason"], "commit")
        self.assertEqual(eps[1]["opened_by"], "activity")

    def test_cap_splits(self):
        evs = [instr("Refactor everything")] + [act("Edit", files=["f%d.py" % i]) for i in range(35)]
        eps = episodes.segment(raw(*evs))
        self.assertEqual(eps[0]["close_reason"], "cap")
        self.assertEqual(eps[0]["significant"], episodes.MAX_SIGNIFICANT)
        self.assertEqual(len(eps), 2)

    def test_lower_is_better_metric(self):
        eps = episodes.segment(raw(instr("A"), act(command="python a.py", output="RESULT val_loss=0.30"), STOP,
                                   instr("B"), act(command="python a.py", output="RESULT val_loss=0.25")))
        self.assertNotIn("metric_drop", eps[1]["flags"])

    def test_parse_results(self):
        r = episodes.parse_results("epoch 3\nRESULT spearman=0.71 split=random n='1,204'\nRESULT acc=91%")
        self.assertEqual(r["metrics"], {"spearman": 0.71, "acc": 91.0})
        self.assertEqual(r["context"], {"split": "random", "n": "1,204"})
        self.assertIsNone(episodes.parse_results("no results here"))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_rawlog_ids_survive_restart(self):
        p = os.path.join(self.dir, "raw.jsonl")
        log = RawLog(p)
        self.assertEqual(log.add({"kind": "instruction", "text": "hi"})["rid"], "R1")
        self.assertEqual(log.add({"kind": "stop"})["rid"], "R2")
        log2 = RawLog(p)
        self.assertEqual(log2.add({"kind": "stop", "rid": "R99"})["rid"], "R3")  # sender cannot pick ids
        self.assertEqual([e["rid"] for e in log2.get(["R1", "R3"])], ["R1", "R3"])

    def test_rawlog_rejects_unknown_kind(self):
        with self.assertRaises(ValueError):
            RawLog(os.path.join(self.dir, "r.jsonl")).add({"kind": "banana"})

    def test_rawlog_skips_torn_line(self):
        p = os.path.join(self.dir, "raw.jsonl")
        log = RawLog(p)
        log.add({"kind": "stop"})
        with open(p, "a") as f:
            f.write('{"kind": "act')
        self.assertEqual(len(log.all()), 1)

    def test_actor_defaults(self):
        d = Diary(os.path.join(self.dir, "diary.json"))
        d.clear()
        self.assertEqual(d.add({"type": "note", "title": "x"})["actor"], "human")
        self.assertEqual(d.add({"type": "surprise", "title": "x", "source": "episteme"})["actor"], "system")
        self.assertEqual(d.add({"type": "plan", "title": "x", "source": "agent", "actor": "human"})["actor"], "human")
        self.assertNotIn("actor", d.add({"type": "note", "title": "x", "source": "colab"}))


if __name__ == "__main__":
    unittest.main()
