# Episteme: MVP

A browser prototype that combines `claude_research.md` and `gemini_research.md` into one tool for the AI4MetaScience hackathon.

```bash
./run
```

That's it. The command opens the app in your browser and stops when you press Ctrl+C. It needs only Python 3.9+; there are no installs, no build step and no account. Data stays in `.episteme/` (gitignored).

## What it shows

Both research docs recommend **Task 2 (provenance diary)** as the core, and `claude_research.md` suggests connecting all three tasks ("one lifecycle, one diary"). The MVP follows that structure:

| Step | Task | What you can try | Ideas used from the research |
|---|---|---|---|
| **1. Vet the question** | Task 1 | Paste a question. It runs through three visible stages (**local rules → literature search → AI refinement**) and gives ambiguous terms with how papers actually measure them, implicit assumptions, existing systematic reviews, candidate datasets, a **proceed / narrow / revise / stop** verdict, and a narrowing ladder. Every finding is tagged `rule`, `search` or `AI`. "Start diary with this" sends the result to step 2. | Term-sense mapper, assumption excavator, data-feasibility probe, narrowing ladder (Claude); Epistemic Interrogator, DataFeasibility Radar (Gemini) |
| **2. Record the work** | Task 2 | Pick a demo on the start screen (hospital readmission or AlphaFold); both change approach at **step 4**. Ask *"Why did they change approach at step 4?"*. Add a plan with `AUROC >= 0.85`, then a run that misses it, then a new plan. | Plan → Run → Surprise → Pivot timeline (both); **hypothesis ledger** that auto-flags contradicted expectations; **pivot micro-prompts** that ask "why?" in the moment; **stated vs inferred** labels; grounded "ask the log"; ⌘⇧E quick-drop thought (Gemini); PROV-JSON and decision-appendix export; HTTP ingest for agents and notebooks |
| **3. Check the claims** | Task 3 | With the hospital-readmission demo open, load its paper and build the claim map. The paper overstates the diary's own results, and the map catches it. | Clickable claim map, hedging-vs-evidence calibrator, spin check, checked-vs-unverified ledger (Claude); ClaimTrace, CalibreSci (Gemini); claims linked back to the diary runs that produced them |

The success criterion in the brief, *"a reviewer who wasn't there can answer 'why did they change approach at step 4?'"*, is built into the diary as a feature.

## Three tiers: local → search → AI

| Tier | What leaves your machine | What it adds |
|---|---|---|
| **Local rules** | Nothing | Instant first pass from a lexicon of contested constructs and regexes |
| **Literature search** (header toggle *Search*, on by default) | Keywords only, never the full question or your diary | Real papers, systematic reviews, datasets; counts of how papers operationalise each term; "already answered?" check |
| **AI refinement** (header toggle *AI*) | Question + search results, to the model you chose | The model proposes sharper searches, Episteme runs them, then the model writes a critique that may cite **only** retrieved papers (invented ids are dropped) |

### Search sources and fallback

| Group | Sources | Key |
|---|---|---|
| Papers | Semantic Scholar, OpenAlex, Europe PMC, PubMed, Crossref, arXiv | None needed; optional keys raise rate limits |
| Datasets | Zenodo, DataCite, Hugging Face | None |
| Web | Brave, Serper (Google results), Tavily | Your own key (Google's own Custom Search API closes on 1 Jan 2027) |

- **Free sources are queried together** and merged, with duplicates found by several sources combined. If one is down or rate-limited, it drops out and the rest cover for it.
- **Web engines form a priority chain:** the first healthy one is used, and the next one is tried if it fails.
- A failing source is **paused** with a growing cooldown (30 s → 15 min). Each source keeps to its documented politeness limit (for example arXiv gets one call per 3 s), and a 429 response gets one retry.
- A **background poller** re-checks every source every 10 minutes using cheap single-record lookups.
- **Source status panel:** click "7/9 sources up" in the header, or "status" on the search tier card. For each source it shows status, latency, last check (and whether that was auto, manual or a search), the last 24 checks as bars, uptime %, the cooldown countdown, and the time to the next automatic check. **Check** probes one source immediately (ignoring its cooldown), and **Check all now** probes every free source. Web engines are checked only on request, because each check uses a query from your quota. The API equivalents are `GET /api/sources` and `POST /api/sources/check` with `{"id": "arxiv"}`, or `{}` for all sources.
- Settings → Search sources is where you switch sources on or off and add keys.
- Results are cached for an hour. Adding a source means writing one function in `episteme/search.py`.

## AI is optional, and you choose the provider

Without a model, local rules and search still work. Click the model badge in the top-right to connect one:

| Provider | Notes |
|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` or paste a key (default model `claude-opus-5-5`) |
| OpenAI / compatible | `OPENAI_API_KEY`, **or any OpenAI-compatible server**: LM Studio, llama.cpp, vLLM, OpenRouter (set the base URL) |
| Google Gemini | `GEMINI_API_KEY` / `GOOGLE_API_KEY` |
| Local (Ollama) | No key, nothing leaves the machine. Auto-detected if Ollama is running. |

If no provider is configured, `./run` auto-detects one from env vars (Anthropic → OpenAI → Gemini → a running Ollama) and otherwise runs without a model. Keys entered in the UI are saved only to `.episteme/config.json` (mode 600). `./run --offline` switches off all network use (no model, no search). To add a provider, write one function in `episteme/llm.py`.

## Themes and contrast

Use the picker in the top-right to switch between **Tokyo Night** (default), **Dracula**, **Catppuccin Mocha**, **One Dark** and **Catppuccin Latte** (light, for projectors). The palettes use each theme's official colours. `tools/build_themes.py` checks every text/background pair the UI draws against WCAG AA (4.5:1). Where an official colour falls short, the script shifts *lightness only*, keeping hue and saturation, and reports the change. Tokyo Night needs no changes. Dracula's comment grey, for example, goes from 2.4:1 to 4.5:1. To add a theme, add a palette there and run `python3 tools/build_themes.py`, which regenerates `episteme/static/themes.css`.

## Logging from other tools

```bash
curl -s http://127.0.0.1:8765/api/events -H 'content-type: application/json' \
  -d '{"type":"run","source":"agent","title":"train v2","result":"AUROC 0.83"}'
```

Event types: `plan` (with `expectation`), `run` (with `result`, `status`, `code`, `params`, `data`), `surprise`, `pivot`, `note`, `artifact`. A Claude Code hook, a Jupyter cell magic or a browser extension would all send events to this endpoint. That is how the Chrome side-panel version described in both research docs would plug in.

## Start screen and demos

Each time Episteme starts it opens on a start screen: start a **new study notebook** (an empty diary with a project name), **load a demo**, or continue the open study. Click the ◈ logo to come back to it. Starting or loading replaces the open diary, so export it first to keep it.

The demos are simulated studies, not real published work. Each one is a recorded capture session in `demo/`, listed in `demo/demos.json`, and loads through the same path as live capture: raw events go into the raw log, then episodes and the stitcher build the diary. Lines with `"kind": "note"` are researcher notes typed into the diary while the capture runs. A demo can come with a paper for Check claims. To add a demo, add a `.jsonl` session and an entry in `demos.json`. `tools/replay.py demo/<id>.jsonl` plays the same file with real-time pacing.

## Layout

```
run                    launcher (hides startup; reuses a running instance)
episteme/server.py     stdlib HTTP server + JSON API (127.0.0.1 only)
episteme/llm.py        provider-agnostic model layer (Anthropic, OpenAI-compatible, Gemini, Ollama)
episteme/search.py     12 search sources, health/cooldown, poller, fallback, merging
episteme/pipeline.py   Task 1 staged job: local rules -> search -> AI refinement
episteme/question.py   Task 1 rules + prompts
episteme/diary.py      Task 2: ledger, micro-prompts, ask-the-log
episteme/claims.py     Task 3
episteme/demos.py      demo studies (demo/demos.json): one format, loaded like live capture
episteme/export.py     JSON, W3C PROV-JSON, Markdown decision appendix
episteme/static/       UI (vanilla HTML/CSS/JS); themes.css is generated
tools/build_themes.py  theme palettes + WCAG contrast check/adjust
```

## Known limits (deliberate for an MVP)

- The local rules use a small lexicon. Search makes them concrete, but sense counts are keyword matches on abstracts, not a real classification; the AI stage does the real interpretation.
- Search ranking is by simple keyword coverage; relevance falls off after the first 10–15 results. Hugging Face matches dataset names only.
- Capture is manual or HTTP-based. The browser extension that watches Colab, chat and GitHub tabs is the next step.
- The claim map reads plain text and does not parse PDFs or inspect figures. The "Not verified" ledger says so explicitly.
