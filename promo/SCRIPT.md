# Episteme promo: script

About 740 words. Length with the current voice: 05:19.

Generated from `promo/scenes.json` by `promo/build.py`. Edit the JSON, not this file.

To replace the voice, record one file per scene (text in `promo/voice-text/<id>.txt`), save it as
`promo/voice/<id>.mp3` and run `python3 promo/build.py` again. See the top of `build.py`.

## 00-hook (00:00 to 00:38)

**Slide 1** (hero): You're a researcher. You want your work to be reproducible.

> Picture yourself as a researcher. You want your work to be reproducible.

**Slide 2** (hero): You're a researcher. You want your work to be reproducible.

> Anyone who reads it should be able to follow what you did, and why you did it.

**Slide 3** (points): So you keep a notebook. It records what, rarely why.

> So you keep a notebook. But you write it at the end of the day, from memory, when there's time.

**Slide 4** (points): So you keep a notebook. It records what, rarely why.

> It records what you ran and what came out. It rarely records why you dropped one approach for another.

**Slide 5** (points): So you keep a notebook. It records what, rarely why.

> And nothing ties a note to the exact code, run or output it describes.

**Slide 6** (hero): Months later, someone reads your paper.

> Months later, someone reads your paper. A reviewer, a colleague who wants to build on it, or you, a year from now. And they ask a simple question.

## 01-hook (00:38 to 00:50)

**Slide 1** (hero): Why did you change approach halfway through?

> Why did you change approach halfway through?

**Slide 2** (hero): Why did you change approach halfway through?

> It sounds simple. But most of the time, nobody can answer it accurately. Not even the people who did the work.

## 02-problem (00:50 to 01:05)

**Slide 1** (points): Research keeps its results. It loses its reasons.

> A paper reports the path that worked.

**Slide 2** (points): Research keeps its results. It loses its reasons.

> The dead ends, the failed runs, the expectation that turned out wrong, and the moment someone said: this isn't working, let's try something else. None of that survives.

## 03-reproducibility (01:05 to 01:27)

**Slide 1** (stat): 

> This is not a small gap. In a 2016 Nature survey of more than fifteen hundred researchers, over seventy percent said they had tried and failed to reproduce another scientist's experiments.

**Slide 2** (stat): 

> And when a result can't be reproduced, the first question is always the same. What exactly did they do, and why?

## 04-agents (01:27 to 01:55)

**Slide 1** (stream): The work is now done with AI agents

> And the way research is done is changing. More and more analysis code is written and run by AI agents, like Claude Code, working alongside the researcher.

**Slide 2** (stream): The work is now done with AI agents

> An agent can take hundreds of actions in an afternoon. The researcher's decisions, the why behind each change, get buried in chat logs and terminal scrollback.

**Slide 3** (hero): The faster the work goes, the less of it anyone can reconstruct.

> The faster the work goes, the less of it anyone can reconstruct.

## 05-meet (01:55 to 02:10)

**Slide 1** (hero): Episteme

> Meet Episteme: a flight recorder for AI-assisted research.

**Slide 2** (hero): Episteme

> It records what was planned, what was run, what happened, and why the approach changed. While the work happens, not afterwards.

## 06-capture (02:10 to 02:45)

**Slide 1** (flow): Capture everything. Keep the decisions.

> You install two hooks: one in Claude Code, and one in git. From then on, every instruction, command, result and commit is captured automatically, into a raw log on your own machine.

**Slide 2** (flow): Capture everything. Keep the decisions.

> Episteme groups that stream into episodes, and turns each one into a short diary of decisions: plans, runs, surprises, and changes of approach.

**Slide 3** (shot): Every entry points back to its evidence [screenshot: raw-capture.jpg]

> The raw log keeps everything. The diary keeps only what a reviewer needs, and every diary entry points back to the raw evidence behind it.

## 07-timeline (02:45 to 03:18)

**Slide 1** (shot): A study, step by step [screenshot: timeline.jpg]

> Here's what that looks like, on a demo study that predicts hospital readmission from clinical notes.

**Slide 2** (shot): The expectation, stated up front [screenshot: timeline.jpg]

> Step one: the researcher's plan, with an expectation stated up front. An AUROC of at least 0.75.

**Slide 3** (shot): The agent runs the baseline [screenshot: timeline.jpg]

> Step two: the agent runs a baseline. The result is 0.54.

**Slide 4** (shot): Contradictions are caught automatically [screenshot: timeline.jpg]

> Step three: Episteme notices, on its own, that the result contradicts the expectation, and records a surprise. Nobody had to write it down.

## 08-pivot (03:18 to 03:49)

**Slide 1** (shot): A change of approach asks why [screenshot: timeline.jpg]

> Step four is the change of approach. Episteme's rules flag it, and ask for the reason, in the researcher's own words.

**Slide 2** (badges): Quoted, or marked as inferred

> If a language model is connected, it proposes the reason, but only as a word-for-word quote of what was said at the time. Anything it can't quote is marked as inferred, and never presented as fact.

**Slide 3** (shot): One click to confirm [screenshot: pivot-and-ask.jpg]

> The researcher confirms it with one click. Now the reason is on the record, linked to the surprise that triggered it.

## 09-attribution (03:49 to 04:03)

**Slide 1** (badges): Every entry says who stated it

> Every entry carries a badge: stated by the researcher, stated by the agent, or inferred by Episteme's own rules. So a reviewer always knows how much weight each line can bear.

## 10-evidence (04:03 to 04:16)

**Slide 1** (shot): What was actually run [screenshot: run-evidence.jpg]

> Open any run, and you see what was actually executed: the command, its parameters, and its result.

**Slide 2** (shot): One click to the raw capture [screenshot: run-evidence.jpg]

> And one click further, the raw capture it came from.

## 11-ask (04:16 to 04:36)

**Slide 1** (shot): Ask the log [screenshot: pivot-and-ask.jpg]

> Now, the reviewer who wasn't there can simply ask the log.

**Slide 2** (shot): An answer that cites the record [screenshot: pivot-and-ask.jpg]

> Why did they change approach at step four? The answer comes back with citations: the reason, stated by the researcher, and the surprise that triggered it. Answers cite only entries in the diary, so there is no invented history.

## 12-export (04:36 to 04:48)

**Slide 1** (doc): The decision record, ready for the paper

> When it's time to publish, export the record as a Markdown decision appendix for your paper, or as W3C PROV-JSON for provenance tools.

## 13-private (04:48 to 05:10)

**Slide 1** (points): Yours, and local

> Episteme runs entirely on your machine.

**Slide 2** (points): Yours, and local

> Secrets are stripped from captured text before anything is stored.

**Slide 3** (points): Yours, and local

> It works with no model at all, or with Claude, OpenAI, Gemini, or a local model through Ollama.

**Slide 4** (points): Yours, and local

> And every study is saved separately, so you can move between projects at any time.

## 14-close (05:10 to 05:19)

**Slide 1** (hero): Research moves faster than ever. Episteme keeps the documentation with it.

> Research moves faster than ever. Episteme makes sure the documentation keeps up.

**Slide 2** (hero): Episteme

> Episteme. Keep the why.
