"""Exports: raw JSON, W3C PROV-JSON, and a Markdown decision appendix."""

import json
import re

from diary import who

TYPE_LABEL = {"plan": "Plan", "run": "Run", "surprise": "Surprise", "pivot": "Pivot", "note": "Note",
              "artifact": "Artifact", "question": "Question"}
AGENT_FOR_SOURCE = {"chat": "ep:ai_assistant", "agent": "ep:ai_assistant", "episteme": "ep:episteme"}
AGENT_FOR_ACTOR = {"human": "ep:researcher", "agent": "ep:ai_assistant", "system": "ep:episteme"}


def _agent_of(e):
    return AGENT_FOR_ACTOR.get(e.get("actor")) or AGENT_FOR_SOURCE.get(e.get("source"), "ep:researcher")


def to_json(snapshot):
    return json.dumps(snapshot, indent=2, ensure_ascii=False)


def to_prov(snapshot):
    events = snapshot["events"]
    doc = {
        "prefix": {"ep": "https://episteme.local/ns#", "prov": "http://www.w3.org/ns/prov#"},
        "agent": {
            "ep:researcher": {"prov:type": "prov:Person"},
            "ep:ai_assistant": {"prov:type": "prov:SoftwareAgent"},
            "ep:episteme": {"prov:type": "prov:SoftwareAgent", "prov:label": "Episteme (auto-detected events)"},
        },
        "entity": {}, "activity": {}, "used": {}, "wasGeneratedBy": {}, "wasAssociatedWith": {},
        "wasDerivedFrom": {}, "wasInformedBy": {}, "wasAttributedTo": {},
    }
    n = 0

    def rel(kind, body):
        nonlocal n
        n += 1
        doc[kind]["_:r%d" % n] = body

    for e in events:
        eid = "ep:" + e["id"]
        attrs = {"prov:label": e["title"], "ep:type": e["type"], "ep:provenance": e.get("provenance"),
                 "ep:source": e.get("source"), "ep:step": e.get("step")}
        for k in ("detail", "expectation", "result", "status", "code"):
            if e.get(k):
                attrs["ep:" + k] = e[k]
        attrs["ep:statedBy"] = who(e)
        for k, label in (("actor", "ep:actor"), ("confirmation", "ep:confirmation"), ("quote", "ep:quote"),
                         ("model_summary", "ep:modelSummary"),
                         ("proposed_reason", "ep:proposedReason"), ("episode_id", "ep:episode")):
            if e.get(k):
                attrs[label] = e[k]
        if e.get("raw_ids"):
            attrs["ep:rawEvidence"] = " ".join(e["raw_ids"])
        if e.get("classified_by"):
            mid = "ep:model_" + re.sub(r"[^A-Za-z0-9]+", "_", e["classified_by"].get("model", "unknown")).strip("_")
            doc["agent"].setdefault(mid, {"prov:type": "prov:SoftwareAgent", "prov:label": e["classified_by"].get("model")})
            rel("wasAttributedTo", {"prov:entity": eid, "prov:agent": mid, "prov:role": "ep:classifier",
                                    "ep:time": e["classified_by"].get("at")})
        if e.get("confirmation") in ("confirmed", "edited"):
            rel("wasAttributedTo", {"prov:entity": eid, "prov:agent": "ep:researcher", "prov:role": "ep:confirmer",
                                    "ep:time": e.get("confirmed_at")})
        if e.get("params"):
            attrs["ep:params"] = json.dumps(e["params"])
        if e["type"] == "run":
            attrs.update({"prov:startTime": e["ts"]})
            doc["activity"][eid] = attrs
            if e.get("data"):
                did = "ep:data_" + e["data"].get("hash", e["data"].get("name", "dataset")).replace(":", "_")[:40]
                doc["entity"][did] = {"prov:type": "ep:Dataset", "prov:label": e["data"].get("name"),
                                      "ep:version": e["data"].get("version"), "ep:hash": e["data"].get("hash")}
                rel("used", {"prov:activity": eid, "prov:entity": did})
            if e.get("result"):
                rid = eid + "_result"
                doc["entity"][rid] = {"prov:type": "ep:Result", "prov:value": e["result"]}
                rel("wasGeneratedBy", {"prov:entity": rid, "prov:activity": eid})
            rel("wasAssociatedWith", {"prov:activity": eid, "prov:agent": _agent_of(e)})
        else:
            attrs["prov:generatedAtTime"] = e["ts"]
            if e["type"] in ("plan", "pivot"):
                attrs["prov:type"] = "prov:Plan"
            doc["entity"][eid] = attrs
            rel("wasAttributedTo", {"prov:entity": eid, "prov:agent": _agent_of(e), "prov:role": "ep:author"})
        for link in e.get("links", []):
            target = next((x for x in events if x["id"] == link), None)
            if not target:
                continue
            if e["type"] == "run" and target["type"] == "run":
                rel("wasInformedBy", {"prov:informed": eid, "prov:informant": "ep:" + link})
            elif e["type"] == "run":
                rel("used", {"prov:activity": eid, "prov:entity": "ep:" + link})
            else:
                rel("wasDerivedFrom", {"prov:generatedEntity": eid, "prov:usedEntity": "ep:" + link})
    return json.dumps({k: v for k, v in doc.items() if v}, indent=2, ensure_ascii=False)


def to_markdown(snapshot):
    lines = ["# Decision appendix: %s" % snapshot.get("project", "Untitled project"), "",
             "Generated by Episteme from the project's provenance diary. Each entry says who stated it: "
             "the researcher, the AI agent (and whether the researcher confirmed it), or Episteme's own "
             "rules (*inferred*, reconstructed rather than recorded at the time).", ""]
    for e in snapshot["events"]:
        lines.append("### [Step %d] %s: %s" % (e["step"], TYPE_LABEL.get(e["type"], e["type"]), e["title"]))
        lines.append("- **Event:** %s · %s · source: %s" % (e["id"], e["ts"], e.get("source")))
        lines.append("- **Stated by:** " + who(e))
        for label, key in (("Expectation", "expectation"), ("Detail / reason", "detail"),
                           ("Quoted from the log", "quote"), ("Model's summary", "model_summary"),
                           ("Originally proposed reason", "proposed_reason"), ("Result", "result"), ("Status", "status")):
            if key == "quote" and e.get("quote") == e.get("detail"):
                continue  # the reason already is the verbatim quote
            if e.get(key):
                lines.append("- **%s:** %s" % (label, e[key]))
        if e.get("classified_by"):
            c = e["classified_by"]
            lines.append("- **Classified by:** %s at %s" % (c.get("model"), c.get("at")))
        if e.get("raw_ids"):
            lines.append("- **Raw evidence:** " + ", ".join(e["raw_ids"]))
        if e.get("params"):
            lines.append("- **Parameters:** " + ", ".join("%s=%s" % kv for kv in e["params"].items()))
        if e.get("data"):
            d = e["data"]
            lines.append("- **Data:** %s v%s (%s)" % (d.get("name"), d.get("version"), d.get("hash")))
        if e.get("links"):
            lines.append("- **Linked to:** " + ", ".join(e["links"]))
        if e.get("code"):
            lang = "bash" if e.get("source") == "agent" else "python"  # captured runs store the shell command
            lines += ["", "```" + lang, e["code"], "```"]
        lines.append("")
    return "\n".join(lines)
