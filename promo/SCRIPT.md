# Episteme promo: script

About 658 words. Length with the current voice: 04:45.

Generated from `promo/scenes.json` by `promo/build.py`. Edit the JSON, not this file.

To replace the voice, record one file per scene (text in `promo/voice-text/<id>.txt`), save it as
`promo/voice/<id>.mp3` and run `python3 promo/build.py` again. See the top of `build.py`.

## 01-hook (00:00 to 00:14)

**Slide 1** (hero): Why did they change approach at step 4?

> Why did they change approach at step four?

**Slide 2** (hero): Why did they change approach at step 4?

> It's the simplest question a reviewer can ask about a study. And most of the time, nobody can answer it. Not even the people who did the work.

## 02-problem (00:14 to 00:36)

**Slide 1** (points): Research keeps its results. It loses its reasons.

> A paper reports the path that worked.

**Slide 2** (points): Research keeps its results. It loses its reasons.

> The dead ends, the failed runs, the expectation that turned out wrong, and the moment someone said: this isn't working, let's try something else. None of that survives.

**Slide 3** (points): Research keeps its results. It loses its reasons.

> Lab notebooks were meant to hold it. But they're written after the fact, from memory, if they're written at all.

## 03-reproducibility (00:36 to 00:58)

**Slide 1** (stat): 

> This is not a small gap. In a 2016 Nature survey of more than fifteen hundred researchers, over seventy percent said they had tried and failed to reproduce another scientist's experiments.

**Slide 2** (stat): 

> And when a result can't be reproduced, the first question is always the same. What exactly did they do, and why?

## 04-agents (00:58 to 01:24)

**Slide 1** (stream): The work is now done with AI agents

> And the way research is done is changing. More and more analysis code is written and run by AI agents, like Claude Code, working alongside the researcher.

**Slide 2** (stream): The work is now done with AI agents

> An agent can take hundreds of actions in an afternoon. The researcher's decisions, the why behind each change, get buried in chat logs and terminal scrollback.

**Slide 3** (hero): The faster the work goes, the less of it anyone can reconstruct.

> The faster the work goes, the less of it anyone can reconstruct.

## 05-meet (01:24 to 01:39)

**Slide 1** (hero): Episteme

> Meet Episteme: a flight recorder for AI-assisted research.

**Slide 2** (hero): Episteme

> It records what was planned, what was run, what happened, and why the approach changed. While the work happens, not afterwards.

## 06-capture (01:39 to 02:13)

**Slide 1** (flow): Capture everything. Keep the decisions.

> You install two hooks: one in Claude Code, and one in git. From then on, every instruction, command, result and commit is captured automatically, into a raw log on your own machine.

**Slide 2** (flow): Capture everything. Keep the decisions.

> Episteme groups that stream into episodes, and turns each one into a short diary of decisions: plans, runs, surprises, and changes of approach.

**Slide 3** (shot): Every entry points back to its evidence [screenshot: raw-capture.jpg]

> The raw log keeps everything. The diary keeps only what a reviewer needs, and every diary entry points back to the raw evidence behind it.

## 07-timeline (02:13 to 02:47)

**Slide 1** (shot): A study, step by step [screenshot: timeline.jpg]

> Here's what that looks like, on a demo study that predicts hospital readmission from clinical notes.

**Slide 2** (shot): The expectation, stated up front [screenshot: timeline.jpg]

> Step one: the researcher's plan, with an expectation stated up front. An AUROC of at least 0.75.

**Slide 3** (shot): The agent runs the baseline [screenshot: timeline.jpg]

> Step two: the agent runs a baseline. The result is 0.54.

**Slide 4** (shot): Contradictions are caught automatically [screenshot: timeline.jpg]

> Step three: Episteme notices, on its own, that the result contradicts the expectation, and records a surprise. Nobody had to write it down.

## 08-pivot (02:47 to 03:17)

**Slide 1** (shot): A change of approach asks why [screenshot: timeline.jpg]

> Step four is the change of approach. Episteme's rules flag it, and ask for the reason, in the researcher's own words.

**Slide 2** (badges): Quoted, or marked as inferred

> If a language model is connected, it proposes the reason, but only as a word-for-word quote of what was said at the time. Anything it can't quote is marked as inferred, and never presented as fact.

**Slide 3** (shot): One click to confirm [screenshot: pivot-and-ask.jpg]

> The researcher confirms it with one click. Now the reason is on the record, linked to the surprise that triggered it.

## 09-attribution (03:17 to 03:30)

**Slide 1** (badges): Every entry says who stated it

> Every entry carries a badge: stated by the researcher, stated by the agent, or inferred by Episteme's own rules. So a reviewer always knows how much weight each line can bear.

## 10-evidence (03:30 to 03:42)

**Slide 1** (shot): What was actually run [screenshot: run-evidence.jpg]

> Open any run, and you see what was actually executed: the command, its parameters, and its result.

**Slide 2** (shot): One click to the raw capture [screenshot: run-evidence.jpg]

> And one click further, the raw capture it came from.

## 11-ask (03:42 to 04:02)

**Slide 1** (shot): Ask the log [screenshot: pivot-and-ask.jpg]

> Now, the reviewer who wasn't there can simply ask the log.

**Slide 2** (shot): An answer that cites the record [screenshot: pivot-and-ask.jpg]

> Why did they change approach at step four? The answer comes back with citations: the reason, stated by the researcher, and the surprise that triggered it. Answers cite only entries in the diary, so there is no invented history.

## 12-export (04:02 to 04:13)

**Slide 1** (doc): The decision record, ready for the paper

> When it's time to publish, export the record as a Markdown decision appendix for your paper, or as W3C PROV-JSON for provenance tools.

## 13-private (04:13 to 04:35)

**Slide 1** (points): Yours, and local

> Episteme runs entirely on your machine.

**Slide 2** (points): Yours, and local

> Secrets are stripped from captured text before anything is stored.

**Slide 3** (points): Yours, and local

> It works with no model at all, or with Claude, OpenAI, Gemini, or a local model through Ollama.

**Slide 4** (points): Yours, and local

> And every study is saved separately, so you can move between projects at any time.

## 14-close (04:35 to 04:45)

**Slide 1** (hero): Research moves faster than ever. Episteme keeps the documentation with it.

> Research moves faster than ever. Episteme makes sure the documentation keeps up.

**Slide 2** (hero): Episteme

> Episteme. Keep the why.
