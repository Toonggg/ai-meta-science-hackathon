"""Literature, dataset and web search with health tracking and fallback. Stdlib only.

Three groups of sources:

  papers    Semantic Scholar, OpenAlex, Europe PMC, PubMed, Crossref, arXiv
  datasets  Zenodo, DataCite, Hugging Face
  web       Brave, Serper (Google results), Tavily: each needs your own key

Fallback strategy:
  - Free sources (papers, datasets) are queried *in parallel*; results are merged
    and de-duplicated. A source that is down just drops out and the others cover it.
  - Keyed web engines cost credits, so they form a *priority chain*: the first
    healthy one is used, and if it fails the next one is tried.
  - Every failure (timeout, 429, 5xx) puts a source in cooldown (30 s, doubling up
    to 15 min) so we stop hammering it; success resets it.
  - A background poller re-checks every source every 10 minutes with a cheap
    probe, so the UI shows live status before you search.
  - Results are cached in memory for an hour.

Adding a source = one function returning a list of normalised records, plus an
entry in SOURCES.
"""

import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import config

UA = "Episteme/0.1 (AI4MetaScience hackathon research prototype)"
TIMEOUT = 12
POLL_EVERY = 600
CACHE_TTL = 3600
HISTORY = 24

# id: label, group, homepage, env vars for an optional/required key, whether a key is required,
# minimum seconds between calls (politeness limits from each provider's docs).
SOURCES = {
    "semantic_scholar": dict(label="Semantic Scholar", group="papers", home="https://www.semanticscholar.org/product/api",
                             env=["SEMANTIC_SCHOLAR_API_KEY", "S2_API_KEY"], key="optional", interval=1.1,
                             key_hint="Optional. Without a key you share a busy public pool (frequent 429s)."),
    "openalex": dict(label="OpenAlex", group="papers", home="https://openalex.org/settings/api",
                     env=["OPENALEX_API_KEY"], key="optional", interval=0.2,
                     key_hint="Optional, free account. Without a key the daily allowance is 10x smaller."),
    "europe_pmc": dict(label="Europe PMC", group="papers", home="https://europepmc.org/RestfulWebService",
                       env=[], key="none", interval=0.2),
    "pubmed": dict(label="PubMed (NCBI)", group="papers", home="https://www.ncbi.nlm.nih.gov/books/NBK25501/",
                   env=["NCBI_API_KEY"], key="optional", interval=0.5,
                   key_hint="Optional. Raises the limit from 3 to 10 requests/second."),
    "crossref": dict(label="Crossref", group="papers", home="https://api.crossref.org",
                     env=["CROSSREF_MAILTO", "EPISTEME_EMAIL"], key="optional", interval=0.2, key_label="Contact email",
                     key_hint="Optional email for Crossref's faster 'polite pool'."),
    "arxiv": dict(label="arXiv", group="papers", home="https://info.arxiv.org/help/api/", env=[], key="none", interval=3.1),
    "zenodo": dict(label="Zenodo", group="datasets", home="https://developers.zenodo.org", env=[], key="none", interval=0.3),
    "datacite": dict(label="DataCite", group="datasets", home="https://support.datacite.org/docs/api", env=[], key="none",
                     interval=0.2),
    "huggingface": dict(label="Hugging Face", group="datasets", home="https://huggingface.co/docs/hub/api",
                        env=["HF_TOKEN"], key="optional", interval=0.2),
    "brave": dict(label="Brave Search", group="web", home="https://api-dashboard.search.brave.com",
                  env=["BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"], key="required", interval=1.0),
    "serper": dict(label="Serper (Google results)", group="web", home="https://serper.dev",
                   env=["SERPER_API_KEY"], key="required", interval=0.2),
    "tavily": dict(label="Tavily", group="web", home="https://tavily.com", env=["TAVILY_API_KEY"], key="required",
                   interval=0.2),
}
GROUP_LABEL = {"papers": "Papers", "datasets": "Datasets", "web": "Web"}


class SourceError(Exception):
    def __init__(self, msg, retry=True):
        super().__init__(msg)
        self.retry = retry  # False for auth errors: no point cooling down and retrying


# ------------------------------------------------------------------ health
class Health:
    def __init__(self):
        self.lock = threading.Lock()
        self.s = {sid: {"state": "unknown", "error": "", "fails": 0, "down_until": 0.0, "last_ok": 0.0,
                        "last_check": 0.0, "latency": None} for sid in SOURCES}
        self.last_call = {sid: 0.0 for sid in SOURCES}
        self.call_locks = {sid: threading.Lock() for sid in SOURCES}
        self.history = {sid: deque(maxlen=HISTORY) for sid in SOURCES}  # recent checks, oldest first
        self.checking = set()

    def ok(self, sid, latency, via="search"):
        with self.lock:
            h = self.s[sid]
            h.update(state="up", error="", fails=0, down_until=0.0, last_ok=time.time(), last_check=time.time(),
                     latency=round(latency, 2), last_via=via)
            self.history[sid].append({"t": time.time(), "ok": True, "ms": int(latency * 1000), "via": via})

    def fail(self, sid, err, via="search"):
        with self.lock:
            h = self.s[sid]
            h["fails"] += 1
            cooldown = 0 if not getattr(err, "retry", True) else min(30 * 2 ** (h["fails"] - 1), 900)
            h.update(state="down" if cooldown else "error", error=str(err)[:160], last_check=time.time(),
                     down_until=time.time() + cooldown, last_via=via)
            self.history[sid].append({"t": time.time(), "ok": False, "err": str(err)[:80], "via": via})

    def cooling(self, sid):
        with self.lock:
            return self.s[sid]["down_until"] > time.time()

    def view(self, sid):
        with self.lock:
            h = dict(self.s[sid])
        h["retry_in"] = max(0, int(h.pop("down_until") - time.time()))
        h["history"] = list(self.history[sid])
        h["checking"] = sid in self.checking
        return h


HEALTH = Health()
_cache = {}
_cache_lock = threading.Lock()


# ------------------------------------------------------------------ settings
def _settings():
    return config.section("search")


def key_for(sid):
    k = (_settings().get("keys") or {}).get(sid, "")
    if k:
        return k
    for name in SOURCES[sid]["env"]:
        if os.environ.get(name):
            return os.environ[name]
    return ""


def enabled(sid):
    if os.environ.get("EPISTEME_OFFLINE") == "1":
        return False
    meta = SOURCES[sid]
    if meta["key"] == "required" and not key_for(sid):
        return False
    return (_settings().get("enabled") or {}).get(sid, True)


def save(settings):
    cur = _settings()
    keys = dict(cur.get("keys") or {})
    for sid, v in (settings.get("keys") or {}).items():
        if sid in SOURCES and v is not None:
            v = v.strip()
            if v == "-":  # explicit clear
                keys.pop(sid, None)
            elif v:
                keys[sid] = v
    en = {sid: bool(v) for sid, v in (settings.get("enabled") or {}).items() if sid in SOURCES}
    order = [s for s in (settings.get("web_order") or cur.get("web_order") or []) if s in SOURCES]
    config.save_section("search", {"enabled": {**(cur.get("enabled") or {}), **en}, "keys": keys, "web_order": order})
    return status()


def web_order():
    order = _settings().get("web_order") or []
    rest = [s for s, m in SOURCES.items() if m["group"] == "web" and s not in order]
    return [s for s in order if SOURCES.get(s, {}).get("group") == "web"] + rest


def status():
    out = []
    for sid, m in SOURCES.items():
        h = HEALTH.view(sid)
        has_key = bool(key_for(sid))
        if not enabled(sid):
            state = "needs_key" if m["key"] == "required" and not has_key else "off"
        else:
            state = h["state"]
        out.append({"id": sid, "label": m["label"], "group": m["group"], "home": m["home"], "key": m["key"],
                    "key_label": m.get("key_label", "API key"), "key_hint": m.get("key_hint", ""),
                    "has_key": has_key, "enabled": enabled(sid), "state": state, "error": h["error"],
                    "retry_in": h["retry_in"], "latency": h["latency"], "last_via": h.get("last_via", ""),
                    "last_ok": h["last_ok"], "last_check": h["last_check"], "checking": h["checking"],
                    "history": h["history"],
                    "uptime": round(100 * sum(x["ok"] for x in h["history"]) / len(h["history"])) if h["history"] else None,
                    "probe_costs_credit": sid not in PROBES})
    up = sum(1 for s in out if s["enabled"] and s["state"] == "up")
    on = sum(1 for s in out if s["enabled"])
    return {"sources": out, "up": up, "enabled": on, "available": on > 0, "web_order": web_order(),
            "poll_every": POLL_EVERY, "next_poll_in": max(0, int(_next_poll - time.time())) if _next_poll else None,
            "polling": _poller_running, "now": time.time()}


# ------------------------------------------------------------------ HTTP
def _http(sid, url, body=None, headers=None, as_text=False):
    """Polite request: respects the source's minimum interval, maps errors."""
    with HEALTH.call_locks[sid]:
        wait = SOURCES[sid]["interval"] - (time.time() - HEALTH.last_call[sid])
        if wait > 0:
            time.sleep(wait)
        HEALTH.last_call[sid] = time.time()
    h = {"user-agent": UA, "accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SourceError("rejected the API key (HTTP %d)" % e.code, retry=False)
        if e.code == 429:
            raise SourceError("rate-limited (HTTP 429)")
        raise SourceError("HTTP %d" % e.code)
    except urllib.error.URLError as e:
        raise SourceError("unreachable (%s)" % getattr(e, "reason", e))
    except (TimeoutError, OSError) as e:
        raise SourceError("timed out" if isinstance(e, TimeoutError) else str(e))
    if as_text:
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        raise SourceError("returned invalid JSON")


def q(s):
    return urllib.parse.quote(s, safe="")


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def rec(source, title, **kw):
    r = {"source": source, "title": strip_tags(title), "authors": "", "year": None, "venue": "", "abstract": "",
         "url": "", "doi": "", "citations": None, "kind": "article"}
    r.update({k: v for k, v in kw.items() if v not in (None, "")})
    if r["doi"]:
        r["doi"] = re.sub(r"^https?://(dx\.)?doi\.org/", "", r["doi"]).lower()
        r["url"] = r["url"] or "https://doi.org/" + r["doi"]
    r["abstract"] = strip_tags(r["abstract"])[:1500]
    return r


REVIEW_RE = re.compile(r"systematic review|meta-analy|scoping review|umbrella review|review of reviews|meta-review", re.I)


def classify(title, types=""):
    t = (title or "") + " " + (types or "")
    if REVIEW_RE.search(t):
        return "systematic_review"
    if re.search(r"\breview\b", t, re.I):
        return "review"
    return None


# ------------------------------------------------------------------ paper sources
def s2(query, n):
    key = key_for("semantic_scholar")
    d = _http("semantic_scholar", "https://api.semanticscholar.org/graph/v1/paper/search?query=%s&limit=%d&fields="
              "title,abstract,year,venue,citationCount,externalIds,url,publicationTypes,authors" % (q(query), n),
              headers={"x-api-key": key} if key else None)
    out = []
    for p in d.get("data") or []:
        types = " ".join(p.get("publicationTypes") or []).replace("MetaAnalysis", "meta-analysis")
        out.append(rec("semantic_scholar", p.get("title"), year=p.get("year"), venue=p.get("venue"),
                       abstract=p.get("abstract"), url=p.get("url"), doi=(p.get("externalIds") or {}).get("DOI"),
                       citations=p.get("citationCount"), kind=classify(p.get("title"), types) or "article",
                       authors=", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])))
    return out


def openalex(query, n):
    key = key_for("openalex")
    url = "https://api.openalex.org/works?search=%s&per_page=%d" % (q(query), n) + ("&api_key=" + q(key) if key else "")
    d = _http("openalex", url)
    out = []
    for w in d.get("results") or []:
        inv = w.get("abstract_inverted_index") or {}
        pos = sorted((i, word) for word, idx in inv.items() for i in idx)
        src = ((w.get("primary_location") or {}).get("source") or {})
        out.append(rec("openalex", w.get("title") or w.get("display_name"), year=w.get("publication_year"),
                       venue=src.get("display_name"), abstract=" ".join(word for _, word in pos), doi=w.get("doi"),
                       url=w.get("doi") or w.get("id"), citations=w.get("cited_by_count"),
                       kind=classify(w.get("title"), w.get("type") if w.get("type") == "review" else "") or "article",
                       authors=", ".join(((a.get("author") or {}).get("display_name") or "")
                                         for a in (w.get("authorships") or [])[:3])))
    return out


def europe_pmc(query, n):
    d = _http("europe_pmc", "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%s&format=json&pageSize=%d"
              "&resultType=core" % (q(query), n))
    out = []
    for p in (d.get("resultList") or {}).get("result") or []:
        types = " ".join(((p.get("pubTypeList") or {}).get("pubType")) or [])
        url = "https://europepmc.org/article/%s/%s" % (p.get("source", "MED"), p.get("id", ""))
        out.append(rec("europe_pmc", p.get("title"), year=p.get("pubYear"), venue=p.get("journalTitle"),
                       abstract=p.get("abstractText"), doi=p.get("doi"), url=url, citations=p.get("citedByCount"),
                       kind=classify(p.get("title"), types) or "article", authors=p.get("authorString", "")[:120]))
    return out


def pubmed(query, n):
    key = key_for("pubmed")
    k = ("&api_key=" + q(key)) if key else ""
    ids = _http("pubmed", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json"
                "&sort=relevance&retmax=%d&term=%s%s" % (n, q(query), k)).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    d = _http("pubmed", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=%s%s"
              % (",".join(ids), k)).get("result", {})
    out = []
    for pid in ids:
        p = d.get(pid) or {}
        doi = next((a["value"] for a in p.get("articleids", []) if a.get("idtype") == "doi"), "")
        year = (re.match(r"\d{4}", p.get("pubdate", "")) or [None])[0]
        out.append(rec("pubmed", p.get("title"), year=int(year) if year else None, venue=p.get("fulljournalname"),
                       doi=doi, url="https://pubmed.ncbi.nlm.nih.gov/%s/" % pid,
                       kind=classify(p.get("title"), " ".join(p.get("pubtype", []))) or "article",
                       authors=", ".join(a.get("name", "") for a in p.get("authors", [])[:3])))
    return out


def crossref(query, n):
    mail = key_for("crossref")
    d = _http("crossref", "https://api.crossref.org/works?query=%s&rows=%d&select=DOI,title,author,issued,"
              "container-title,abstract,is-referenced-by-count,type%s" % (q(query), n, ("&mailto=" + q(mail)) if mail else ""))
    out = []
    for w in (d.get("message") or {}).get("items") or []:
        year = (((w.get("issued") or {}).get("date-parts") or [[None]])[0] or [None])[0]
        title = (w.get("title") or [""])[0]
        out.append(rec("crossref", title, year=year, venue=(w.get("container-title") or [""])[0], doi=w.get("DOI"),
                       abstract=w.get("abstract"), citations=w.get("is-referenced-by-count"),
                       kind=classify(title) or "article",
                       authors=", ".join(("%s %s" % (a.get("given", ""), a.get("family", ""))).strip()
                                         for a in (w.get("author") or [])[:3])))
    return out


def arxiv(query, n):
    words = [w for w in re.findall(r"[\w-]+", query) if len(w) > 2][:6]
    sq = " AND ".join("all:" + w for w in words) or "all:" + query
    raw = _http("arxiv", "https://export.arxiv.org/api/query?search_query=%s&max_results=%d&sortBy=relevance"
                % (q(sq), n), as_text=True)
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise SourceError("returned invalid XML")
    out = []
    for e in root.findall("a:entry", ns):
        title = e.findtext("a:title", "", ns)
        doi = e.findtext("x:doi", "", ns)
        out.append(rec("arxiv", title, year=int(e.findtext("a:published", "0000", ns)[:4]) or None, venue="arXiv",
                       abstract=e.findtext("a:summary", "", ns), url=e.findtext("a:id", "", ns), doi=doi,
                       kind=classify(title) or "preprint",
                       authors=", ".join(a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)[:3])))
    return out


# ------------------------------------------------------------------ dataset sources
def zenodo(query, n):
    d = _http("zenodo", "https://zenodo.org/api/records?q=%s&type=dataset&size=%d&sort=bestmatch" % (q(query), n))
    out = []
    for h in (d.get("hits") or {}).get("hits") or []:
        m = h.get("metadata") or {}
        out.append(rec("zenodo", m.get("title") or h.get("title"), year=(m.get("publication_date") or "")[:4] or None,
                       venue="Zenodo", abstract=m.get("description"), doi=h.get("doi"),
                       url=(h.get("links") or {}).get("self_html"), kind="dataset",
                       authors=", ".join(c.get("name", "") for c in (m.get("creators") or [])[:3])))
    return out


def datacite(query, n):
    d = _http("datacite", "https://api.datacite.org/dois?query=%s&resource-type-id=dataset&page%%5Bsize%%5D=%d"
              % (q(query), n))
    out = []
    for item in d.get("data") or []:
        a = item.get("attributes") or {}
        desc = next((x.get("description", "") for x in a.get("descriptions") or [] if x.get("description")), "")
        out.append(rec("datacite", (a.get("titles") or [{}])[0].get("title", ""), year=a.get("publicationYear"),
                       venue=a.get("publisher") if isinstance(a.get("publisher"), str) else (a.get("publisher") or {}).get("name"),
                       abstract=desc, doi=a.get("doi"), url=a.get("url"), kind="dataset"))
    return out


def huggingface(query, n):
    words = [w for w in re.findall(r"[A-Za-z][\w-]+", query) if len(w) > 3]
    term = max(words, key=len) if words else query  # HF matches dataset names, so use one strong keyword
    tok = key_for("huggingface")
    d = _http("huggingface", "https://huggingface.co/api/datasets?search=%s&limit=%d&sort=downloads" % (q(term), n),
              headers={"authorization": "Bearer " + tok} if tok else None)
    return [rec("huggingface", x.get("id"), venue="Hugging Face", url="https://huggingface.co/datasets/" + x.get("id", ""),
                year=(x.get("lastModified") or "")[:4] or None, citations=x.get("downloads"), kind="dataset")
            for x in d if isinstance(x, dict)]


# ------------------------------------------------------------------ web sources (keyed)
def brave(query, n):
    d = _http("brave", "https://api.search.brave.com/res/v1/web/search?q=%s&count=%d" % (q(query), n),
              headers={"x-subscription-token": key_for("brave")})
    return [rec("brave", r.get("title"), url=r.get("url"), abstract=r.get("description"), kind="web")
            for r in (d.get("web") or {}).get("results") or []]


def serper(query, n):
    d = _http("serper", "https://google.serper.dev/search", body={"q": query, "num": n},
              headers={"x-api-key": key_for("serper")})
    return [rec("serper", r.get("title"), url=r.get("link"), abstract=r.get("snippet"), kind="web")
            for r in d.get("organic") or []]


def tavily(query, n):
    d = _http("tavily", "https://api.tavily.com/search", body={"query": query, "max_results": n},
              headers={"authorization": "Bearer " + key_for("tavily")})
    return [rec("tavily", r.get("title"), url=r.get("url"), abstract=r.get("content"), kind="web")
            for r in d.get("results") or []]


ADAPTERS = {"semantic_scholar": s2, "openalex": openalex, "europe_pmc": europe_pmc, "pubmed": pubmed,
            "crossref": crossref, "arxiv": arxiv, "zenodo": zenodo, "datacite": datacite,
            "huggingface": huggingface, "brave": brave, "serper": serper, "tavily": tavily}

# Cheap probes for the poller (single-record lookups where possible; never the paid web engines).
PROBES = {
    "semantic_scholar": lambda: _http("semantic_scholar", "https://api.semanticscholar.org/graph/v1/paper/"
                                      "ARXIV:1706.03762?fields=title",
                                      headers={"x-api-key": key_for("semantic_scholar")} if key_for("semantic_scholar") else None),
    "openalex": lambda: _http("openalex", "https://api.openalex.org/works/W2741809807"),
    "europe_pmc": lambda: _http("europe_pmc", "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=cancer"
                                "&format=json&pageSize=1"),
    "pubmed": lambda: _http("pubmed", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=pubmed&retmode=json"),
    "crossref": lambda: _http("crossref", "https://api.crossref.org/works/10.1038/nature14539"),
    "arxiv": lambda: _http("arxiv", "https://export.arxiv.org/api/query?id_list=1706.03762", as_text=True),
    "zenodo": lambda: _http("zenodo", "https://zenodo.org/api/records?size=1"),
    "datacite": lambda: _http("datacite", "https://api.datacite.org/heartbeat", as_text=True),
    "huggingface": lambda: _http("huggingface", "https://huggingface.co/api/datasets?limit=1"),
}


# ------------------------------------------------------------------ running searches
def _run_one(sid, query, n):
    key = (sid, query, n)
    with _cache_lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1], True
    t0 = time.time()
    try:
        try:
            res = ADAPTERS[sid](query, n)
        except SourceError as e:
            if "429" not in str(e):
                raise
            time.sleep(2.0)  # one polite retry on rate limiting, then give up and let other sources cover
            res = ADAPTERS[sid](query, n)
    except SourceError as e:
        HEALTH.fail(sid, e)
        raise
    except Exception as e:  # unexpected payload shape etc.
        err = SourceError("unexpected response (%s)" % type(e).__name__)
        HEALTH.fail(sid, err)
        raise err
    HEALTH.ok(sid, time.time() - t0)
    with _cache_lock:
        _cache[key] = (time.time(), res)
    return res, False


def search_group(group, queries, n=12):
    """Query every healthy source of a group (web: first healthy in priority order).

    Returns (records, report). The report lists, per source, whether it answered,
    was skipped (off / cooling down) or failed, and why.
    """
    if isinstance(queries, str):
        queries = [queries]
    sids = [s for s, m in SOURCES.items() if m["group"] == group]
    if group == "web":
        sids = web_order()
    report, records = [], []

    def entry(sid, state, count=0, error="", cached=False):
        report.append({"id": sid, "label": SOURCES[sid]["label"], "state": state, "count": count, "error": error,
                       "cached": cached})

    if group == "web":  # priority chain: stop at the first engine that answers
        for sid in sids:
            if not enabled(sid):
                continue
            if HEALTH.cooling(sid):
                entry(sid, "skipped", error="cooling down after: " + HEALTH.view(sid)["error"])
                continue
            try:
                got = []
                for qq in queries:
                    r, cached = _run_one(sid, qq, n)
                    got += r
                records += got
                entry(sid, "ok", len(got), cached=cached)
                break
            except SourceError as e:
                entry(sid, "failed", error=str(e))
        return dedupe(records), report

    active = []
    for sid in sids:
        if not enabled(sid):
            entry(sid, "off")
        elif HEALTH.cooling(sid):
            entry(sid, "skipped", error="cooling down after: " + HEALTH.view(sid)["error"])
        else:
            active.append(sid)
    per = {sid: {"count": 0, "errors": [], "cached": True} for sid in active}

    def worker(sid):  # sources in parallel; one source's queries in sequence (public pools allow ~1 at a time)
        got = []
        for qq in queries:
            if HEALTH.cooling(sid) and per[sid]["errors"]:
                break  # it just failed; don't keep hitting it
            try:
                r, cached = _run_one(sid, qq, n)
                got += r
                per[sid]["count"] += len(r)
                per[sid]["cached"] &= cached
            except SourceError as e:
                per[sid]["errors"].append(str(e))
        return got

    with ThreadPoolExecutor(max_workers=max(1, len(active))) as pool:
        for got in pool.map(worker, active):
            records += got
    for sid in active:
        p = per[sid]
        if p["errors"] and not p["count"]:
            entry(sid, "failed", error=p["errors"][0])
        else:
            entry(sid, "ok", p["count"], error=p["errors"][0] if p["errors"] else "", cached=p["cached"] and not p["errors"])
    order = {s: i for i, s in enumerate(sids)}
    report.sort(key=lambda r: order[r["id"]])
    return dedupe(records), report


def _norm_title(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())[:90]


def dedupe(records):
    """Merge the same work found by several sources; keep the richest fields."""
    merged, index = [], {}
    for r in records:
        keys = [k for k in (r["doi"] and "doi:" + r["doi"], "t:" + _norm_title(r["title"])) if k and len(k) > 6]
        hit = next((index[k] for k in keys if k in index), None)
        if hit is None:
            r = dict(r, found_in=[r["source"]])
            merged.append(r)
            for k in keys:
                index[k] = r
            continue
        if r["source"] not in hit["found_in"]:
            hit["found_in"].append(r["source"])
        for f in ("abstract", "venue", "authors", "doi", "year"):
            if not hit.get(f) and r.get(f):
                hit[f] = r[f]
        if (r.get("citations") or 0) > (hit.get("citations") or 0):
            hit["citations"] = r["citations"]
        if r["kind"] in ("systematic_review", "review") and hit["kind"] not in ("systematic_review",):
            hit["kind"] = r["kind"]
        for k in keys:
            index.setdefault(k, hit)
    return merged


def rank(records, terms):
    """Relevance = query-term coverage in title/abstract, plus a little citation weight."""
    terms = [t.lower() for t in terms if t]
    for r in records:
        title, text = r["title"].lower(), (r["title"] + " " + r.get("abstract", "")).lower()
        cover = sum(1 for t in terms if t in text) / max(1, len(terms))
        in_title = sum(1 for t in terms if t in title) / max(1, len(terms))
        r["coverage"] = round(cover, 2)
        r["score"] = round(cover * 3 + in_title + math.log10((r.get("citations") or 0) + 1) * 0.4 +
                           (0.5 if r["kind"] == "systematic_review" else 0) + 0.15 * (len(r["found_in"]) - 1), 3)
    return sorted(records, key=lambda r: -r["score"])


# ------------------------------------------------------------------ poller
_next_poll = 0.0
_poller_running = False
_wake = threading.Event()


def check_one(sid, via="manual", include_web=False):
    """Probe one source now, regardless of cooldown. Web engines are only probed
    when explicitly asked (include_web), because each probe spends a query credit."""
    if sid not in SOURCES:
        raise KeyError(sid)
    if not enabled(sid):
        return
    if sid not in PROBES and not include_web:
        return
    with HEALTH.lock:
        HEALTH.checking.add(sid)
    t0 = time.time()
    try:
        if sid in PROBES:
            PROBES[sid]()
        else:
            ADAPTERS[sid]("research", 1)
        HEALTH.ok(sid, time.time() - t0, via)
    except SourceError as e:
        HEALTH.fail(sid, e, via)
    except Exception as e:
        HEALTH.fail(sid, SourceError(type(e).__name__), via)
    finally:
        with HEALTH.lock:
            HEALTH.checking.discard(sid)


def check_all(include_web=False, via="manual"):
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        list(pool.map(lambda sid: check_one(sid, via, include_web), SOURCES))
    return status()


def start_poller():
    global _poller_running

    def loop():
        global _next_poll
        while True:
            try:
                check_all(via="poll")
            except Exception:
                pass
            _next_poll = time.time() + POLL_EVERY
            _wake.wait(POLL_EVERY)
            _wake.clear()

    if os.environ.get("EPISTEME_OFFLINE") != "1":
        _poller_running = True
        threading.Thread(target=loop, daemon=True, name="source-poller").start()


def poll_now():
    """Ask the background poller to run a full check right away (non-blocking)."""
    _wake.set()
