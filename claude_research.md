# AI4MetaScience Hackathon: Research Notes

*Compiled 2026-10-29. Sources: `AI4MetaScience_Hackathon_Tasks.pdf` (primary), [ai4metascience.org](https://ai4metascience.org/index.html), [ai4metascience-hackathon.stockholm.ai](https://ai4metascience-hackathon.stockholm.ai/), plus web research on the competitive landscape. Links are inline. Vendor claims and funding numbers come from press or aggregator sites and have not been checked further. Items marked (unverified) could not be confirmed from a primary source.*

---

## 0. Event context

| | |
|---|---|
| **Hackathon** | 10–17 Nov 2026, Stockholm (kick-off 10 Nov, 17:30 CET, RISE KTH). Submission deadline **17 Nov 18:00 CET**; winner announced 24 Nov. Organised by Stockholm AI, the AIM NeurIPS workshop, and Sweden AI Factory (sponsor). |
| **Prize** | All-expenses-paid trip to NeurIPS 2026 in Paris, a poster, and an **oral presentation** at the workshop. |
| **Workshop** | *AI for Meta-Science: Scaling and Organizing Science in the Age of AI Scientists*, NeurIPS 2026, Paris, **13 Dec 2026**. Organisers: Prabhant Singh (Microsoft), Khuong T G Hieu (Paris-Saclay), Hilde Weerts and Joaquin Vanschoren (TU/e), Lele Cao (Microsoft Gaming / King). Speakers include Thomas Dietterich, Isabelle Guyon, Vlasta Sikimić, Joydeep Biswas and Jack Stilgoe. |
| **Workshop thesis** | Science faces *"a new bottleneck: evaluation, verification, and governance."* Themes: scaling evaluation alongside production (AI reviewers, verification tools); quality control and integrity ("AI slop"); and credit, incentives and what counts as a publication. |
| **Not published** | Judging criteria, team size, tech constraints, submission format. **Action: email info@stockholm.ai.** |

**What this means for us:** The winning project gets presented to a meta-science and ML audience. The pitch will land best if it speaks to *verification and accountability of AI-accelerated science*, not just "a productivity tool."

---

## 1. Task summaries (from the PDF)

1. **"Is this question worth asking?"** The user pastes in one research question. The tool should flag ambiguous or inconsistently used terms, surface implicit assumptions, say what evidence or data would be needed and whether it can be obtained, and give a verdict of **proceed / narrow / revise / stop**. *Success criterion:* specific critique ("'engagement' is used in three senses in the literature"), not generic advice.
2. **Provenance-preserving lab notebook for AI-assisted execution.** A wrapper around an AI-assisted task that automatically captures plans and hypotheses with their reasoning, what was run (code, parameters, data version), failures or surprises and how the plan changed, and a timeline someone can walk back through. *Success criterion:* a reviewer who wasn't there can answer **"why did they change approach at step 4?"**
3. **Claim-to-evidence linker for one paper.** For each major claim, link the exact figure, table, paragraph or code path. Flag claims with no evidence, claims whose evidence is weaker than the stated confidence, and what was checked versus left unverified. *Output:* a **claim map**, not a single score.

---

## 2. Competitive landscape

### Task 1: Question stress-testing

**Bottom line: nobody audits the question itself.** Existing tools assume the question is well-posed. They either generate ideas, check whether the work has been done before, or summarise evidence.

| Company / tool | What they do | Gap vs. task |
|---|---|---|
| [Edison Scientific / FutureHouse](https://futurehouse.org/tools) (Edison: $70M seed) | Kosmos "AI Scientist"; **Owl** (formerly HasAnyone) answers "has anyone done X?" | Novelty check only. No term-sense analysis, assumption audit or verdict |
| [Google Co-Scientist / Hypothesis Generation](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/) | Multi-agent system; a "Reflection" agent critiques hypotheses | Critiques the hypotheses it generates itself; no evidence it accepts a user's question as input. No feasibility or term checks |
| [Ai2 Asta](https://allenai.org/asta) | "Frame research questions, trace ideas to evidence" | Closest in spirit, but no ambiguity or assumption audit and no verdict |
| [Elicit](https://elicit.com/blog/introducing-research-agent-workflows), [Consensus](https://www.mobihealthnews.com/news/consensus-raises-115m-ai-research-engine-scientific-papers), [Scite](https://researchsolutions.investorroom.com/2023-11-27-Research-Solutions-Announces-Acquisition-of-scite) | Evidence synthesis; yes/no agreement meter; supporting/contrasting citations | Assume a well-formed question. Useful as **backends** for checking assumptions |
| SciSpace, Iris.ai, Paperguide, Undermind | Gap-finding and deep literature search | Retrieval and gap-finding; they don't stress-test how the question is framed |
| Sakana AI Scientist, Autoscience, Intology, Lila, Periodic Labs | Autonomous AI-scientist and lab companies | Generate their own ideas; they don't vet a human's |
| [XLSCOUT](https://xlscout.ai/reducing-rd-risk-with-ai-the-power-of-early-novelty-detection/) | Novelty checks for patents and R&D | Prior art only |

**Academic prior work to cite or build on:**
- [Wulff & Mata, *Nat. Hum. Behav.* 2025](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12106064/): LLM embeddings that detect **jingle-jangle** fallacies (one label for different constructs, or different labels for one construct). This is the closest technical precedent for the "engagement has three senses" criterion, but it only covers psychology scales.
- [Si, Yang & Hashimoto](https://arxiv.org/abs/2409.04109): LLM ideas were judged *more novel* than human ideas. A [follow-up](https://arxiv.org/abs/2506.20803) found they *scored worse once actually carried out*. That gap is a strong argument for vetting questions before committing to them.
- Others: [ResearchAgent](https://aclanthology.org/2025.naacl-long.342), [Scideator](https://arxiv.org/abs/2409.14634) novelty checker, [ContraCrow](https://arxiv.org/abs/2409.13740) (factual contradictions), [SCICO-RADAR](https://aclanthology.org/2026.tacl-1.36.pdf) (concept alignment across papers), [definition sensitivity, NeurIPS 2026](https://neurips.cc/virtual/2026/178267).

**Stealth or early-stage:**
- Inherent ($50M seed, May 2026, "AI-native science")
- Unreasonable Labs ($13.5M)
- "Scientificai" (listed as stealth)
- An ex-Ai2 startup with Oren Etzioni (unverified)

None of these is publicly positioned as a question critic.

### Task 2: Provenance notebook / research diary

**Bottom line:** Many tools record **what** ran; none records **why the plan changed**, and nothing does this across the browser tools researchers actually use. Every incumbent covers one slice:

| Slice | Players | What's missing |
|---|---|---|
| Electronic lab notebooks (ELNs) | [Benchling AI](https://www.benchling.com/ai), [Sapio ELaiN](https://www.businesswire.com/news/home/20250916394364/en), LabArchives, SciNote, eLabFTW, RSpace | Reasoning is typed in by hand; wet-lab and enterprise focus |
| ML experiment tracking | W&B (Models and [Weave](https://docs.wandb.ai/weave/guides/integrations/agents/claude-code-harness)), MLflow, DVC, ClearML, Comet/Opik, Aim. [Neptune was acquired by OpenAI](https://openai.com/index/openai-to-acquire-neptune/) and is shutting down for external users | The "what" is solved: parameters, metrics, lineage. No hypotheses or pivots |
| LLM/agent tracing | LangSmith, [Langfuse (acquired by ClickHouse)](https://langfuse.com/blog/announcing-acquisition), Arize Phoenix, Braintrust, AgentOps, Logfire | Built for production debugging; span trees, not a research narrative |
| Coding-agent session capture | **[Entire](https://docs.entire.io/core-concepts)** (ex-GitHub CEO Thomas Dohmke, **$60M seed**, Feb 2026; agent sessions linked to commits); [SpecStory](https://docs.specstory.com/specstory/introduction); [git-ai](https://usegitai.com) / [Agent Trace spec](https://agent-trace.dev/) | Repo and IDE only. Raw transcripts or line attribution, with no hypothesis or pivot model. **Entire is the nearest well-funded neighbour** |
| Provenance and reproducibility | W3C PROV, [PROV-AGENT](https://arxiv.org/abs/2508.02866) (ORNL), noWorkflow, ReproZip, RO-Crate, Code Ocean, Renku | They reproduce the final state; the path and its reasons are lost. No reviewer-facing UI |
| AI scientists | [Edison Kosmos](https://edisonscientific.com/articles/announcing-kosmos), Perceptic ($12M, "every claim traceable") | Traceability only inside their own closed agent |
| Browser knowledge capture | Recall, Heptabase, Glasp, Readwise, Hypothesis, Zotero Connector, Obsidian Web Clipper, Liner, Sider, Memex | Organised by topic, not time. Record what you *read*, not *decisions*; no link to chats, Colab or GitHub |
| Memory and screen capture | [Mem0 OpenMemory](https://mem0.ai/blog/introducing-the-openmemory-chrome-extension), Screenpipe, Microsoft Recall, Limitless (reportedly bought by Meta), **[Dia browser (acquired by Atlassian)](https://en.wikipedia.org/wiki/Dia_(web_browser))** | Raw pixels, or memory that feeds context back to an AI. No project or decision model. Dia/Atlassian could move into this space |
| Chat timeline extensions | e.g. [AI-chat-timeline](https://github.com/RachelWanggg/AI-chat-timeline-extension), [research-extension](https://github.com/Fiialkovskyi/research-extension) (hobby) | One chat or one session; no semantics |

**Academic signals that the "why" problem is live:**
- [AER (Mar 2026)](https://arxiv.org/abs/2603.21692) stores intent, observations, inferences and *versioned plans* for each step. It argues reasoning *"cannot be rebuilt from saved computational state."*
- [LEDGER](https://arxiv.org/pdf/2608.18398) builds claim-to-evidence trace graphs.
- [AuditWeave](https://arxiv.org/pdf/2607.09682) is an evidence layer that auditors can navigate.
- [Value-level ELN provenance with LLM agents](https://arxiv.org/abs/2610.27859v1).

**Browser-diary white space:** We found **nothing** that watches activity across tabs (arXiv/PDFs, ChatGPT and Claude chats, Colab/Jupyter, GitHub, Overleaf) and turns it into a **project-scoped decision timeline**.

Two angles the incumbents lack:
- **Local-first privacy.** Malwarebytes [documented an extension that harvested AI chats](https://www.malwarebytes.com/blog/news/2025/12/chrome-extension-slurps-up-ai-chats-after-users-installed-it-for-privacy), so trust is a real selling point.
- **Interop with existing formats:** Entire, SpecStory, Agent Trace and W3C PROV.

### Task 3: Claim-to-evidence linker

**Bottom line:** No public product outputs an **intra-paper** claim → anchor (figure, table, paragraph, code line) → confidence/caveat → checked or unverified map. Existing tools do one of three things:
- check a paper against **other papers**
- look for **fraud and integrity** signals
- write **review prose**

| Company / project | What they do | Gap vs. task |
|---|---|---|
| **[q.e.d Science](https://connect.biorxiv.org/news/2025/11/04/qed_review_tool)** (pilots with bioRxiv and EMBO) | Breaks a manuscript into claims and scores each | **Closest.** Checks claims against the *literature*; a competitor says it doesn't analyse figures (unconfirmed by q.e.d) |
| [Reviewer3](https://www.the-scientist.com/reviewer3-an-ai-based-system-to-streamline-peer-review-74934), [Hum Alchemist Review](https://hum.works/review) | Multi-agent review; extracts claims, checks methods and statistics | Output is prose or editor triage, not an inspectable map |
| [Google PAT / Deep Review](https://arxiv.org/abs/2606.28277) (used at ICML/NeurIPS 2026) | Finds errors in math and proofs | Reports errors, doesn't link claims to evidence |
| [Stanford Agentic Reviewer](https://paperreview.ai/tech-overview), [Lambda ReviewGrounder](https://www.plushcap.com/content/lambda/blog/lambda-reviewgrounder-grounding-ai-assisted-peer-review-in-evidence) | Literature-grounded reviews | Grounds the *review*, not the paper's own claims |
| Black Spatula, YesNoError | LLM error hunting | No claim map; about 10% false positives |
| Proofig/Octym, ImageTwin, Clear Skies, Signals, Springer Nature tools | Image integrity and paper-mill detection | Misconduct, not overclaiming |
| SciScore, Ripeta, DataSeer, Paperpal Preflight | Rigor and reporting checklists | Check that statements are *present*, not that claims are *supported* |
| statcheck, GRIM, SPRITE | Recompute reported statistics | Narrow, but a **useful sub-module** |
| Scite, Elicit, Consensus, SciSpace | Synthesis across papers | Not an audit of a single paper |
| ORKG, nanopublications | Structured claim and provenance formats | Hand-curated, but a good **export format** |

**Closest research, all prototypes:**
- [RIGOURATE](https://arxiv.org/abs/2601.04350): retrieves evidence for each claim from within the paper and scores overstatement (10K+ claim–evidence sets from ICLR/NeurIPS). This is very close to the "weaker than stated" requirement.
- [FactReview](https://arxiv.org/abs/2604.04074): *runs the paper's repo* and labels each claim Supported, Partial, Conflict or Inconclusive.
- [ReAgent](https://arxiv.org/pdf/2609.22111): audits a paper against its repo.
- Benchmarks: [SciClaimEval](https://arxiv.org/html/2602.07621v1) (figure verification still well below human level), SciTab, ToolSciVer, SciFact.
- Spin detection in biomedicine: [DeSpin](https://arxiv.org/pdf/2502.07963).

**Context:**
- AAAI-26 ran AI review on all 22,977 main-track papers.
- NeurIPS 2026 is running an [AI-reviewing randomized trial](https://neurips.cc/Conferences/2026/ai-reviewing-experiment).
- DeepMind and Springer Nature are building a peer-review assistant (reported Oct 2026).
- This is the **most crowded and fastest-moving** of the three spaces.

---

## 3. Ideas (1–2 sentences each)

### Task 1: Question stress-test
1. **Term-sense mapper.** For each key term, pull about 50 papers (OpenAlex / Semantic Scholar), cluster how each one *operationalises* the term, and report e.g. "'engagement' = time-on-app (12 papers), self-report scale (9), behavioural clicks (7)" with citations. This generalises Wulff & Mata beyond psychology.
2. **Assumption excavator.** Break the question into its presuppositions (e.g., "social media is one construct," "wellbeing is measurable cross-sectionally") and check each against supporting and contrasting literature.
3. **Data-feasibility probe.** Map the variables the question needs onto real datasets (ICPSR, UK Biobank, OpenML, HF Datasets, Zenodo), and flag those that would require unobtainable data, such as platform-internal logs or counterfactuals.
4. **"Already answered?" check.** Look for existing systematic reviews or meta-analyses on the question. If one exists, recommend *stop* or *narrow to the open sub-question* and cite it.
5. **Narrowing ladder.** Generate 3 progressively sharper rewrites (using the PICO/FINER frameworks) and re-score each one, so the "narrow/revise" verdict comes with a concrete better question.
6. **Adversarial advisor panel.** Simulated methodologist, domain skeptic and funder argue it out, then output a verdict with dissent recorded. This is a fun demo but at risk of producing the "generic advice" the success criterion warns against.
7. **Browser sidebar critic.** Highlight a question in Overleaf or Google Docs and get the critique in a side panel. This fits the browser-first instinct and could share infrastructure with the Task 2 extension.

### Task 2: Provenance notebook (★ = browser-diary angle)
1. ★ **Research Diary extension (core).** A Chrome extension where you tag tabs to a project. It captures events from arXiv/PDFs, ChatGPT/Claude chats, Colab/Jupyter, GitHub and Overleaf, and an LLM groups them into **Plan → Run → Surprise → Pivot** entries, each linked to its evidence.
2. ★ **Pivot micro-prompts.** When the extension detects a probable change of direction (new approach in a chat, a reverted commit, an abandoned notebook), it asks a one-line "why?" in the moment. This captures real rationale rather than reconstructing it later, which answers the AER critique.
3. ★ **Hypothesis ledger with pre-stated expectations.** Before a run, the researcher (or the agent) records "I expect X." The result is compared automatically, and contradicted expectations become first-class timeline nodes. This is close to a lightweight pre-registration.
4. **Agent-side hook / MCP server.** A Claude Code hook or MCP server streams the agent's plan, tool calls, code and data hashes into the *same* diary, so terminal agents and browser activity end up in one timeline.
5. ★ **"Ask the log" reviewer view.** A reviewer asks "why did they change approach at step 4?" and gets an answer that cites only diary events, with clickable evidence. This is the success criterion shipped as a feature.
6. **Decision appendix export.** Export the timeline as W3C PROV / RO-Crate plus a readable PDF "decision appendix" that can be attached to a paper or preprint.
7. ★ **Dead-end archive.** Automatically summarise abandoned branches into a shareable negative-results log, so failed attempts become reusable knowledge instead of disappearing.
8. ★ **Local-first and redacted.** All data stays in IndexedDB, secrets and PII are redacted before any LLM call, and the user chooses what to share. This builds trust in a space where chat-harvesting extensions have been caught.
9. ★ **Advisor digest.** Weekly auto-generated "what I tried, what failed, what changed and why" summary for supervisors or collaborators.

### Task 3: Claim-to-evidence linker
1. **Clickable claim map.** Upload a PDF and get a side panel of claims. Clicking a claim highlights the exact figure, table or paragraph region in PDF.js, and each link is labelled strong, weak or missing.
2. **Hedging-vs-evidence calibrator.** Score the certainty of the wording ("we show" vs "suggests") against the strength of the evidence (n, seeds, error bars, statistical tests) and flag mismatches, e.g. "'we demonstrate' backed by 1 seed, no CIs."
3. **Abstract-to-results consistency (spin check).** Check that every claim in the abstract and introduction has a counterpart in the results, and flag claims that only appear in the framing.
4. **Code-path linker.** Given the repo, trace each number in a results table to the script or config that produces it, and flag numbers with no generating code.
5. **Stats recomputation module.** Run statcheck/GRIM-style consistency checks on the extracted numbers and attach the results to the relevant claims.
6. **arXiv overlay extension.** Show the claim map directly on arxiv.org / alphaxiv pages as you read (browser-native again).
7. **Checked-vs-unverified ledger with export.** An explicit list of what the tool verified, what it couldn't (e.g., supplementary material not provided), and why, exportable as nanopublications.

### Cross-task idea (worth considering)
**One lifecycle, one diary.** Task 1 vets the question at project start, Task 2's diary logs the work, and at write-up time the diary *becomes the evidence base* for Task 3. Paper claims link to the diary entries and runs that produced them. This is too big for one week, but it makes a strong *vision slide*. The Task 2 diary is the natural centre.

---

## 4. Initial take (for team discussion)

**Task 2 + browser diary looks like the strongest choice:**
- **Clearest white space.** It is the only option where we found no product covering the browser and cross-tool slice. Task 3 is crowded (q.e.d, Reviewer3, Google, Springer Nature/DeepMind), and Task 1 has strong adjacent players (Ai2 Asta, FutureHouse Owl).
- **Fits the workshop thesis.** It targets accountability and governance of AI-assisted work, the "verification bottleneck."
- **Demo-able against the success criterion.** Record a staged research session with a deliberate pivot, then have a judge ask "why step 4?" live.

**Suggested MVP scope for 7 days:**
- A Chrome MV3 extension with a side panel.
- 3 capture sources: Claude/ChatGPT chat turns, GitHub commits, Colab/Jupyter cell runs.
- The Plan/Run/Surprise/Pivot segmentation.
- Pivot micro-prompts.
- The reviewer timeline with grounded "ask the log."
- JSON/PROV export.

**Risks to discuss:**
1. **Fragile capture.** Reading content from chat apps' pages is brittle; prefer stable sources such as the GitHub API, Jupyter kernel messages, and the Claude Code hook.
2. **Rationale reconstructed by an LLM may be wrong.** Mitigate with in-the-moment micro-prompts, and by labelling each entry *inferred* or *stated*.
3. **Privacy.** Default to local-first storage.
4. **Incumbents.** Entire, W&B or Atlassian/Dia could move into this space. Position the tool as *science-specific* (hypotheses, expectations, data versions), not generic agent logging.

**Open questions:**
- Judging criteria and team size (email the organisers).
- Do we target a specific field for the demo (ML experiments are easiest to stage)?
- Is a browser extension acceptable as a submission format?
