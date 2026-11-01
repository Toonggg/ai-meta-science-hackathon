"""Task 1 as a visible three-stage pipeline, run as a background job the UI polls.

  1. Local rules   instant, nothing leaves the machine
  2. Search        keywords (not the full question) go to free scholarly APIs;
                   finds existing reviews, how papers measure each term, datasets
  3. AI refine     the model reads stage 1+2, proposes sharper searches, we run
                   them, and it writes a critique citing only papers we found

Every finding carries an `origin` (rule / search / ai) so the UI can show where
it came from, in the same spirit as the diary's stated/inferred labels.
"""

import re
import threading
import time
import uuid

import llm
import question
import search

JOBS = {}
_lock = threading.Lock()

STOP = set("""a an the of to in on at and or for with by from into about how does do did is are was were what which who
whom whose why when where will would can could should may might must this that these those there their its it as be
been being than then so such not no yes vs versus between among across over under more less most least any all each
other study effect effects impact impacts affect affects influence relationship role use using among""".split())

GENERIC_CUES = set("""time self report reported scale scales score scores measure measured measures based level levels
specific data rate rates life any other general from with into number use used using test tests total""".split())


def new_job():
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "status": "running", "created": time.time(), "updated": time.time(),
           "stages": {s: {"state": "pending", "note": ""} for s in ("local", "search", "ai")},
           "analysis": None, "papers": [], "datasets": [], "web": []}
    with _lock:
        for k in [k for k, j in JOBS.items() if time.time() - j["created"] > 3600]:
            JOBS.pop(k, None)
        JOBS[jid] = job
    return job


def get(jid):
    with _lock:
        j = JOBS.get(jid)
        return None if j is None else _copy(j)


def _copy(o):
    if isinstance(o, dict):
        return {k: _copy(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_copy(v) for v in o]
    return o


def _set(job, **kw):
    with _lock:
        job.update(kw)
        job["updated"] = time.time()


def _stage(job, name, state, note="", **extra):
    with _lock:
        job["stages"][name].update(state=state, note=note, **extra)
        job["updated"] = time.time()


def start(q, use_search, use_ai):
    job = new_job()
    threading.Thread(target=_run, args=(job, q, use_search, use_ai), daemon=True).start()
    return job["id"]


# ------------------------------------------------------------------ helpers
def keywords(q, analysis):
    """Search keywords: lexicon terms first (as phrases), then other content words."""
    low = q.lower()
    out = [t["term"] for t in analysis["terms"]]
    for w in re.findall(r"[a-z][a-z0-9-]+", low):
        if w in STOP or len(w) < 4 or any(w in t for t in out):
            continue
        out.append(w)
    return out[:7]


def sense_cues(label, term=""):
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]+", label)
    own = set(re.findall(r"[a-z0-9-]+", term.lower()))  # the term itself is not evidence for one sense
    cues = []
    for w in words:
        if w.lower() in own:
            continue
        if re.fullmatch(r"[A-Z0-9-]{2,}", w):  # acronyms: PHQ-9, PANAS, UWES
            cues.append(w.lower())
        elif len(w) >= 4 and w.lower() not in GENERIC_CUES:
            cues.append(w.lower())
    return cues


def tag(items, origin):
    for it in items:
        it.setdefault("origin", origin)
    return items


def cite_list(papers, limit=40, abstract_chars=500):
    lines = []
    for p in papers[:limit]:
        meta = ", ".join(str(x) for x in (p.get("year"), p.get("venue"), p["kind"].replace("_", " "),
                                          "%s citations" % p["citations"] if p.get("citations") is not None else "") if x)
        lines.append("[%s] %s (%s)\n    %s" % (p["id"], p["title"], meta, (p.get("abstract") or "(no abstract)")[:abstract_chars]))
    return "\n".join(lines)


# ------------------------------------------------------------------ stage 2 enrichment
def enrich(analysis, papers, datasets, web, kw):
    a = analysis
    n = len(papers)
    # How do papers that use each term actually measure it?
    for t in a["terms"]:
        using = [p for p in papers if t["term"] in (p["title"] + " " + p.get("abstract", "")).lower()]
        t["papers_using"] = len(using)
        ev = []
        for sense in t["senses"]:
            cues = sense_cues(sense, t["term"])
            hits = [p for p in using if cues and any(c in (p["title"] + " " + p.get("abstract", "")).lower() for c in cues)]
            ev.append({"sense": sense, "count": len(hits), "papers": [p["id"] for p in hits[:4]]})
        t["evidence"] = ev
        seen = sum(1 for e in ev if e["count"])
        if using:
            t["note"] = ("%s Search: %d of the %d papers found use '%s'; %d of the %d senses appear among them."
                         % (t["note"], len(using), n, t["term"], seen, len(ev))).strip()

    # Already answered? Systematic reviews / meta-analyses covering most of the keywords.
    reviews = [p for p in papers if p["kind"] == "systematic_review" and p.get("coverage", 0) >= 0.6]
    if reviews:
        top = reviews[:4]
        a["already_answered"] = ("Search found %d systematic review(s) or meta-analyses that overlap most of your "
                                 "keywords: %s. Check whether they already answer your question; if so, narrow to what "
                                 "they leave open."
                                 % (len(reviews), "; ".join("[%s] %s (%s)" % (p["id"], p["title"], p.get("year") or "n.d.")
                                                            for p in top)))
        a["already_answered_origin"] = "search"
        if a["verdict"] == "proceed":
            a["verdict"] = "narrow"
            a["verdict_reason"] = ("Existing systematic reviews already cover this ([%s]). Narrow to a sub-question they "
                                   "leave open." % "], [".join(p["id"] for p in top[:2]))
            a["verdict_origin"] = "search"
    elif n:
        a["already_answered"] = ("Search found %d related papers but no systematic review or meta-analysis matching most "
                                 "of the keywords, which suggests the question is still open (absence in the top results "
                                 "is not proof)." % n)
        a["already_answered_origin"] = "search"

    # Datasets found.
    if datasets:
        a["data_needs"].append({
            "need": "Candidate open datasets found by search",
            "availability": "available",
            "where": "; ".join("[%s] %s (%s)" % (d["id"], d["title"][:80], d["venue"] or d["source"]) for d in datasets[:5]),
            "origin": "search",
        })
    return a


# ------------------------------------------------------------------ stage 3 prompts
REFINE_SCHEMA = llm.obj({"queries": llm.arr(llm.obj({"query": llm.STR, "purpose": llm.STR}))})
REFINE_SYSTEM = """You plan literature searches to stress-test a research question.
You are given the question, a rule-based first pass, and the papers a first keyword search returned.
Propose 2-4 short keyword queries (3-7 words each, no boolean syntax) that would fill the biggest gaps, e.g.:
how a specific ambiguous term is operationalised, whether a systematic review already exists, a competing explanation,
or a dataset that could answer it. Say in `purpose` what each query is for."""

GROUNDED_SCHEMA = dict(question.SCHEMA)
GROUNDED_SCHEMA["properties"] = dict(question.SCHEMA["properties"],
                                     key_papers=llm.arr(llm.obj({"id": llm.STR, "why": llm.STR})))
GROUNDED_SCHEMA["required"] = list(GROUNDED_SCHEMA["properties"])

GROUNDED_SYSTEM = question.SYSTEM + """

You are also given numbered search results: papers [P1], [P2], ... and datasets [D1], ... retrieved from scholarly APIs
(Semantic Scholar, OpenAlex, Europe PMC, PubMed, Crossref, arXiv, Zenodo, DataCite, Hugging Face).
- Ground the critique in them and cite inline with their ids, e.g. "'engagement' is measured as time-on-app [P3] and as a self-report scale [P7]".
- Cite ONLY ids from the list. Never invent papers. If the results don't cover a point, say that it is unverified.
- already_answered: name the reviews by id if they address the question.
- key_papers: the 3-6 results a researcher should read first, with one line each on why."""


# ------------------------------------------------------------------ the job
def _run(job, q, use_search, use_ai):
    try:
        # 1 - local
        _stage(job, "local", "running")
        a = question.heuristic(q)
        for k in ("terms", "assumptions", "data_needs"):
            tag(a[k], "rule")
        a["verdict_origin"] = "rule"
        a["already_answered_origin"] = "rule"
        _set(job, analysis=a)
        _stage(job, "local", "done", "%d terms, %d assumptions" % (len(a["terms"]), len(a["assumptions"])))

        # 2 - search
        papers, datasets, web = [], [], []
        kw = keywords(q, a)
        if not use_search:
            _stage(job, "search", "skipped", "Search is turned off")
        elif not search.status()["available"]:
            _stage(job, "search", "skipped", "All sources are disabled")
        else:
            core = " ".join(kw)
            queries = [core, " ".join(kw[:4]) + " systematic review meta-analysis"]
            _stage(job, "search", "running", "Searching %d sources" % search.status()["enabled"], keywords=kw,
                   queries=queries)
            papers, rep_p = search.search_group("papers", queries, n=12)
            papers = search.rank(papers, kw)
            papers = [p for p in papers if p["coverage"] >= 0.4][:30] or papers[:10]
            for i, p in enumerate(papers):
                p["id"] = "P%d" % (i + 1)
            datasets, rep_d = search.search_group("datasets", " ".join(kw[:3]), n=6)
            datasets = [d for d in search.rank(datasets, kw) if d["coverage"] >= 0.34][:8]
            for i, d in enumerate(datasets):
                d["id"] = "D%d" % (i + 1)
            rep_w = []
            if any(s["enabled"] for s in search.status()["sources"] if s["group"] == "web"):
                web, rep_w = search.search_group("web", q, n=6)
                for i, w in enumerate(web):
                    w["id"] = "W%d" % (i + 1)
            a = enrich(a, papers, datasets, web, kw)
            report = rep_p + rep_d + rep_w
            answered = [r for r in report if r["state"] == "ok"]
            failed = [r for r in report if r["state"] in ("failed", "skipped")]
            note = "%d papers, %d reviews, %d datasets from %d sources" % (
                len(papers), sum(p["kind"] == "systematic_review" for p in papers), len(datasets), len(answered))
            if failed:
                note += "; %d unavailable (covered by the others)" % len(failed) if answered else "; no source answered"
            _set(job, analysis=a, papers=papers, datasets=datasets, web=web)
            _stage(job, "search", "done" if answered else "failed", note, report=report, keywords=kw, queries=queries)

        # 3 - AI refine
        if not llm.available():
            _stage(job, "ai", "skipped", "No model connected. Click the model badge (top right) to add one, or use a local model.")
        elif not use_ai:
            _stage(job, "ai", "skipped", "AI is switched off")
        else:
            label = llm.status()["label"]
            extra_q = []
            if papers:
                _stage(job, "ai", "running", "%s is planning follow-up searches" % label)
                plan = llm.structured(REFINE_SYSTEM, "QUESTION: %s\n\nFIRST PASS VERDICT: %s - %s\n\nKEYWORDS: %s\n\nPAPERS:\n%s"
                                      % (q, a["verdict"], a["verdict_reason"], ", ".join(kw),
                                         cite_list(papers, 20, 250)), REFINE_SCHEMA)
                extra_q = [x for x in plan["queries"] if x["query"].strip()][:4]
                _stage(job, "ai", "running", "Running %d refined searches" % len(extra_q), queries=extra_q)
                more, rep = search.search_group("papers", [x["query"] for x in extra_q], n=8)
                known = {search._norm_title(p["title"]) for p in papers}
                more = [p for p in search.rank(more, kw + [w for x in extra_q for w in x["query"].lower().split()])
                        if search._norm_title(p["title"]) not in known][:15]
                for i, p in enumerate(more):
                    p["id"] = "P%d" % (len(papers) + i + 1)
                    p["via_ai"] = True
                papers = papers + more
                _set(job, papers=papers)
            _stage(job, "ai", "running", "%s is writing a grounded critique" % label, queries=extra_q)
            evidence = ("PAPERS:\n%s\n\nDATASETS:\n%s" % (cite_list(papers), cite_list(datasets, 10, 200))) if papers else \
                "No search results are available. Say clearly that your critique is not grounded in retrieved literature."
            out = llm.structured(GROUNDED_SYSTEM if papers else question.SYSTEM,
                                 "Research question:\n%s\n\n%s" % (q, evidence),
                                 GROUNDED_SCHEMA if papers else question.SCHEMA)
            for k in ("terms", "assumptions", "data_needs"):
                tag(out[k], "ai")
            out["verdict_origin"] = out["already_answered_origin"] = "ai"
            out["mode"] = "ai"
            out.setdefault("key_papers", [])
            ids = {p["id"] for p in papers} | {d["id"] for d in datasets}
            out["key_papers"] = [k for k in out["key_papers"] if k["id"] in ids]
            _set(job, analysis=out, rules_analysis=a)
            _stage(job, "ai", "done", "Grounded in %d papers" % len(papers) if papers else "Not grounded (no search results)",
                   queries=extra_q)
    except llm.LLMError as e:
        _stage(job, "ai", "failed", str(e))
    except Exception as e:  # never leave the UI spinning
        for name, st in job["stages"].items():
            if st["state"] in ("running", "pending"):
                _stage(job, name, "failed", "Internal error: %s" % e)
                break
    finally:
        for name, st in job["stages"].items():
            if st["state"] == "pending":
                _stage(job, name, "skipped", "")
        _set(job, status="done")
