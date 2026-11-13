"""Strip secrets from captured text before it is stored or sent to a model.

Used by the capture hooks (before anything reaches raw.jsonl) and again by the
stitcher (before anything leaves the machine). Pattern-based, so it is a safety
net, not a guarantee: the README says so.

Must stay Python 3.8 compatible: capture hooks run under whatever `python3` the
researcher's shell has.
"""

import os
import re

MASK = "[REDACTED]"

PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{16,}"),          # Anthropic / OpenAI style
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),         # GitHub tokens
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),                    # Slack
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                # AWS access key id
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),                           # Google API key
    re.compile(r"\bhf_[A-Za-z0-9]{20,}"),                               # Hugging Face
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-~+/]{16,}=*"),
]
# key=value / key: value / --api-key value, for names that look secret.
ASSIGN = re.compile(r"(?i)(\b[\w\-]*(?:api[_\-]?key|apikey|token|secret|passw(?:or)?d|pwd|credential)s?[\w\-]*"
                    r"[\"']?\s*(?:[=:]|\s)\s*[\"']?)([^\s\"',;]{6,})")
URL_CREDS = re.compile(r"(\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:)([^\s@/]+)(@)", re.I)

SECRET_ENV = re.compile(r"(?i)(key|token|secret|passw|pwd|credential)")


def _env_secrets():
    vals = []
    for name, val in os.environ.items():
        if SECRET_ENV.search(name) and val and len(val) >= 8:
            vals.append(val)
    return sorted(vals, key=len, reverse=True)


def redact(text, env=True):
    if not text:
        return text
    if not isinstance(text, str):
        text = str(text)
    if env:
        for val in _env_secrets():
            text = text.replace(val, MASK)
    for p in PATTERNS:
        if p.groups:
            text = p.sub(lambda m: m.group(1) + " " + MASK, text)
        else:
            text = p.sub(MASK, text)
    text = URL_CREDS.sub(lambda m: m.group(1) + MASK + m.group(3), text)
    text = ASSIGN.sub(lambda m: m.group(1) + MASK, text)
    return text


def redact_obj(obj, env=True):
    """Redact every string inside a JSON-like structure."""
    if isinstance(obj, str):
        return redact(obj, env)
    if isinstance(obj, list):
        return [redact_obj(v, env) for v in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v, env) for k, v in obj.items()}
    return obj
