"""Task 1: "Is this question worth asking?"

Heuristic mode uses a small lexicon of constructs known to be operationalised
in conflicting ways (the jingle-jangle problem, Wulff & Mata 2025). It is a
stand-in for the literature-backed term-sense mapper described in
claude_research.md (OpenAlex / Semantic Scholar clustering). AI mode asks
Claude for the same structure.
"""

import re

import llm

# term -> (senses as operationalised in the literature, data notes)
LEXICON = {
    "engagement": (["time-on-app / session minutes (logged)", "self-report engagement scales (e.g. UWES-style)",
                    "behavioural interactions: likes, clicks, posts", "psychological absorption / flow"],
                   "Logged usage is mostly platform-internal; self-report is obtainable but noisy."),
    "social media": (["any platform use (aggregate screen time)", "specific platforms (Instagram, TikTok, ...)",
                      "active posting vs passive scrolling", "algorithmic feed exposure"],
                     "Platform-level exposure data is rarely accessible to academics."),
    "wellbeing": (["life satisfaction (Cantril ladder)", "affect / mood (PANAS)", "clinical symptoms (PHQ-9, GAD-7)",
                   "eudaimonic wellbeing (purpose, autonomy)"],
                  "Survey cohorts exist (e.g. UK Millennium Cohort, Add Health)."),
    "well-being": None,  # alias
    "mental health": (["diagnosed disorder", "symptom scale scores", "help-seeking / service use", "self-rated mental health"],
                      "Diagnoses need clinical records; symptom scales are in many cohorts."),
    "performance": (["accuracy on a benchmark", "speed / latency", "human-rated quality", "downstream task success"],
                    "Specify the metric and the benchmark."),
    "productivity": (["output per hour", "tasks completed", "self-reported productivity", "revenue / value added"],
                     "Firm-level productivity data is often proprietary."),
    "intelligence": (["IQ test scores", "g-factor from batteries", "academic achievement", "task-specific benchmark (for AI)"],
                     "Instrument choice changes conclusions."),
    "quality": (["expert ratings", "citation counts", "replication success", "reviewer scores"],
                "Different proxies disagree; state which one."),
    "impact": (["citations", "policy uptake", "economic value", "causal effect size"],
               "'Impact' is both a construct and a causal claim; separate them."),
    "trust": (["self-reported trust scales", "behavioural reliance (advice taking)", "institutional trust surveys"],
              "Behavioural reliance needs an experiment."),
    "bias": (["statistical bias of an estimator", "demographic performance gaps", "stereotype association (e.g. WEAT)",
              "cognitive bias"],
             "Very different literatures share this word."),
    "fairness": (["demographic parity", "equalised odds", "calibration within groups", "individual fairness"],
                 "These criteria are mutually incompatible in general."),
    "misinformation": (["false claims (fact-checked)", "misleading-but-true content", "low-credibility source domains"],
                       "Labels depend on the fact-checker list used."),
    "learning": (["test score gains", "retention after delay", "skill transfer", "self-reported learning"],
                 "Needs pre/post measurement."),
    "creativity": (["divergent thinking tests (AUT)", "expert-rated originality", "novelty of outputs vs corpus"],
                   "Ratings are rater-dependent."),
    "cohesion": (["interpersonal trust", "civic participation", "network clustering", "polarisation indices"],
                 "Mostly survey-based; network data is hard to get."),
    "polarization": (["affective polarisation (feeling thermometers)", "ideological distance", "network segregation"],
                     "Affective and ideological polarisation can move in opposite directions."),
    "success": (["graduation / completion", "income", "self-rated success", "citations or awards"],
                "Pick one and justify it."),
    "readmission": (["any-cause 30-day readmission", "unplanned readmission only", "readmission to the same hospital"],
                    "Same-hospital readmission undercounts; linked claims data fixes this."),
    "ai": (["large language models", "any machine learning system", "automated decision rules"],
           "Name the system class you mean."),
}
LEXICON["well-being"] = LEXICON["wellbeing"]

CAUSAL = re.compile(r"\b(impact|effects?|affects?|causes?|caus\w+|leads? to|drives?|improves?|reduces?|increases?|"
                    r"decreases?|influences?|harms?|benefits?|makes?)\b", re.I)
NORMATIVE = re.compile(r"\b(should|ought|must we|is it right|is it moral|good or bad)\b", re.I)
BROAD_POP = re.compile(r"\b(society|people|humans?|humanity|everyone|the world|users|individuals)\b", re.I)
SPECIFIC_POP = re.compile(r"\b((?:adult |older |young |pediatric |paediatric )?(?:inpatients?|patients?)|adolescents?|teen\w*|children|adults?|students?|patients?|inpatients?|nurses|"
                          r"workers|employees|women|men|aged \d+|\d+\s*-\s*\d+[- ]year|in [A-Z][a-z]+)\b")
TIMEFRAME = re.compile(r"\b(\d{4}|years?|months?|weeks?|days?|longitudinal|over time|during|after|before|within)\b", re.I)
UNIVERSAL = re.compile(r"\b(all|always|never|every|any)\b", re.I)
RESTRICTED_HINT = re.compile(r"\b(algorithm\w*|feed|platform|internal|private|proprietary|counterfactual|"
                             r"time-on-app|recommend\w*)\b", re.I)


def heuristic(q):
    text = q.strip()
    low = text.lower()

    cm = CAUSAL.search(text)
    causal = bool(cm)
    terms = []
    for term, entry in LEXICON.items():
        if term == "well-being" and "wellbeing" in low:
            continue
        m = re.search(r"\b" + re.escape(term) + r"\b", low)
        if not m:
            continue
        if cm and m.start() == cm.start():
            continue  # e.g. 'impact' used as the causal verb, not as a construct
        senses, note = entry
        terms.append({"term": term, "senses": senses, "note": note, "pos": m.start(), "end": m.end()})
    terms.sort(key=lambda t: t["pos"])
    normative = bool(NORMATIVE.search(text))
    broad = BROAD_POP.search(text)
    specific = SPECIFIC_POP.search(text)
    has_time = bool(TIMEFRAME.search(text))

    assumptions = []
    for t in terms:
        assumptions.append({
            "text": "'%s' is a single, agreed-upon construct" % t["term"],
            "risk": "high" if len(t["senses"]) >= 3 else "medium",
            "check": "The literature uses at least %d operationalisations (%s). Pick one and justify it."
                     % (len(t["senses"]), "; ".join(t["senses"][:3])),
        })
    if causal:
        verb = cm.group(0)
        assumptions.append({
            "text": "The relationship is causal ('%s'), not just an association" % verb,
            "risk": "high",
            "check": "Observational data cannot identify this without a design: randomised experiment, natural experiment, "
                     "or longitudinal panel with fixed effects. Reverse causation is plausible.",
        })
    if broad and not specific:
        assumptions.append({
            "text": "The effect is the same across '%s'" % broad.group(0),
            "risk": "medium",
            "check": "Effects usually differ by age, context and subgroup. Name the population.",
        })
    if UNIVERSAL.search(text):
        assumptions.append({
            "text": "A universal quantifier ('%s') holds without exceptions" % UNIVERSAL.search(text).group(0),
            "risk": "medium",
            "check": "Universal claims are falsified by one counter-example; reframe as an average or conditional effect.",
        })
    if not has_time:
        assumptions.append({
            "text": "Timing does not matter (no time frame or follow-up period is stated)",
            "risk": "low",
            "check": "State when the exposure and the outcome are measured.",
        })

    data_needs = []
    for t in terms:
        note = t["note"].lower()
        restricted = "platform" in note or "proprietary" in note or "clinical records" in note
        data_needs.append({
            "need": "A measurement of '%s' (%s)" % (t["term"], t["senses"][0]),
            "availability": "restricted" if restricted else "available",
            "where": t["note"],
        })
    if causal:
        data_needs.append({
            "need": "Exogenous variation in the exposure (experiment, policy change, outage) or repeated measures",
            "availability": "unknown",
            "where": "Search for natural experiments; otherwise downgrade the question to an association.",
        })
    if RESTRICTED_HINT.search(text):
        data_needs.append({
            "need": "Platform-internal or counterfactual data implied by '%s'" % RESTRICTED_HINT.search(text).group(0),
            "availability": "unobtainable",
            "where": "Usually only accessible to the platform itself (or via data-donation studies).",
        })

    issues = []
    if normative:
        verdict, reason = "stop", "The question is normative ('should'/'ought'). Data cannot settle it; reframe it as an empirical question about consequences."
    else:
        n_amb = sum(1 for t in terms if len(t["senses"]) >= 3)
        n_unob = sum(1 for d in data_needs if d["availability"] == "unobtainable")
        if n_amb >= 2:
            verdict = "revise"
            reason = "%d core terms (%s) each have several incompatible operationalisations; the question has no single answer as written." % (
                n_amb, ", ".join("'%s'" % t["term"] for t in terms if len(t["senses"]) >= 3))
        elif n_unob and causal:
            verdict = "revise"
            reason = "It makes a causal claim that needs data researchers usually cannot obtain."
        elif (broad and not specific) or causal or not has_time or n_amb == 1:
            verdict = "narrow"
            bits = []
            if broad and not specific:
                bits.append("the population is too broad ('%s')" % broad.group(0))
            if causal:
                bits.append("it is causal without an identification strategy")
            if n_amb == 1:
                bits.append("'%s' needs a fixed definition" % next(t["term"] for t in terms if len(t["senses"]) >= 3))
            if not has_time:
                bits.append("there is no time frame")
            reason = "Answerable once narrowed: " + "; ".join(bits) + "."
        else:
            verdict, reason = "proceed", "Terms, population and time frame are specific enough to start."
    issues = reason

    # Narrowing ladder: three progressively sharper rewrites.
    if specific:
        pop = specific.group(0)
        if pop.lower() in ("adolescent", "adult", "student", "patient", "inpatient", "teen", "teenager"):
            pop += "s"
    else:
        pop = "[a named population, e.g. 13-15-year-olds in Sweden]"
    split_at = cm.start() if cm else None
    if split_at is None:
        m = re.search(r"\b(predicts?|associated|correlat\w*|relat\w*|and|between|with|on)\b", low)
        split_at = m.start() if m else len(low)
    xs = [t for t in terms if t["pos"] < split_at]
    ys = [t for t in terms if t["pos"] >= split_at]
    if not xs and len(ys) > 1:
        xs, ys = ys[:1], ys[1:]

    def phrase(group, fallback):
        if not group:
            return fallback, fallback
        name = text[group[0]["pos"]:group[-1]["end"]]
        return name, "%s (measured as %s)" % (name, group[-1]["senses"][0])

    x_name, x = phrase(xs, "[exposure]")
    y_name, y = phrase(ys, "[outcome]")
    rewrites = [
        "Among %s, is %s associated with %s?" % (pop, x_name, y_name),
        "Among %s, is %s associated with %s over 12 months?" % (pop, x, y),
        "Among %s, does a change in %s predict a later change in %s, using a two-wave panel with individual fixed effects?"
        % (pop, x, y),
    ]
    for t in terms:
        t.pop("pos", None)
        t.pop("end", None)

    return {
        "mode": "heuristic",
        "verdict": verdict,
        "verdict_reason": issues,
        "terms": terms,
        "assumptions": assumptions,
        "data_needs": data_needs,
        "rewrites": rewrites,
        "already_answered": "Not checked in offline mode. With AI mode or a literature backend (OpenAlex, Elicit), "
                            "Episteme would look for existing systematic reviews and recommend 'stop' or 'narrow' if one exists.",
    }


SCHEMA = llm.obj({
    "verdict": llm.enum("proceed", "narrow", "stop", "revise"),
    "verdict_reason": llm.STR,
    "terms": llm.arr(llm.obj({"term": llm.STR, "senses": llm.arr(llm.STR), "note": llm.STR})),
    "assumptions": llm.arr(llm.obj({"text": llm.STR, "risk": llm.enum("high", "medium", "low"), "check": llm.STR})),
    "data_needs": llm.arr(llm.obj({"need": llm.STR, "availability": llm.enum("available", "restricted", "unobtainable", "unknown"),
                                   "where": llm.STR})),
    "rewrites": llm.arr(llm.STR),
    "already_answered": llm.STR,
})

SYSTEM = """You are a demanding methodologist who stress-tests a research question before anyone invests months in it.
Be specific, never generic. Good: "'engagement' is used in at least three senses: time-on-app, self-report scales, click behaviour".
Bad: "consider defining your terms".
- terms: each key term that is ambiguous or used inconsistently in the literature, with the distinct operationalisations (senses) and a note on how that affects the answer.
- assumptions: the implicit presuppositions, with risk and a concrete check against the literature or data.
- data_needs: what evidence would answer the question, whether it is available / restricted / unobtainable, and named sources (datasets, repositories, cohorts).
- rewrites: exactly three progressively narrower rewrites (PICO/FINER style), the last one with a named design.
- already_answered: name known systematic reviews or meta-analyses if you are confident they exist; otherwise say what to search for. Never invent citations.
- verdict: proceed / narrow / revise / stop, with a one-paragraph reason that cites the specific problems above."""


def analyse(question, use_ai):
    if use_ai and llm.available():
        try:
            out = llm.structured(SYSTEM, "Research question:\n" + question, SCHEMA)
            out["mode"] = "ai"
            return out
        except llm.LLMError as e:
            out = heuristic(question)
            out["ai_error"] = str(e)
            return out
    return heuristic(question)
