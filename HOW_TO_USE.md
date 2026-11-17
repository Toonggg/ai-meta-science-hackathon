# How to use Episteme

This guide walks you through Episteme screen by screen: first a demo, then your own study, then automatic capture of an AI agent. For how it works inside, see the [technical README](README.md).

## Contents

1. [Start Episteme](#1-start-episteme)
2. [A five-minute tour with a demo](#2-a-five-minute-tour-with-a-demo)
3. [Record your own study by hand](#3-record-your-own-study-by-hand)
4. [Capture an AI agent automatically](#4-capture-an-ai-agent-automatically)
5. [Ask the log](#5-ask-the-log)
6. [Export the record](#6-export-the-record)
7. [Vet a research question (step 1)](#7-vet-a-research-question-step-1)
8. [Check a paper's claims (step 3)](#8-check-a-papers-claims-step-3)
9. [Settings: model, search and theme](#9-settings-model-search-and-theme)
10. [Troubleshooting](#10-troubleshooting)

## 1. Start Episteme

You need macOS or Linux with Python 3.9 or newer. Check with `python3 --version`. Nothing else needs installing.

```bash
git clone https://github.com/Toonggg/ai-meta-science-hackathon.git
cd ai-meta-science-hackathon
./run
```

Your browser opens Episteme at `http://127.0.0.1:8765`. Press **Ctrl+C** in the terminal to stop it. Running `./run` again while it is already running just opens the page.

| Command | What it does |
|---|---|
| `./run` | start and open the browser |
| `./run --offline` | no network at all: no model, no literature search |
| `./run --reset` | delete all saved studies and start empty (asks first) |
| `./run --no-open --port 9000` | don't open a browser; use another port |

Everything you record stays on your computer, in the `.episteme/` folder.

## 2. A five-minute tour with a demo

Episteme opens on a **start screen**: your saved studies, a new study notebook, or a demo. Every study is saved on your machine, so you can switch between them at any time. To get back to the start screen from inside a study, click **Studies** at the top right (it shows the name of the open study) or the **◈ Episteme** logo.

Both demos are simulated studies, made to show the tool. Load **Hospital readmission**.

**Read the timeline.** The **Record work** tab shows the study as numbered steps, oldest first:

| Step | What you see | What it means |
|---|---|---|
| 1 | **Plan** with an expectation, "AUROC >= 0.75" | the researcher's instruction to the agent, with the result they expected |
| 2 | **Run**, "auroc 0.54" | the agent ran the TF-IDF baseline and printed a result |
| 3 | **Surprise**, "Expectation contradicted" | Episteme noticed that 0.54 misses the 0.75 the plan expected |
| 4 | **Pivot**, "Possible change of approach" | Episteme spotted that the next instruction changes direction |
| 5 | **Plan**, switch to PubMedBERT embeddings | the researcher's new instruction |
| 6 | **Run**, "auroc 0.81" | the new approach |
| 7 | **Artifact**, a commit | the code change, from git |
| 8 | **Note**, "only one seed and one hospital" | a caveat the researcher typed |

Click any card to expand it: the reasoning, the exact command, the result, the linked steps, and **Raw evidence** (what the capture hooks recorded behind that step).

**Read the badges.** Each card says who stated it:

- **researcher**: the person's own words.
- **agent**: the AI agent's own words, quoted exactly.
- **agent ✓**: an agent's reason that the researcher confirmed.
- **inferred**: Episteme's own reconstruction. Trust it less.
- **pending**: flagged, but nobody has given the reason yet.

**Answer the brief's question.** Step 4 is the change of approach. What happens next depends on whether a model is connected (see [Settings](#9-settings-model-search-and-theme)):

- **With a model:** within a few seconds, step 4 is classified and its reason is quoted word for word from the researcher's instruction. A card above the timeline asks you to **Confirm**, **Edit** or **Skip** it if the reason came from the agent.
- **Without a model:** step 4 stays **pending**. The card "Why did the approach change at step 4?" lets you type the reason in your own words (**Save reason**) or **Skip**.

Then, in **Reviewer: ask the log** on the right, click **Why did they change approach at step 4?**. The answer cites the steps it rests on as small chips like `E3`. Click one to jump to that step.

**Switch views.** Above the timeline:

- **All:** every step.
- **Decisions:** plans, pivots, surprises, notes and failed runs only.
- **Raw capture:** everything the hooks recorded, grouped into episodes.

## 3. Record your own study by hand

On the start screen, type a project name under **New study notebook** and click **Start notebook**. Your other studies are kept; open them again from **Your studies** on the start screen. A study you no longer need can be deleted there (export it first to keep a copy, see [section 6](#6-export-the-record)).

Use the bar at the top of **Record work**. Pick a type, write one line, and click **Add**:

| Type | Use it for | Extra fields |
|---|---|---|
| Thought | an idea, a doubt, a caveat | details |
| Plan / hypothesis | what you are about to try | **I expect…**, for example `AUROC >= 0.75` |
| Run / result | what you ran and what came out | result, for example `AUROC 0.62 (5-fold CV)`; ok or failed |
| Surprise | something that didn't match | details |
| Artifact / commit | a file, figure or commit worth pointing to | details |

Press **⌘⇧E** (Ctrl+Shift+E on Linux) from anywhere on the page to jump to the bar and drop a thought.

**Expectations are checked for you.** If a plan says `AUROC >= 0.75` and a later run reports `AUROC 0.62`, Episteme adds a **Surprise** automatically. If you then add a new plan, it asks **Why the change of direction?** in the moment, while you still remember. Write one line, or skip it and the step is logged as inferred.

Write expectations as a metric, a comparison and a number (`F1 > 0.8`, `rmse <= 2.5`) so they can be checked.

To delete a step, hover over its card and click **×** at the right.

## 4. Capture an AI agent automatically

If you work with Claude Code, Episteme can record the session without you typing anything.

**1. Switch capture on, once per project.** With Episteme running:

```bash
python3 capture/install.py /path/to/your/project
```

This adds a Claude Code hook and a git hook to that project. `python3 capture/install.py /path/to/your/project --remove` takes them out again.

**2. Have your scripts print results as `RESULT` lines.** This is how Episteme knows a run produced an outcome:

```
RESULT auroc=0.81 seed=42 split=cluster
```

Numbers become metrics. Setup values such as `seed`, `n`, `epochs` and `lr` are kept as context and never compared.

To have results checked, state an expectation in your instruction after a word such as *expect*, *target*, *goal*, *aim for* or *at least*: "Try a family split. I expect AUROC >= 0.8." A comparison without one of these words ("use lr<0.01") is treated as a setting, not an expectation.

**3. Work as usual.** Each instruction you give the agent becomes a **Plan**, each run with a `RESULT` becomes a **Run**, and each commit becomes an **Artifact**. When an instruction changes direction, a **Pivot** appears:

- If your instruction gives the reason ("switch to a family split, the random split leaks similar proteins"), it is recorded as the **researcher**'s, word for word.
- If the agent gave the reason, a card asks you to **Confirm**, **Edit** or **Skip** it. Confirming takes one click and marks it **agent ✓**.

The line next to the view buttons shows how many episodes were captured and whether pivots are waiting for a model. **Raw capture** shows everything recorded.

**What it doesn't record:** file contents, diffs, and decisions made outside the agent, such as in a meeting. Add those as a Thought. Secrets such as API keys and tokens are stripped before anything is stored.

**Other tools** can log steps directly. Open **Export and capture** in the sidebar for a ready-made `curl` example.

**Good to know:**

- Run one agent session per project at a time; two parallel sessions get mixed up.
- If Episteme isn't running, captured events wait and are sent when it starts again.
- Jobs started in the background (cluster jobs, `nohup`) report outside the agent, so log their results by hand.

## 5. Ask the log

**Reviewer: ask the log** answers questions about the study from the diary only. Type a question or click an example:

- "Why did they change approach at step 4?"
- "Which expectations were contradicted?"
- "What was tried and abandoned?"

Every answer cites its steps (`E3`, `E7`); click a chip to see the step. The answer says whose statement it rests on (researcher, agent or inferred) and says so when the log has no answer.

The line under each answer shows how it was made: by the connected model, or by **Local rules (no model call)**. Without a model, questions about a specific step ("step 4", "E7") work best.

## 6. Export the record

Open **Export and capture** in the sidebar:

| Export | For |
|---|---|
| Decision appendix (.md) | pasting into a paper, report or supplementary material |
| W3C PROV-JSON | provenance tools that read the W3C PROV standard; keeps who stated, classified and confirmed each step |
| Raw JSON | a full backup of the diary |

The same panel has **All studies…**, which reopens the start screen.

## 7. Vet a research question (Task 1)

Open **1 Vet question** at the top. Paste one research question, or click an example, and press **Stress-test** (or Enter).

Three stages run and show their progress:

1. **Local rules:** instant, nothing leaves your computer.
2. **Literature search:** sends keywords only, never your full question, to free scholarly databases.
3. **AI refinement:** if a model is connected, it runs sharper searches and writes a critique that may cite only papers that were found.

You get:

- **A verdict:** proceed, narrow, revise or stop, with the reason.
- **Ambiguous terms:** for example, the different senses of "engagement", with the papers that use each.
- **Implicit assumptions**, each with a risk level and how to check it.
- **Evidence needed:** marked available, restricted or unobtainable.
- **Already answered?** Existing reviews on the question.
- **A narrowing ladder:** sharper versions of your question.

Each finding is tagged **rule**, **search** or **AI**, so you can see where it came from. Click a paper chip such as `P3` to jump to that paper.

Click **Start diary with this →** next to a sharper question to make it the first step of your diary.

## 8. Check a paper's claims (Task 3)

Open **3 Check claims**. Paste the paper's text (abstract, results and discussion, as plain text) and click **Build claim map**. With the Hospital readmission demo open, **Load demo paper** fills in a paper that overstates the demo's own results; try to spot where before running it.

The map has one row per claim:

| Column | What it shows |
|---|---|
| Claim | the sentence, with strong wording in bold and hedged wording in italics |
| Evidence in paper | the figures, tables or sections it cites; crossed out if the paper doesn't contain them |
| Diary | the diary runs that produced the numbers in the claim; click to jump there |
| Status | supported, weak evidence, overclaimed, or no evidence |
| Why | the reasons, for example "one seed" or "claims generalisation from one hospital" |

Below the table, **Checked** and **Not verified** list exactly what was and wasn't examined. The map reads text only: it doesn't open PDFs or read figures.

## 9. Settings: model, search and theme

Click the status pill at the top right (for example "No model · no search"). It opens a menu with three rows:

- **Literature search:** switch it on or off. The button next to it shows how many search sources are up; click it for live status and a **Check** button per source.
- **AI model:** switch it on or off. The button next to it opens the provider settings.
- **Theme:** five colour themes, including a light one for projectors.

**Connecting a model.** In the provider settings, choose a provider and model and paste a key if one is needed:

| Provider | Notes |
|---|---|
| Anthropic Claude | key from console.anthropic.com |
| OpenAI or compatible | also LM Studio, vLLM, OpenRouter, Berget AI: set the base URL |
| Google Gemini | key from aistudio.google.com |
| Ollama | runs on your computer; no key, nothing leaves the machine |

Keys are saved only on your computer, in `.episteme/config.json`. You can also put them in a `.env` file in the project folder, which `./run` reads at start, for example `ANTHROPIC_API_KEY=…`.

Everything works without a model. You lose the automatic pivot classification and the model's answers and critiques. Rules, search, the expectation checks and the local answers still work.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| "Episteme needs Python 3.9 or newer" | Your `python3` is older (common with old Anaconda installs). Run `which -a python3` to find a newer one and put it first on your PATH, or install Python from python.org. |
| The page doesn't open | Open `http://127.0.0.1:8765` yourself. If that port is taken, `./run` uses the next free one and prints the address. |
| Nothing appears from Claude Code | Is Episteme running? Did you run `capture/install.py` on that project? Captured events wait and arrive when Episteme starts. |
| Runs don't show up | The script must print a `RESULT key=value` line. Runs without one (unless they fail) are kept in **Raw capture** but don't become steps. |
| No Surprise when a result misses | The plan needs an expectation: in the **I expect…** field, or in an agent instruction after a word like *expect* or *target*. |
| Step 4 stays "pending" | No model is connected, or the model call failed. Connect one in settings, or write the reason yourself on the card. |
| The answer says "Local rules (no model call)" | No model is connected, or **AI model** is switched off in the menu. |
| Search finds nothing | Check the sources' status in the menu, or whether you started with `--offline`. |
| I want to start over | Click the ◈ logo, then **Start notebook** or load a demo. Export first to keep the current diary. |
