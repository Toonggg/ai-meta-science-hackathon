# AI4MetaScience Hackathon: Task 2 Demo Guide

> **Task 2: Provenance-Preserving Lab Notebook for AI-Assisted Execution**  
> *Core Problem:* In AI-assisted science, an agent codes, tests, and pivots autonomously. The reasoning behind decisions disappears, quietly destroying scientific reproducibility.  
> *Success Criterion:* A reviewer who was never in the room can look at the log and answer:  
> **"Why did they change approach at step 4?"** without asking the researcher.

---

## 1. Quickstart

### Start the Server
```bash
./run
```
Opens `http://127.0.0.1:8765` in your browser. (Zero external dependencies; pure Python 3.9+ standard library).

---

## 2. Two Demo Paths

### Path A: One-Click Browser Demo (Fastest & Safest)
1. In the browser header, click the **`⚡ Load AlphaFold Demo`** button (or select **AlphaFold** from the start screen).
2. The complete provenance timeline renders instantly.
3. In the right **Auditor Station** panel, click:  
   **`🎯 Test Question: "Why did they change approach at step 4?"`**
4. Watch Episteme answer immediately with grounded citations to `[E2]` and `[E4]`.

### Path B: Live Streaming Replay (Most Visual / Engaging)
Show the audience the log populating in real time as an AI agent works:
1. Start Episteme:
   ```bash
   ./run
   ```
2. In a second terminal, replay the AlphaFold discovery session at 15x speed:
   ```bash
   python3 tools/replay.py demo/alphafold.jsonl --clear --project "AlphaFold 2 discovery (CASP14)" --speed 15
   ```
3. Watch the browser timeline stream events as they happen:
   - **Step 1 (Plan):** Expectation set: `GDT_TS >= 80.0`.
   - **Step 2 (Run):** Dilated ResNet + physical gradient descent fails on CASP target `T1024` (`gdt_ts=61.2`).
   - **Step 3 (Surprise):** Auto-detected contradiction in the Hypothesis Ledger (`Missed target by -18.8`).
   - **Step 4 (Pivot):** Proposes end-to-end Evoformer + Invariant Point Attention head. Click **Confirm** (`Agent Stated ✓`).
   - **Step 5 (Run & Artifact):** Reaches `gdt_ts=89.4`, followed by Git commit `b8e104f`.

---

## 3. The 3-Minute Presentation Pitch Script

| Time | Slide / Screen Action | Spoken Script |
| :--- | :--- | :--- |
| **0:00 - 0:30** | Show title & empty diary | *"In 2026, AI agents can write code, train models, and run science experiments overnight. But when you inspect the final result in the morning, why was the baseline abandoned? Why did they change hyperparameters or switch models at step 4? The decision trail vanishes. Episteme is a zero-overhead research flight recorder that preserves scientific provenance as work happens."* |
| **0:30 - 1:15** | Trigger replay or load demo | *"Episteme non-invasively wraps Claude Code and Git using simple hooks. Here, a simulated team investigates protein folding on CASP target T1024. Notice step 1: the researcher states an explicit expectation: GDT_TS >= 80.0. At step 2, physical relaxation stalls at 61.2. Without human intervention, Episteme's rule engine auto-detects a Surprise in the Hypothesis Ledger."* |
| **1:15 - 2:00** | Point out the Step 4 Pivot card | *"This triggers the Step 4 Pivot: switching from 2-stage physical relaxation to an end-to-end Evoformer with Invariant Point Attention. Notice the attribution badge: 'Agent (Stated)'. Episteme enforces that AI cannot put words in anyone's mouth — it quotes verbatim. The lead researcher clicks 'Confirm' to sign off."* |
| **2:00 - 2:40** | Click **"Why did they change approach at step 4?"** | *"Now put yourself in the shoes of a peer reviewer or grant auditor who wasn't there. Click 'Why did they change approach at step 4?'. Episteme parses the provenance graph and produces a grounded explanation: steric clashes and triangle inequality violations in distograms [E2] led to the direct 3D backbone frame approach [E4]. Hovering jumps directly to the evidence."* |
| **2:40 - 3:00** | Show **Export & Capture** box | *"Finally, click 'W3C PROV-JSON' and 'Decision Appendix'. Episteme outputs open provenance standards ready for archival or paper submission. Built with 100% Python standard library, zero npm/pip packages, runs offline or online."* |

---

## 4. Key Differentiators to Highlight for Judges

1. **Deterministic Rules First, LLM Second:**
   - Episodes, metrics, expectations, and surprises are detected instantly by deterministic rules. The LLM is only called to classify pivots and summarize, and an offline heuristic fallback is always available.
2. **Strict Attribution & Anti-Hallucination:**
   - Every statement carries an actor badge: `Researcher (Stated)`, `Agent (Stated)`, `Inferred`, or `Confirmed ✓`. Stated reasons must be verbatim quotes from the raw log.
3. **Open Standards:**
   - Complies with W3C PROV-JSON specifications for scientific provenance.
4. **Non-Invasive Capture:**
   - Installable in any existing research repository with a single command:  
     `python3 capture/install.py /path/to/project`
