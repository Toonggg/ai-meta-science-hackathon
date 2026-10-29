# AI for Meta-Science: Research & Ideation Report
**Prepared for the AI4MetaScience Hackathon (Stockholm) & NeurIPS 2026 Workshop (Paris)**  
*Document Target:* `gemini_research.md`  
*Primary References:*  
- [NeurIPS 2026 Workshop: AI for Meta-Science](https://ai4metascience.org/index.html)
- [AI4MetaScience Hackathon Stockholm](https://ai4metascience-hackathon.stockholm.ai/)
- Official Hackathon Tasks Brief: [AI4MetaScience_Hackathon_Tasks.pdf](file:///Users/tony/Desktop/GitHub/ai-meta-science-hackathon/AI4MetaScience_Hackathon_Tasks.pdf)

---

## 1. Executive Summary & Meta-Scientific Foundations

Modern AI has solved the **marginal cost of production** in scientific inquiry. Foundation models and specialized biological architectures (e.g., AlphaFold, ESM, RFdiffusion) make generating code, hypothesizing mechanism candidates, designing synthetic proteins, and drafting manuscripts instantaneous. 

However, as highlighted by the organizers of the [AI for Meta-Science Workshop at NeurIPS 2026](https://ai4metascience.org/index.html) (Prabhant Singh, Hilde Weerts, Joaquin Vanschoren, et al.) and keynote speakers such as Thomas G. Dietterich (Oregon State) and Isabelle Guyon, scaling generation without scaling verification triggers an **epistemic crisis**:
1. **Ideation Noise:** Researchers waste months testing ill-posed or ambiguous questions.
2. **Provenance Decay:** Autonomous and semi-autonomous coding agents iterate at machine speed, discarding the decision trails, negative results, and failure rationales necessary for peer review and reproducibility.
3. **Verification Bottleneck:** Reviewers cannot trace claims in AI-polished text back to primary tabular or visual evidence.

The companion [AI4MetaScience Hackathon](https://ai4metascience-hackathon.stockholm.ai/) (Nov 10–17, 2026, hosted by Stockholm AI and Sweden AI Factory at RISE KTH) directly challenges participants to build working tools that address these failure modes. The winning team earns an all-expenses-paid trip to NeurIPS 2026 in Paris and an oral presentation slot.

This report conducts a thorough two-stage investigation:
1. **Stage 1: Commercial & Competitive Landscape:** Mapping public companies, venture-backed startups, and stealth/frontier projects against each hackathon task to identify market white space.
2. **Stage 2: Idea Catalog:** Presenting concise (1–2 sentence) implementation concepts across all three tasks.
3. **Deep Dive: Browser-Based Provenance Lab Notebook & Diary (Task 2):** Providing an architectural and product blueprint tailored to the user's preferred direction.

---

## 2. Stage 1: Commercial & Competitive Landscape Analysis

The table below summarizes the landscape across public entities, venture-backed startups, and frontier initiatives, followed by task-by-task breakdowns.

| Task Domain | Public Companies | VC-Backed Startups & Private Scaleups | Open-Source & Academic Frontiers | Commercial Gap / Market White Space |
| :--- | :--- | :--- | :--- | :--- |
| **Task 1: Ideation Stress-Test** | **RELX / Elsevier** (Scopus, SciVal)<br>**Clarivate** (Web of Science)<br>**Research Solutions** (NASDAQ: RSSS) | **Elicit** ($9M+)<br>**Consensus** (Seed/Series A)<br>**Causaly** ($60M+)<br>**Undermind**<br>**Iris.ai**<br>**SciSpace** | **Sakana AI** (*The AI Scientist*)<br>**FutureHouse** (*PaperQA2*)<br>**Google DeepMind** (*AI Co-Scientist*) | Tools optimize for *generating* ideas or *finding papers*, acting as "yes-men". None provide adversarial stress-testing, semantic term disambiguation, or data-availability gatekeeping. |
| **Task 2: Provenance Lab Notebook** | **Thermo Fisher Scientific** (LIMS)<br>**Waters Corp** (Andrew+)<br>**Dassault Systèmes** (BIOVIA)<br>*Pre-IPO:* **Benchling** ($6B+ valuation) | **Dotmatics**<br>**LabArchives**<br>**SciNote**<br>**Weights & Biases** ($1B+)<br>**Arize AI / Phoenix**<br>**LangSmith** | **Marimo** (Reactive notebook)<br>**Curvenote**<br>**MLProvLab** (Jupyter lineage)<br>**DVC / Iterative.ai** | Traditional ELNs are static compliance forms for wet labs; MLOps tools track raw machine metrics (loss, latency). Neither records human-agent *reasoning paths, hypotheses, or failure pivots*. |
| **Task 3: Claim-to-Evidence Linker** | **Research Solutions** (Scite.ai)<br>**Springer Nature** (w/ DeepMind Agent Kit) | **SciScore** (SciCrunch)<br>**Scholarcy**<br>**Factiverse**<br>**QED Science**<br>**Review-it.ai** | **Allen Institute** (SciFact / MultiVerS)<br>**Microsoft Research** (Claimify)<br>**ToolSciVer** (Multimodal visual audit) | Products check external citation sentiments (Scite) or compliance checklists (SciScore). None build an internal, multi-modal bipartite graph linking in-text claims to specific figure sub-panels, tables, and code. |

---

### Task 1: "Is this question worth asking?" Ideation Stress-Test Tool
*Core Objective from Brief:* Take one research question, extract and disambiguate terms, expose implicit assumptions, flag unobtainable data, and issue a definitive recommendation (*proceed / narrow / revise / stop*).

#### 1. Public Companies
- **RELX Group / Elsevier (AMS: REN / NYSE: RELX):** Operates *Scopus* and *SciVal*. Provides macro-level bibliometrics, trend analyses, and author citation tracking. However, it offers zero linguistic or epistemic stress-testing for preliminary research questions before work starts.
- **Clarivate PLC (NYSE: CLVT):** Operates *Web of Science* and *InCites*. Focuses on journal impact, citation indexing, and intellectual property. No automated assumption decomposition or hypothesis critique exists in its suite.
- **Research Solutions (NASDAQ: RSSS):** Acquired *Scite.ai*. Scite provides "Smart Citations" (classifying citations as supporting, mentioning, or contrasting), but it evaluates published literature retrospectively rather than stress-testing an uncommitted question prospectively.

#### 2. Private Startups & Frontier Labs
- **Elicit (elicit.com):** Raised ~$9M. Uses LLMs to query scientific papers, extract data matrices, and summarize findings. *Limitation:* It operates as a discovery and summarization assistant; it does not critique the logical formulation or data-feasibility of the researcher's query.
- **Consensus (consensus.app):** An AI search engine synthesizing peer-reviewed findings into an "agreement meter". *Limitation:* Highly effective at answering "Does creatine increase muscle mass?", but cannot analyze a raw, ambiguous doctoral hypothesis (e.g., "How does digital engagement impact societal cohesion?").
- **Causaly (causaly.com):** Raised $60M+. Maps causal relationships extracted from biomedical literature to accelerate drug target discovery. *Limitation:* Enterprise biopharma focus; maps known cause-and-effect pairs rather than stress-testing novel methodology or uncovering hidden epistemological assumptions.
- **Sakana AI (*The AI Scientist*):** Fully automated end-to-end scientist agent that writes, executes, and reviews papers. *Limitation:* It creates an automated pipeline for rapid execution, but does not serve as an interactive, adversarial sparring partner for human scientists deciding whether to invest months of effort.
- **FutureHouse & DeepMind Co-Scientist:** Frontier labs building autonomous reasoning agents for biology. Their focus is generating valid hypotheses and running protocols, not serving as a lightweight pre-flight gatekeeper.

#### 3. Market White Space
Current tools act as **"yes-men"** (generating complementary literature or congratulatory summaries). There is no dedicated **"hostile peer reviewer for ideation"** that rejects vague terminology, checks open-science data repositories for required empirical measurements, and issues an uncompromising *stop* or *narrow* verdict with literature-grounded justifications.

---

### Task 2: Provenance-Preserving Lab Notebook for AI-Assisted Execution
*Core Objective from Brief:* Build a lightweight logging/wrapper tool around an AI-assisted research task that automatically captures proposed plans, actual execution (code, parameters, data), failures/contradictions, and a human-walkable timeline explaining *why* decisions were made.

#### 1. Public Companies & Enterprise Titans
- **Benchling (Valued at $6.1B, impending IPO):** The market leader in cloud Electronic Lab Notebooks (ELNs) for molecular biology, CRISPR design, and biopharma inventory. *Limitation:* Benchling is designed for manual human data entry and structured biological entities (plasmids, cell lines). It has no concept of tracking the iterative, non-deterministic decision loops of autonomous AI agents or coding assistants.
- **Thermo Fisher Scientific (NYSE: TMO) & Waters Corp (NYSE: WAT):** Provide enterprise LIMS (Laboratory Information Management Systems) and instrument automation. *Limitation:* Heavyweight, rigid compliance and hardware audit trails; completely detached from computational dry-lab workflows and AI agent tool calls.
- **Dassault Systèmes (EPA: DSY):** BIOVIA Notebook. Enterprise compliance-first ELN for chemical patents. Completely inaccessible to modern ML/AI researchers and lacks agent provenance awareness.

#### 2. Private Startups & MLOps / Tracing Platforms
- **Weights & Biases (W&B / Weave):** Raised $250M+. The gold standard for ML experiment tracking (metrics, loss curves, model checkpoints). *Limitation:* W&B tracks *what happened computationally* (floating-point loss over epochs), not *why the human/agent chose to run that script*, what hypothesis failed, or why hyperparameter tuning pivoted at step 4.
- **LangSmith (LangChain), Arize AI (Phoenix), Braintrust:** The emerging leaders in LLM application observability and trace logging. *Limitation:* Built for software engineers monitoring API latency, token costs, and prompt evaluations in production apps. They do not capture scientific provenance (dataset versions, empirical hypotheses, statistical anomalies, or scientific pivots).
- **Curvenote & Marimo:** Modern open-source computational notebook frameworks designed to modernize Jupyter. Marimo introduces reactive execution to fix state hidden-variable bugs, while Curvenote builds version-controlled scientific publishing pipelines. *Limitation:* Neither wraps around an autonomous agent to automatically extract the narrative "reasoning ledger" demanded by the brief.

#### 3. Market White Space (Directly Aligning with User's Vision)
Researchers work across **browser tabs** (Google Colab, JupyterHub, Claude/ChatGPT, PubMed, arXiv, AlphaFold DB). When an AI coding agent or chatbot fails, hallucinates, or pivots, that conversational and code context is discarded across fragmented browser histories. There is no **browser-native research flight recorder** that continuously binds web-based AI discussions, executed code snippets, parameter variations, and human thought logs into a unified, reviewer-ready timeline.

---

### Task 3: Claim-to-Evidence Linker for One Paper
*Core Objective from Brief:* Take a single manuscript/preprint as input, identify all primary claims, link each claim directly to its intra-document proof (figure panel, table row, results snippet, or code repository path), and flag unsupported assertions or mismatched epistemic confidence.

#### 1. Public Companies & Academic Publishers
- **Springer Nature:** Recently announced a research partnership with Google DeepMind utilizing Gemini and the Agent Development Kit (ADK) to prototype automated peer-review assistants (*ScholarPeer*). *Limitation:* Proprietary publisher-facing tool focused on referee assignment and macro manuscript assessment, not an open reader-facing claim-to-figure inspection map.
- **Research Solutions / Scite.ai (NASDAQ: RSSS):** Masters paper-to-paper citation networks, but does not parse the *internal architecture* of a single document to link Section 4.1 claims to Figure 2c.
- **Digital Science (Holtzbrinck Publishing Group) / Ripeta:** Scans manuscripts for reproducibility criteria (data availability statements, software licenses, ethics declarations). *Limitation:* Checks compliance presence/absence rather than validating whether the quantitative assertion in the abstract matches the sample size in Table 1.

#### 2. Private Startups & Specialized Tools
- **SciScore (SciCrunch):** Uses NLP to audit manuscripts for rigor indicators (blinding, randomization, sex as a biological variable, RRID cell-line identification). *Limitation:* Operates as a static checklist checker for editorial desks; does not verify whether experimental data actually supports substantive theoretical claims.
- **Scholarcy:** A commercial "paper summarizer" that extracts key findings, tables, and references into interactive summary cards. *Limitation:* Generates summaries for reader convenience; does not perform adversarial auditing of evidence strength versus claim confidence.
- **Factiverse (Seed-stage):** Automated fact-checking startup for news and corporate text. *Limitation:* Generalist NLP model comparing text against web articles; incapable of interpreting multi-modal scientific figures, gel assays, or statistical regression tables.

#### 3. Academic Frontiers
- **SciFact & MultiVerS (Allen Institute for AI / UW):** Leading research benchmark for scientific claim verification against abstract rationale sentences.
- **ToolSciVer (2026):** Recent breakthrough in multi-modal scientific claim verification using visual-tool-augmented agents to inspect charts and plots.
- **Claimify (Microsoft Research, 2025):** Framework for decomposing long-form texts into atomic factual claims.

#### 4. Market White Space
Reviewers currently have no mechanism to generate a **bipartite Claim-Evidence Graph** of an unreviewed preprint. Current automated tools produce a single qualitative score or generic grammar/rigor summary. An interactive, navigable visual matrix that allows a reviewer to click on a high-confidence claim and immediately see its underlying data points (highlighting small sample sizes, missing error bars, or unverified assertions) is completely absent from commercial software.

---

## 3. Stage 2: Idea Catalog Across the Three Tasks

As requested, below are targeted, high-impact concepts for each task, with descriptions kept strictly to **1–2 sentences**.

### Task 1: "Is this question worth asking?" (Ideation Stress-Test)
1. **The Epistemic Interrogator (Socratic Falsifier):** A web app that subjects a pasted research question to an automated adversarial peer review, decomposing ambiguous variables, identifying unprovable hidden assumptions, and generating a strict *proceed / narrow / revise / stop* scorecard.
2. **TermScope (Literature Semantic Disambiguator):** A tool that connects directly to OpenAlex and Semantic Scholar to contrast every keyword in a user's research question against conflicting empirical definitions in the literature, warning when an operationalization collision exists.
3. **DataFeasibility Radar:** An ideation pre-flight checker that maps the data requirements implied by a research hypothesis against global public repositories (Zenodo, Dryad, GEO, NCBI, Hugging Face) and explicitly flags when needed evidence is non-existent or statistically unfeasible.
4. **AssumptionGraph:** A tool that converts a research question into a directed acyclic graph (DAG) of foundational assumptions, ranking each node by existing literature consensus and pinpointing the single weakest link that could invalidate the entire project.

---

### Task 2: Provenance-Preserving Lab Notebook (Focus Area)
1. **Episteme (The Browser-Based Research Flight Recorder & Diary):** A lightweight Chrome Side Panel extension that passively observes a researcher's web-based AI interactions (ChatGPT, Colab, Claude, arXiv), automatically generating a time-stamped, annotated research diary explaining every hypothesis shift, failed code attempt, and parameter change. *(Flagship)*
2. **WhyGraph (Git-for-Agent-Decisions):** A minimal Python and Jupyter wrapper that intercepts AI agent calls, committing not just code diffs but a structured "decision node" documenting why the agent altered its strategy after a step failure.
3. **ColabTrace (Browser-Native Experiment Sidecar):** A browser extension dedicated to Google Colab and JupyterHub that logs each cell execution, binds it to the conversational AI prompt that generated it, and visually highlights when an approach was abandoned.
4. **AgentChronicle:** A background daemon that translates raw tool calls, environment errors, and parameter sweeps into an auto-generated, human-readable narrative diary structured specifically for external peer reviewers.
5. **PivotLog (The Negative-Result Ledger):** A notebook plugin focused on preserving scientific failures, automatically tagging discarded models or data-cleaning scripts with agent-generated justifications to eliminate redundant experimentation.
6. **ProvenancePill:** A zero-configuration browser toolbar that lets researchers drop bookmarks, AI chat snippets, and terminal logs into a persistent project canvas that compiles an audit trail for published papers with one click.

---

### Task 3: Claim-to-Evidence Linker
1. **ClaimTrace (In-Document Multi-Modal Evidence Linker):** A PDF viewer tool that extracts every empirical assertion in a paper, builds a visual bounding box around its supporting figure sub-panel or table row, and flags claims lacking direct textual or visual evidence.
2. **CalibreSci (Epistemic Calibration Auditor):** An LLM-powered auditing pipeline that scores the mismatch between linguistic assertion strength (e.g., *"proves conclusively"*) and actual empirical backing (e.g., small sample sizes, missing control cohorts, or p-hacking risks).
3. **FigureGround:** A multi-modal vision-language tool that crops every chart and plot in a manuscript, extracts raw plotted values via OCR, and cross-examines them against the quantitative numbers reported in the abstract and results paragraphs.
4. **ReviewerZero Claim Map:** An interactive reviewer dashboard that organizes a preprint into an inspectable claim matrix (*Claim → Evidence → Caveat*), color-coding unverified assertions to focus human peer reviewers on critical weak points.

---

## 4. Deep Dive: The Browser-Based Research Diary & Provenance Tool (Task 2)

Given the user's strong interest in **Task 2**, this section provides a detailed architectural and functional blueprint for **Episteme**, a browser-based research diary designed to win the AI4MetaScience Hackathon.

### The Problem: The Invisible Trail of AI-Assisted Science
When researchers execute projects today, their cognitive and computational workspace is the **web browser**:
- Hypotheses and literature searches happen on **arXiv, PubMed, and AlphaFold DB**.
- Code generation, debugging, and data processing happen in **ChatGPT, Claude, Cursor Web, and GitHub**.
- Model training and data exploration happen in **Google Colab, Kaggle Notebooks, and JupyterHub**.

When an agent hallucinates, a dataset proves corrupt, or a modeling architecture fails, the researcher pivots in seconds. By the time a paper is written, **90% of the exploratory trail is lost**. A reviewer evaluating the methodology has no way of knowing:
- *Why did the authors filter out 30% of the cohort at Step 3?*
- *Was this hyperparameter chosen systematically, or was it the only run that did not crash?*
- *Did the agent try four other architectures that yielded contradictory results?*

```
Traditional Workflow (The Black Box):
[Initial Idea] ──> [200 Unrecorded AI Prompts & Colab Runs] ──> [Final Script & Paper]
                                                                        │
                                                    Reviewer: "Why step 4?" (Unanswerable)

Episteme Workflow (The Provenance-Preserving Trail):
[Initial Idea] ──> [ Episteme Browser Sidecar (Auto-Diary) ] ──> [Auditable Decision Map]
                         │
                         ├─ Capture: Hypothesis proposed in Claude tab
                         ├─ Bind: Code run executed in Google Colab tab
                         ├─ Record: Out-of-memory / error contradiction
                         └─ Explain: "Pivoted from Adam to Sophia due to loss spike"
```

---

### System Architecture of "Episteme"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BROWSER RUNTIME (Chrome Extension)                     │
│                                                                             │
│  Active Workspaces:                                                         │
│  [ Google Colab / Jupyter ]    [ Claude / ChatGPT ]    [ arXiv / AlphaFold] │
│              │                          │                         │         │
│              ▼                          ▼                         ▼         │
│     DOM & Console Observer       Prompt/Response Hook     URL & Context Tap │
│              │                          │                         │         │
└──────────────┼──────────────────────────┼─────────────────────────┼─────────┘
               │                          │                         │
               └─────────────────► ┌──────┴──────┐ ◄────────────────┘
                                   │ Event Bus   │
                                   └──────┬──────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EPISTEME SIDECAR & LOCAL BACKEND                        │
│                                                                             │
│  1. Event Normalizer: Formats raw DOM/chat/code into unified research events│
│  2. Epistemic Reasoner (Local LLM / Gemini API):                             │
│     - Identifies Intent ("Let's test if normalization fixes skew")          │
│     - Detects Outcome ("Runtime error: NaN loss detected")                  │
│     - Generates Pivot Rationale ("Switched from Log-transform to Box-Cox")  │
│  3. Provenance Ledger: SQLite / IndexedDB storing immutable timeline nodes │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REVIEWER & RESEARCHER UI                            │
│                                                                             │
│  - Interactive Research Diary (Chronological markdown notes auto-written)   │
│  - Step-by-Step Decision DAG (Visual graph of pivots and failed branches)   │
│  - One-Click Verification Report (Exportable HTML/PDF for peer reviewers)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Key Functional Components

#### 1. Zero-Friction Web Observation (Sidecar Extension)
Built as a Manifest V3 Chrome Extension featuring a persistent **Chrome Side Panel**:
- **Colab/Jupyter Tagger:** Attaches to the active notebook tab, intercepting cell executions, execution counters, parameter dictionaries, and error stack traces.
- **AI Chat Interceptor:** Monitors interactions on major research chat interfaces (Anthropic Claude, OpenAI ChatGPT, Perplexity), capturing the prompt instruction, the proposed plan, and the returned code block.
- **Manual "Lab Thought" Quick-Drop:** Allows the researcher to hit `Cmd+Shift+E` and type a 5-word thought (e.g., *"data looks right-skewed, testing transform"*) without leaving their coding flow.

#### 2. The Semantic Decision Extractor
Raw telemetry is unreadable to humans. Episteme runs a lightweight parser (powered by Gemini Flash or local LLM) on every batch of execution events to extract four fundamental meta-science primitives:
- **Hypothesis / Intent:** What was the intended purpose of this step?
- **Execution Artifact:** What code was run, what hyperparameters were set, and what data version was accessed?
- **Empirical Outcome:** Did it succeed, crash, or produce contradictory metrics?
- **Adaptive Pivot:** If failed or discarded, why did the direction change?

#### 3. Meeting the Hackathon's Golden Success Criterion
> *Brief Success Criterion: "A reviewer who wasn't present can look at the log after the fact and answer 'why did they change approach at step 4?' without having to ask the researcher."*

**Scenario Walkthrough:**
- **Step 3 in Log:** Agent runs feature extraction using standard TF-IDF on a clinical trial dataset in Google Colab.
- **Contradiction:** High-dimensional sparse matrix exhausts GPU RAM, causing kernel failure. In parallel, cross-validation AUROC stalls at 0.54.
- **Step 4 Pivot in Episteme Diary:**
  ```markdown
  ### [Step 4] Methodological Pivot: Sparse TF-IDF -> Clinical BERT Embeddings
  - **Timestamp:** 14:22:08 CET
  - **Prior State:** Step 3 failed due to out-of-memory error on sparse matrix and poor AUROC (0.54).
  - **Reason for Change:** The researcher and AI agent recognized that clinical note semantics were lost in n-gram tokenization.
  - **Action Taken:** Switched to frozen PubMedBERT embeddings with batch size 32.
  - **Observed Result:** Convergence in 4 epochs, AUROC increased to 0.81.
  ```
A peer reviewer inspecting the exported Episteme timeline sees the full context immediately—no ambiguity, no missing variables, and complete transparency.

---

### 7-Day Hackathon Implementation Blueprint

| Phase | Duration | Deliverables |
| :--- | :--- | :--- |
| **Day 1: Setup & Data Model** | Kick-off (RISE KTH) | Define JSON schema for scientific provenance events; initialize Plasmo/React extension repository; configure local IndexedDB storage. |
| **Day 2: Chrome Extension Side Panel** | Build Days 2–3 | Implement Manifest V3 Side Panel UI; build content scripts to observe Google Colab DOM / notebook execution and LLM chat interfaces. |
| **Day 3: Reasoning Engine** | Build Days 3–4 | Connect event stream to Gemini 2.5/Flash API; implement prompt templates for extracting *Hypothesis*, *Execution*, *Failure*, and *Pivot Rationale*. |
| **Day 4: Interactive Diary UI** | Build Day 5 | Build the researcher's living diary view: split-view timeline, interactive step inspection, code/parameter diff viewers, and Markdown auto-formatter. |
| **Day 5: Reviewer Mode & Export** | Build Day 6 | Implement "Reviewer Audit Mode": a clean, single-page standalone web report generator that packages the timeline into a reproducible HTML bundle. |
| **Day 6: Benchmark & Stress Testing** | Build Day 7 | Run an end-to-end sample AI task (e.g., iterative model tuning on a public Kaggle/bioinformatics dataset) to generate a live, undeniable demonstration trail. |
| **Day 7: Demo Video & Submission** | Nov 17 (18:00 CET) | Polish 3-minute pitch deck, record demo video demonstrating the "Step 4 Pivot", and submit to Stockholm AI / Sweden AI Factory. |

---

## 5. Strategic Hackathon Roadmap: From Stockholm to Paris

### 1. How to Impress the Judges (Stockholm AI, Sweden AI Factory, & NeurIPS Organizers)
- **Avoid Just Another Dev Tool:** Judges at an AI for Meta-Science hackathon do not want another generic developer APM (like Datadog or LangSmith). Emphasize **epistemology, reproducibility, and scientific accountability**.
- **Demonstrate Real Scientific Use Cases:** Instead of a toy Python script (`print("hello")`), showcase a realistic biomedical or scientific workflow—such as fine-tuning a small protein property prediction model or running a bioinformatics data-cleaning pipeline where initial assumptions fail.
- **Zero Overhead for the Researcher:** If a tool requires 10 minutes of manual configuration per run, scientists will reject it. Showing that Episteme functions passively in a browser sidecar proves instant adoptability.

### 2. The 3-Minute Demo Script
1. **The Hook (0:00–0:40):** Show an AI agent rapidly iterating on code in Colab and ChatGPT. Point out how fast the screen scrolls, how many attempts fail, and how quickly the prompt history becomes an untraceable mess.
2. **The Problem Statement (0:40–1:10):** Quote the task brief: *"As execution gets delegated to AI tools, this trail disappears. Reviewers are left with a polished paper and zero provenance."*
3. **The Solution in Action (1:10–2:20):** Open the Episteme Side Panel. Show how each step is captured in real time. Click on **Step 4** and demonstrate how the reviewer sees the exact failed code, the error, and the explicit reasoning for why the method was abandoned.
4. **The Meta-Science Impact (2:20–3:00):** Show the one-click exportable "Scientific Audit Trail" attached to a preprint. Connect directly to the NeurIPS 2026 workshop vision: bringing true accountability to the age of autonomous AI scientists.

---

## 6. Conclusion & Next Steps

This investigation demonstrates that while the commercial market is saturated with automated discovery tools, paper summarizers, and code generators, **the meta-science layer—validation, provenance, and verification—is wide open**.

By focusing on **Task 2 (Provenance-Preserving Lab Notebook)** with a **browser-based research diary**, the team addresses:
- The exact personal preference and natural workflow of the researcher.
- A critical structural void in current MLOps and ELN tooling.
- The highest-probability path to winning the Stockholm Hackathon and securing an oral presentation at NeurIPS 2026 in Paris.

*Next immediate step:* Align on the product name, finalize the Git repository structure, and initialize the browser extension scaffolding before the November 10 kick-off at RISE KTH.
