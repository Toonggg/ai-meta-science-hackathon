#!/usr/bin/env python3
"""Quick script to test the Berget AI API key and list available models.

Uses stdlib urllib only (no pip dependencies).
Reads key and base URL from .env or environment.
"""

import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Simple .env loader
def load_env(env_path):
    if not os.path.isfile(env_path):
        return
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

load_env(os.path.join(ROOT, ".env"))

API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("EPISTEME_API_KEY")
BASE_URL = (os.environ.get("EPISTEME_BASE_URL") or "https://api.berget.ai/v1").rstrip("/")
MODEL = os.environ.get("EPISTEME_MODEL") or "glm-5.3-flash"

if not API_KEY:
    sys.exit("Error: No API key found in .env or environment.")

print(f"Testing Berget AI connection...")
print(f"Base URL: {BASE_URL}")
print(f"Key:      {API_KEY[:8]}...{API_KEY[-4:]}")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Test /models endpoint
print("\n1. Fetching available models from /v1/models...")
models_req = urllib.request.Request(f"{BASE_URL}/models", headers=headers)
available_models = []
try:
    with urllib.request.urlopen(models_req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        models = data.get("data", [])
        print(f"✓ Found {len(models)} model(s):")
        for m in models:
            m_id = m.get("id")
            available_models.append(m_id)
            print(f"   - {m_id}")
except urllib.error.HTTPError as e:
    print(f"⚠ Could not list models (HTTP {e.code}): {e.read().decode(errors='replace')[:200]}")
except Exception as e:
    print(f"⚠ /models request failed: {e}")

# Determine model to test
target_model = MODEL
if available_models and target_model not in available_models:
    target_model = available_models[0]
    print(f"\nTarget model '{MODEL}' not in listed models; defaulting to '{target_model}'")

# 2. Test chat completions
print(f"\n2. Testing chat completion with model: {target_model}...")
chat_payload = {
    "model": target_model,
    "messages": [
        {"role": "system", "content": "You are a concise scientific assistant."},
        {"role": "user", "content": "Respond with: 'Berget AI is connected!' followed by 1 sentence on protein folding."}
    ],
    "max_tokens": 100,
    "temperature": 0.2
}

chat_req = urllib.request.Request(
    f"{BASE_URL}/chat/completions",
    data=json.dumps(chat_payload).encode("utf-8"),
    headers=headers
)

try:
    with urllib.request.urlopen(chat_req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        reply = result["choices"][0]["message"]["content"].strip()
        print("✓ Response received successfully:")
        print(f"   \"{reply}\"")
        print("\nSUCCESS: Berget AI key is valid and working!")
except urllib.error.HTTPError as e:
    print(f"✗ Chat completion failed with HTTP {e.code}:")
    print(e.read().decode(errors="replace")[:300])
    sys.exit(1)
except Exception as e:
    print(f"✗ Chat completion failed: {e}")
    sys.exit(1)
