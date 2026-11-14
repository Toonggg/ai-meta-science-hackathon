# Episteme AlphaFold Demo & Agent Guide

## 1. Project Summary
**Episteme** is a zero-dependency research flight recorder built for the AI4MetaScience hackathon. It tracks the provenance of AI-assisted scientific discovery across three core tasks:
1. **Task 1 (Vet Question):** Stress-tests research questions against pre-cutoff literature and flags unstated assumptions or feasibility limits.
2. **Task 2 (Provenance Diary & Ledger):** Automatically captures plans, tool runs, surprises, and pivots to answer the brief's defining test: *"Why did they change approach at step 4?"*
3. **Task 3 (Claim-to-Evidence Linker):** Extracts paper claims and maps them back to verified run evidence and caveats.

---

## 2. Quickstart: Human Presenter Demo

### Step 1: Start Episteme
```bash
./run
```
Opens Episteme at `http://127.0.0.1:8765`. It auto-loads credentials from `.env` (configured for Berget AI).

### Step 2: Replay the AlphaFold Discovery Session
In a second terminal:
```bash
python3 tools/replay.py demo/alphafold_session.jsonl --clear --project "AlphaFold 2 Discovery (CASP14)" --speed 15
```
*(Use `--instant` to load all events immediately without waiting).*

### Step 3: Demonstrate in the Browser
1. **Watch Timeline:** See the baseline run fail on CASP target `T1024` (`gdt_ts=61.2`), triggering an auto-detected **Surprise** in the Hypothesis Ledger.
2. **Review Step 4 (The Pivot):** Observe the agent proposing a pivot to end-to-end **Evoformer + IPA** attention. Click **Confirm** on the pivot card to attribute approval to the lead researcher.
3. **Ask the Log:** In the side panel, prompt:
   > *"Why did they change approach at step 4?"*
   
   Episteme returns the grounded rationale citing the failure of physical relaxation in run 2, triangle inequality violations in 2D distograms, and contemporaneous SE(3) equivariance literature.

---

## 3. Autonomous AI Agent Instructions

AI agents running headless benchmarks or automating evaluations can operate Episteme via stdlib Python or HTTP without opening a browser.

### Headless Verification Flow:

1. **Launch Server:**
   ```bash
   python3 episteme/server.py --state .episteme --port 8765 &
   SERVER_PID=$!
   ```

2. **Replay Session Instantly:**
   ```bash
   python3 tools/replay.py demo/alphafold_session.jsonl --instant --clear --project "AlphaFold 2 Discovery"
   ```

3. **Verify Stitched Events via API:**
   ```bash
   # Retrieve diary events
   curl -s http://127.0.0.1:8765/api/events | grep -o '"type":"[^"]*"'

   # Query the provenance log programmatically
   curl -s http://127.0.0.1:8765/api/ask \
     -H 'Content-Type: application/json' \
     -d '{"question": "Why did they change approach at step 4?"}'
   ```

4. **Shutdown Server:**
   ```bash
   kill $SERVER_PID
   ```
