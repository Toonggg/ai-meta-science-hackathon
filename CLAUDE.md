# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Episteme: a local browser tool built for the AI4MetaScience hackathon (brief: `AI4MetaScience_Hackathon_Tasks.pdf`). It covers all three hackathon tasks as one lifecycle: **Task 1** vet a research question, **Task 2** provenance diary (the core), **Task 3** claim-to-evidence map. The success criterion it is built around: a reviewer who wasn't there can answer *"why did they change approach at step 4?"*.

**Hard constraint: Python 3.9+ standard library only.** No pip dependencies, no build step, no JS framework. All HTTP (LLM providers, search APIs) goes through `urllib`. `tools/replay.py` must also stay Python 3.8 compatible. Keep it that way.

## Commands

```bash
./run                    # start server + open browser (reuses a running instance); Ctrl+C stops
./run --offline          # no network: no model, no search
./run --reset            # start from an empty diary (wipes diary, raw log, stitch state)
./run --no-open --port 9000

python3 -m unittest discover -s tests                       # all tests
python3 -m unittest discover -s tests -p test_stitcher.py   # one file
python3 -m unittest discover -s tests -k StitcherTest       # by name pattern

python3 tools/build_themes.py   # regenerate episteme/static/themes.css (never edit that file by hand)
python3 tools/replay.py demo/alphafold.jsonl --clear --project "AlphaFold 2" --instant  # replay a demo session live into a running server
python3 capture/install.py /path/to/project   # install Claude Code + git capture hooks there (--remove undoes)
```

`python3 -m unittest tests.test_x` does **not** work: the test modules put `episteme/`, `capture/` and `tools/` on `sys.path` themselves and import modules by bare name (`import server`, `from store import Diary`). Use `discover -s tests`. The `episteme/*.py` modules likewise import each other by bare name, not as a package.

`./run` sources `.env` (gitignored) for API keys. State lives in `.episteme/` (gitignored): `diary.json`, `raw.jsonl`, `stitch.json`, `config.json`, `token`, `url`, `server.log`, `spool.jsonl`.

## Architecture

`episteme/server.py` is a stdlib `ThreadingHTTPServer` bound to 127.0.0.1 serving `episteme/static/` (vanilla HTML/CSS/JS) and a JSON API under `/api/*`.

### Task 2 capture pipeline (the part that spans most files)

```
capture/claude_hook.py, capture/git_post_commit
   └─ capture/send.py ──POST /api/raw──▶ RawLog (raw.jsonl, append-only, ids R1, R2…)
                                           └─ episodes.segment()  pure function → episodes
                                                └─ stitcher.py (background thread) → diary events (E1, E2…) in Diary (diary.json)
                                                     └─ diary.after_add(): hypothesis ledger, surprises, pivot prompts
```

- **Raw vs diary**: `raw.jsonl` holds everything captured; `diary.json` holds only decisions (plan/run/surprise/pivot/note/artifact/question). Diary events point back at evidence via `raw_ids`. Event and raw shapes are documented in the docstrings of `store.py` and `episodes.py`.
- **episodes.py**: `segment()` must stay a pure function of the raw list with bounded look-ahead, so earlier episode ids never change as new raw events arrive. Only *final* episodes get stitched. Results are detected from `RESULT key=value` lines in command output.
- **stitcher.py**: "rules propose, the model confirms." Rules create plan/run/surprise/artifact events instantly. Episodes flagged as possible changes of approach get a pending pivot, then the LLM classifies it *outside* the stitcher lock. A "stated" reason must be a verbatim quote found in the source text; otherwise it's downgraded to "inferred". Model paraphrase goes in `model_summary`, never in `detail`.
- **Attribution is server-decided.** `server.py` strips `ATTRIBUTION_FIELDS` (actor, confirmed_by, quote, raw_ids…) from posted events. Routes in `NEEDS_TOKEN` (confirm, pivot, delete, demo, clear, settings, sources) require the per-start random token embedded in the page (also written to `.episteme/token`). `tests/test_security.py` covers this, plus host/origin checks.
- **redact.py** strips secrets from captured text before it is stored or sent.

### Task 1 and Task 3

- `pipeline.py` runs Task 1 as a staged background job (`/api/question/start`, poll `/api/jobs/<id>`): local rules (`question.py`) → literature search (`search.py`) → AI refinement. The AI may cite only retrieved papers; invented ids are dropped. Findings are tagged `rule` / `search` / `AI`.
- `search.py`: many free sources queried in parallel and merged, plus a web-engine priority chain; per-source health, cooldowns, politeness limits, a background poller, and an hour-long cache. A new source is one function there.
- `claims.py`: Task 3 claim map over plain text, linked back to diary runs.
- `export.py`: JSON, W3C PROV-JSON, Markdown decision appendix.

### Start screen and demos

- On each server start the UI shows a start screen (`#start` in `index.html`, `openStart()` in `app.js`): new study notebook, load a demo, or continue the open study. The ◈ logo and the sidebar "New study or demo…" reopen it. There is one diary at a time; starting or loading replaces it.
- Demos live in `demo/`, listed in `demo/demos.json` (id, title, project, summary, session file, optional paper). Every demo is a raw capture session (`.jsonl`) and loads through `server.load_demo()` → `RawLog` → episodes → stitcher, the same path as live capture, so demos and real sessions can't drift apart. The stitcher runs with `ask_model=False` during the load; the background thread classifies pivots afterwards if a model is set.
- `{"kind": "note", "about": "last_run", ...}` lines are researcher notes (not raw capture); `demos.py` adds them to the diary once the raw lines before them are stitched. `tools/replay.py` understands them too, and `tests/test_demos.py` checks that replay and load give the same diary.
- A new demo is a `.jsonl` file plus an entry in `demos.json`. API: `GET /api/demos`, `POST /api/demo {"id"}` (token), `GET /api/demo-paper` (paper of the loaded demo, or empty).

### LLM layer

`llm.py` exposes only `text()` and `structured()` to the rest of the code. Providers: anthropic, openai (and any OpenAI-compatible base URL, e.g. Berget AI via `.env`), gemini, ollama, none. Config order: UI-saved `.episteme/config.json` → `EPISTEME_PROVIDER/MODEL/BASE_URL/API_KEY` env → auto-detect from provider key env vars → running Ollama → offline. Everything must still work with no model. A new provider is one `_call_<name>()` function plus entries in `ADAPTERS`/`DEFAULTS`.

## Repo notes

- `claude_research.md`, `gemini_research.md`, `design.md` (UI improvement ideas), `bugs.md` (front-end bug log with resolutions) are planning docs, not code.
- `docs/` has the narrative behind the AlphaFold demo; `demo/README.md` is the presenter/headless-agent walkthrough.
