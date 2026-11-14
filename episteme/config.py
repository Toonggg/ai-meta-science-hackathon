"""Shared local settings file: .episteme/config.json (mode 600, gitignored).

    {"llm": {"provider": ..., "model": ..., "base_url": ..., "api_key": ...},
     "search": {"enabled": {"arxiv": true, ...}, "keys": {"brave": "...", ...}}}
"""

import json
import os
import threading

_lock = threading.Lock()
_path = None


def _load_dotenv(env_path):
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except OSError:
        pass


def init(state_dir):
    global _path
    _path = os.path.join(state_dir, "config.json")
    root_env = os.path.join(os.path.dirname(state_dir), ".env")
    _load_dotenv(root_env)


def load():
    if not _path or not os.path.exists(_path):
        return {}
    try:
        with open(_path, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError:
        return {}
    if "provider" in data and "llm" not in data:  # pre-sections format
        data = {"llm": data}
    return data


def section(name):
    return load().get(name) or {}


def save_section(name, value):
    with _lock:
        data = load()
        data[name] = value
        fd = os.open(_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
