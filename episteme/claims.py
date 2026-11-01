"""Task 3: claim-to-evidence linker for one paper.

Produces a claim map (claim -> anchors -> certainty vs evidence -> status), not
a score, plus an explicit checked/unverified ledger. Cross-task twist from
claude_research.md ("one lifecycle, one diary"): numbers in a claim are also
traced back to the diary runs that produced them.
"""

import re

import llm

STRONG = re.compile(r"\b(prove[sn]?|demonstrates?|demonstrated|establish(es|ed)?|conclusively|clearly|necessary|"
                    r"always|substantially|dramatically|robust|generali[sz]es?)\b", re.I)
MODERATE = re.compile(r"\b(show[sn]?|find|found|outperforms?|improves?|achieves?|reach(es)?|explains?|reveals?|"
                      r"faster|better|higher|lower)\b", re.I)
HEDGED = re.compile(r"\b(suggests?|may|might|could|indicates?|appears?|preliminary|possibly|likely)\b", re.I)
CLAIM_CUE = re.compile(STRONG.pattern + "|" + MODERATE.pattern + "|" + HEDGED.pattern + r"|\bwe\b", re.I)
ANCHOR = re.compile(r"\b(Fig(?:ure)?\.?\s*\d+[a-z]?|Table\s*\d+|Section\s*\d+(?:\.\d+)*|Eq(?:uation)?\.?\s*\(?\d+\)?|"
                    r"Appendix\s*[A-Z0-9]+|[\w/\-]+\.(?:py|ipynb|R|yaml|json))", re.I)
NUM = re.compile(r"(?<![\w.])(\d+\.\d+|\d+%)")
WEAK_EVIDENCE = re.compile(r"single (run|seed)|one seed|seed \d+\b(?! and)|n\s*=\s*\d\b|n\s*=\s*[1-2]\d\b|"
                           r"no (confidence|error bars?)|single (site|hospital)", re.I)
STRONG_EVIDENCE = re.compile(r"±|\bCI\b|confidence interval|p\s*[<=]\s*0?\.\d+|\d+\s+seeds|std\b|standard deviation", re.I)
SCOPE = re.compile(r"\b(generali[sz]\w*|across (hospitals|datasets|populations|domains)|in general|any|all|universal\w*|robust to)\b", re.I)
HEADER = re.compile(r"^\s*(#+\s*)?((\d+(\.\d+)*)\s+)?(abstract|introduction|methods?|results?|discussion|conclusions?|"
                    r"related work|experiments?|evaluation|limitations)\b.*$", re.I)
FRAMING = re.compile(r"abstract|introduction|discussion|conclusion|body", re.I)
POINTER = re.compile(r"^((?:Table|Fig(?:ure)?\.?)\s*\d+)\s+(reports|shows|lists|summari[sz]es|presents)", re.I)
CAPTION = re.compile(r"^\s*(Fig(?:ure)?\.?|Table)\s*\d+\s*[:.]", re.I)


def norm_anchor(a):
    a = re.sub(r"\s+", " ", a.strip())
    a = re.sub(r"^Fig(?:ure)?\.?\s*", "Figure ", a, flags=re.I)
    return a[0].upper() + a[1:]


def split(text):
    """Return list of (section, sentence) plus captions."""
    out, captions, section = [], {}, "Body"
    for line in text.splitlines():
        if not line.strip():
            continue
        if CAPTION.match(line):
            key = norm_anchor(re.match(r"\s*((?:Fig(?:ure)?\.?|Table)\s*\d+)", line, re.I).group(1))
            captions[key] = line.strip()
            continue
        h = HEADER.match(line)
        if h and len(line.split()) <= 6:
            section = line.strip().lstrip("#").strip()
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line.strip()):
            if s:
                out.append((section, s))
    return out, captions


def certainty(s):
    if STRONG.search(s):
        return "strong"
    if HEDGED.search(s):
        return "hedged"
    return "moderate"


def heuristic(text, events):
    sents, captions = split(text)
    claims = []
    context = {}  # section -> anchor introduced by a pointer sentence ("Table 2 reports ...")
    for i, (section, s) in enumerate(sents):
        pm = POINTER.match(s)
        if pm:
            context[section] = norm_anchor(pm.group(1))
            if not re.search(r"\bthat\b", s) and not STRONG.search(s):
                continue  # descriptive pointer ("Table 2 reports ..."), used as evidence below
        if not CLAIM_CUE.search(s) or len(s.split()) < 6:
            continue
        anchors, seen = [], set()
        refs = [norm_anchor(a) for a in ANCHOR.findall(s)]
        if not refs and section in context and NUM.search(s) and not FRAMING.search(section):
            refs = [context[section]]  # results sentence under "Table 2 reports ..."
        for a in refs:
            if a in seen:
                continue
            seen.add(a)
            found = a in captions or any(a.lower() in t.lower() for j, (_, t) in enumerate(sents) if j != i)
            anchors.append({"kind": "explicit", "ref": a, "found_in_paper": found,
                            "excerpt": captions.get(a, "")})
        nums = NUM.findall(s)
        support_text = []
        # Implicit anchors: framing claims (abstract, intro, discussion) are backed by results
        # sentences that report the same numbers. Never the other way round.
        if FRAMING.search(section):
            for j, (sec2, t) in enumerate(sents):
                if j == i or FRAMING.search(sec2) or t in seen:
                    continue
                if any(n in t for n in nums):
                    seen.add(t)
                    anchors.append({"kind": "paragraph", "ref": sec2, "found_in_paper": True, "excerpt": t})
                    support_text.append(t)
        for a in anchors:
            if a["excerpt"]:
                support_text.append(a["excerpt"])
        # Cross-task: trace numbers back to diary runs.
        diary = []
        for e in events:
            blob = " ".join(str(e.get(k, "")) for k in ("result", "detail", "title"))
            shared = [n for n in nums if n in blob]
            if shared and e["type"] in ("run", "note", "surprise"):
                diary.append({"id": e["id"], "title": e["title"], "result": e.get("result", ""),
                              "provenance": e.get("provenance", "stated")})
                support_text.append(blob)
        caveats = [e for e in events if e["type"] == "note" and any(d["id"] in e.get("links", []) for d in diary)]
        for c in caveats:
            diary.append({"id": c["id"], "title": c["title"], "result": "", "provenance": c.get("provenance", "stated")})
            support_text.append(c.get("detail", "") + " " + c["title"])

        joined = " ".join(support_text)
        cert = certainty(s)
        weak = WEAK_EVIDENCE.search(joined + " " + s)
        strong_ev = STRONG_EVIDENCE.search(joined)
        scope = SCOPE.search(s)
        issues = []
        has_evidence = bool(anchors or diary)
        if not has_evidence:
            status = "unsupported"
            issues.append("No figure, table, paragraph, code path or diary run backs this claim.")
        elif any(a["kind"] == "explicit" and not a["found_in_paper"] for a in anchors):
            status = "unsupported"
            issues.append("Cites %s, which does not appear anywhere else in the paper."
                          % ", ".join(a["ref"] for a in anchors if a["kind"] == "explicit" and not a["found_in_paper"]))
        elif cert == "strong" and (weak or not strong_ev):
            status = "overclaimed"
            issues.append("Wording is strong ('%s') but the evidence %s." % (
                STRONG.search(s).group(0),
                "is weak: '%s'" % weak.group(0) if weak else "reports no uncertainty (no CIs, seeds or tests)"))
        elif weak:
            status = "weak"
            issues.append("Evidence is limited: '%s'." % weak.group(0))
        else:
            status = "supported"
        unseen = [a["ref"] for a in anchors if a["ref"].startswith("Figure")]
        if unseen and status == "supported" and not diary:
            issues.append("Rests on %s, whose contents were not inspected in offline mode: support is unverified."
                          % ", ".join(unseen))
        if scope and status != "unsupported":
            if not any(re.search(r"hospital|site|dataset|population|external", t, re.I) for t in support_text if t != s):
                status = "overclaimed" if status != "unsupported" else status
                issues.append("Scope claim ('%s') with no evidence beyond the data actually used." % scope.group(0))
        if scope and not has_evidence:
            issues.append("Scope claim ('%s') with no evidence beyond the data actually used." % scope.group(0))
        if scope and re.search(r"generali|across|hospital|site|population|external", s, re.I):
            # The researcher's own caveats in the diary can directly contradict a generalisation claim.
            for e in events:
                blob = "%s %s" % (e.get("title", ""), e.get("detail", ""))
                m = re.search(r"(one|single) (hospital|site|dataset)|no external validation", blob, re.I)
                if e["type"] == "note" and m and e["id"] not in [d["id"] for d in diary]:
                    diary.append({"id": e["id"], "title": e["title"], "result": "", "provenance": e.get("provenance", "stated")})
                    status = "overclaimed"
                    issues.append("Contradicted by the diary: %s records '%s'." % (e["id"], m.group(0)))
        claims.append({
            "id": "C%d" % (len(claims) + 1),
            "section": section,
            "text": s,
            "certainty": cert,
            "anchors": anchors,
            "diary_links": diary,
            "status": status,
            "issues": issues,
        })

    figs = sorted({a["ref"] for c in claims for a in c["anchors"] if a["ref"].startswith("Figure")})
    ledger = {
        "checked": [
            "Every claim's explicit references (Figure/Table/Section) exist elsewhere in the paper text",
            "Numbers in claims matched to Results paragraphs and to diary runs",
            "Claim wording strength compared with uncertainty reporting (seeds, CIs, tests)",
            "Scope words (generalizes, across, robust) checked against the data described",
        ],
        "unverified": [
            "Contents of %s not inspected: figures are not read in offline mode" % (", ".join(figs) or "figures"),
            "Table values not parsed from the PDF; only captions and text were seen",
            "Code not executed; statistics not recomputed (statcheck/GRIM would plug in here)",
            "Literature context not checked (claims are judged only against this paper and the diary)",
        ],
    }
    return {"mode": "heuristic", "claims": claims, "ledger": ledger}


SCHEMA = llm.obj({
    "claims": llm.arr(llm.obj({
        "id": llm.STR, "section": llm.STR, "text": llm.STR,
        "certainty": llm.enum("strong", "moderate", "hedged"),
        "anchors": llm.arr(llm.obj({"kind": llm.enum("explicit", "paragraph", "code"), "ref": llm.STR,
                                    "found_in_paper": {"type": "boolean"}, "excerpt": llm.STR})),
        "diary_links": llm.arr(llm.obj({"id": llm.STR, "title": llm.STR, "result": llm.STR,
                                        "provenance": llm.enum("stated", "inferred")})),
        "status": llm.enum("supported", "weak", "overclaimed", "unsupported"),
        "issues": llm.arr(llm.STR),
    })),
    "ledger": llm.obj({"checked": llm.arr(llm.STR), "unverified": llm.arr(llm.STR)}),
})

SYSTEM = """You audit ONE paper: map each major claim to the exact evidence inside the paper, and to the researcher's provenance diary when provided.
- Extract the major empirical claims (abstract, intro, results, discussion). Quote them verbatim in `text`. Ids C1, C2, ...
- anchors: the specific figure, table, paragraph or code path that supports the claim, with a short verbatim excerpt. Mark found_in_paper=false if the cited item does not exist in the text.
- diary_links: diary events (by id) whose results produced or qualify the claim, e.g. a run that produced a number, or a note with a caveat.
- certainty: how strongly the claim is worded. status: supported / weak (evidence limited) / overclaimed (wording stronger than the evidence, or scope beyond the data) / unsupported (no evidence).
- issues: concrete reasons, e.g. "'we demonstrate' backed by one seed and no CIs".
- ledger: what you actually checked versus what you could not verify (figures you could not see, code not run, etc.). Be honest."""


def analyse(text, events, use_ai):
    if use_ai and llm.available():
        compact = [{k: e.get(k) for k in ("id", "type", "title", "detail", "result", "provenance", "links") if e.get(k)}
                   for e in events]
        try:
            out = llm.structured(SYSTEM, "PAPER:\n%s\n\nDIARY:\n%s" % (text, compact), SCHEMA)
            out["mode"] = "ai"
            return out
        except llm.LLMError as e:
            out = heuristic(text, events)
            out["ai_error"] = str(e)
            return out
    return heuristic(text, events)
