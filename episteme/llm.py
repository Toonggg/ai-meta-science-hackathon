"""Provider-agnostic LLM layer. Episteme works fully offline without any of it.

Every feature calls only two functions, `text()` and `structured()`. Behind
them sits one small adapter per provider, all on stdlib HTTP so ./run needs no
pip install:

    anthropic  Claude Messages API (native, with JSON-schema output)
    openai     OpenAI Chat Completions, and any OpenAI-compatible server:
               LM Studio, vLLM, llama.cpp server, OpenRouter, Azure... (set base_url)
    gemini     Google Gemini generateContent
    ollama     local models via Ollama's native /api/chat (JSON-schema `format`)
    none       offline heuristics only

Configuration (first match wins):
  1. Settings saved from the UI     -> .episteme/config.json "llm" section (stays on this machine)
  2. Env: EPISTEME_PROVIDER, EPISTEME_MODEL, EPISTEME_BASE_URL, EPISTEME_API_KEY
  3. Auto-detect: ANTHROPIC_API_KEY -> OPENAI_API_KEY -> GEMINI_API_KEY/GOOGLE_API_KEY
     -> a running Ollama on localhost -> offline heuristics.

To add a provider, write one function `_call_<name>(cfg, system, user, schema)`
that returns the model's text, and register it in ADAPTERS/DEFAULTS.
"""

import json
import os
import re
import threading
import urllib.error
import urllib.request

import config

DEFAULTS = {
    "anthropic": {"model": "claude-opus-5-5", "base_url": "https://api.anthropic.com", "key_env": ["ANTHROPIC_API_KEY"]},
    "openai": {"model": "gpt-5", "base_url": "https://api.openai.com/v1", "key_env": ["OPENAI_API_KEY"]},
    "gemini": {"model": "gemini-2.5-flash", "base_url": "https://generativelanguage.googleapis.com/v1beta",
               "key_env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"]},
    "ollama": {"model": "llama3.1:8b", "base_url": "http://localhost:11434", "key_env": []},
    "none": {"model": "", "base_url": "", "key_env": []},
}
LABELS = {"anthropic": "Anthropic Claude", "openai": "OpenAI / compatible", "gemini": "Google Gemini",
          "ollama": "Local (Ollama)", "none": "Offline heuristics"}
TIMEOUT = float(os.environ.get("EPISTEME_LLM_TIMEOUT", "180"))

_lock = threading.Lock()
_cfg = None


class LLMError(Exception):
    pass


# -- configuration ------------------------------------------------------------

def _env_key(provider):
    for name in DEFAULTS[provider]["key_env"]:
        if os.environ.get(name):
            return os.environ[name]
    return ""


def _ollama_running(base_url):
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=0.4) as r:
            return r.status == 200
    except Exception:
        return False


def _detect():
    if os.environ.get("EPISTEME_OFFLINE") == "1":
        return {"provider": "none"}
    p = os.environ.get("EPISTEME_PROVIDER", "").lower()
    if p in DEFAULTS:
        return {"provider": p}
    for p in ("anthropic", "openai", "gemini"):
        if _env_key(p):
            return {"provider": p}
    if _ollama_running(DEFAULTS["ollama"]["base_url"]):
        return {"provider": "ollama"}
    return {"provider": "none"}


def _resolve(raw):
    p = raw.get("provider", "none")
    if p not in DEFAULTS:
        p = "none"
    d = DEFAULTS[p]
    from_env = os.environ.get("EPISTEME_PROVIDER", "").lower() == p
    return {
        "provider": p,
        "model": raw.get("model") or (from_env and os.environ.get("EPISTEME_MODEL")) or d["model"],
        "base_url": (raw.get("base_url") or (from_env and os.environ.get("EPISTEME_BASE_URL")) or d["base_url"]).rstrip("/"),
        "api_key": raw.get("api_key") or (from_env and os.environ.get("EPISTEME_API_KEY")) or _env_key(p),
    }


def init(state_dir):
    global _cfg
    config.init(state_dir)
    raw = config.section("llm") or None
    if os.environ.get("EPISTEME_OFFLINE") == "1":
        raw = {"provider": "none"}
    _cfg = _resolve(raw or _detect())


def save(settings):
    """Persist settings chosen in the UI. Keys stay local (file mode 600)."""
    global _cfg
    raw = {k: (settings.get(k) or "").strip() for k in ("provider", "model", "base_url", "api_key")}
    if not raw["api_key"] and _cfg and raw["provider"] == _cfg["provider"]:
        raw["api_key"] = _cfg.get("api_key", "")  # blank field = keep existing key
    with _lock:
        config.save_section("llm", {k: v for k, v in raw.items() if v})
        _cfg = _resolve(raw)
    return status()


def status():
    c = _cfg or {"provider": "none", "model": "", "base_url": ""}
    return {
        "provider": c["provider"],
        "label": LABELS[c["provider"]],
        "model": c["model"],
        "base_url": c["base_url"],
        "has_key": bool(c.get("api_key")),
        "available": available(),
        "providers": [{"id": k, "label": LABELS[k], "model": v["model"], "base_url": v["base_url"],
                       "needs_key": bool(v["key_env"]), "env_key_found": bool(_env_key(k))} for k, v in DEFAULTS.items()],
    }


def available():
    c = _cfg
    if not c or c["provider"] == "none":
        return False
    local = c["provider"] == "ollama" or (c["provider"] == "openai" and "api.openai.com" not in c["base_url"])
    return local or bool(c.get("api_key"))


# -- HTTP + adapters ------------------------------------------------------------

def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code in (401, 403):
            raise LLMError("The provider rejected the API key (HTTP %d)" % e.code)
        if e.code == 429:
            raise LLMError("Rate limited by the provider; try again shortly")
        raise LLMError("HTTP %d from provider: %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise LLMError("Could not reach %s (%s)" % (url.split("?")[0], e.reason))
    except TimeoutError:
        raise LLMError("The model took longer than %ds" % TIMEOUT)


def _call_anthropic(c, system, user, schema):
    output_config = {"effort": "medium"}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    body = {"model": c["model"], "max_tokens": 16000, "system": system,
            "messages": [{"role": "user", "content": user}], "output_config": output_config}
    headers = {"x-api-key": c["api_key"], "anthropic-version": "2023-06-01"}
    url = c["base_url"] + "/v1/messages"
    try:  # server-side refusal fallback (beta); retried without it if the account rejects it
        resp = _post(url, {**body, "fallbacks": "default"},
                     {**headers, "anthropic-beta": "server-side-fallback-2026-07-01"})
    except LLMError as e:
        if "HTTP 400" not in str(e):
            raise
        resp = _post(url, body, headers)
    if resp.get("stop_reason") == "refusal":
        raise LLMError("The model declined this request")
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")


def _call_openai(c, system, user, schema):
    body = {"model": c["model"], "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "schema": schema, "strict": True}}
    headers = {"authorization": "Bearer " + c["api_key"]} if c.get("api_key") else {}
    try:
        resp = _post(c["base_url"] + "/chat/completions", body, headers)
    except LLMError as e:
        # Many OpenAI-compatible local servers don't support json_schema; fall back to plain JSON mode.
        if not schema or "HTTP 400" not in str(e):
            raise
        body["response_format"] = {"type": "json_object"}
        resp = _post(c["base_url"] + "/chat/completions", body, headers)
    return resp["choices"][0]["message"].get("content") or ""


def _call_gemini(c, system, user, schema):
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}]}
    if schema:
        body["generationConfig"] = {"responseMimeType": "application/json", "responseJsonSchema": schema}
    resp = _post("%s/models/%s:generateContent" % (c["base_url"], c["model"]), body, {"x-goog-api-key": c["api_key"]})
    try:
        return "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise LLMError("Gemini returned no content")


def _call_ollama(c, system, user, schema):
    body = {"model": c["model"], "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if schema:
        body["format"] = schema
    return _post(c["base_url"] + "/api/chat", body, {}).get("message", {}).get("content", "")


ADAPTERS = {"anthropic": _call_anthropic, "openai": _call_openai, "gemini": _call_gemini, "ollama": _call_ollama}


# -- public API ------------------------------------------------------------------

def text(system, user):
    if not available():
        raise LLMError("No model configured")
    return ADAPTERS[_cfg["provider"]](_cfg, system, user, None)


def structured(system, user, schema):
    """Ask for JSON matching `schema`. Smaller/local models may drift, so the
    reply is parsed leniently and coerced to the schema's shape."""
    if not available():
        raise LLMError("No model configured")
    prompt = user + "\n\nRespond with JSON only, matching this JSON schema:\n" + json.dumps(schema)
    raw = ADAPTERS[_cfg["provider"]](_cfg, system, prompt, schema)
    return coerce(_parse_json(raw), schema)


def _parse_json(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                pass
    raise LLMError("The model did not return valid JSON")


def coerce(value, schema):
    t = schema.get("type")
    if t == "object":
        value = value if isinstance(value, dict) else {}
        return {k: coerce(value.get(k), s) for k, s in schema.get("properties", {}).items()}
    if t == "array":
        return [coerce(v, schema["items"]) for v in value] if isinstance(value, list) else []
    if "enum" in schema:
        return value if value in schema["enum"] else schema["enum"][-1]
    if t == "string":
        return value if isinstance(value, str) else ("" if value is None else str(value))
    return value


# -- schema helpers -----------------------------------------------------------------

def obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


STR = {"type": "string"}


def arr(items):
    return {"type": "array", "items": items}


def enum(*values):
    return {"type": "string", "enum": list(values)}
