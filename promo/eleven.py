#!/usr/bin/env python3
"""Voice the promo with ElevenLabs, one file per scene, spending credits only when told to.

    python3 promo/eleven.py                       # status: per scene, chars, credits, ok/stale/missing (free)
    python3 promo/eleven.py --voices              # list the voices your account can use (free)
    python3 promo/eleven.py --sample "Text" --go  # one short test clip -> promo/build/eleven-sample-*.mp3
    python3 promo/eleven.py --scenes 00-hook --go # (re)voice these scenes if missing or stale
    python3 promo/eleven.py --all --go            # (re)voice every missing or stale scene

Without --go nothing is sent to the TTS endpoint; you only see what it would cost.
Settings live in promo/eleven.json (voice_id, model_id, voice_settings, pronounce). Each
recording gets a sidecar promo/voice/<id>.json with a hash of text + voice + model + settings,
so a scene is "stale" as soon as its narration in scenes.json or the settings change, and only
those scenes are regenerated. Then run `python3 promo/build.py` as usual.

API key: ELEVENLABS_API_KEY in the environment or in the repo's .env. Standard library only.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VOICE_DIR = os.path.join(HERE, "voice")
BUILD = os.path.join(HERE, "build")
API = "https://api.elevenlabs.io"
DEFAULTS = {
    "voice_id": "",
    "model_id": "eleven_multilingual_v2",
    "output_format": "mp3_44100_128",
    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": 1.0},
    "pronounce": {},
}


def load_cfg():
    cfg = dict(DEFAULTS)
    p = os.path.join(HERE, "eleven.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    env = os.path.join(ROOT, ".env")
    if not key and os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            m = re.match(r"\s*(?:export\s+)?ELEVENLABS_API_KEY\s*=\s*['\"]?([^'\"\s]+)", line)
            if m:
                key = m.group(1)
    return key


def call(path, key, body=None):
    req = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit("ElevenLabs %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:500]))


def scenes():
    with open(os.path.join(HERE, "scenes.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    return [(sc["id"], " ".join(b["say"] for b in sc["beats"])) for sc in cfg["scenes"]]


def spoken(text, pronounce):
    for k, v in pronounce.items():
        text = re.sub(r"(?<![\w.])%s(?![\w])" % re.escape(k), v, text)
    return text


def fingerprint(text, cfg):
    blob = json.dumps([text, cfg["voice_id"], cfg["model_id"], cfg["voice_settings"], cfg["output_format"]], sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def state(sid, fp):
    side = os.path.join(VOICE_DIR, sid + ".json")
    if not os.path.exists(os.path.join(VOICE_DIR, sid + ".mp3")):
        return "missing"
    if not os.path.exists(side):
        return "unknown"  # an mp3 not made by this script
    with open(side, encoding="utf-8") as f:
        return "ok" if json.load(f).get("fingerprint") == fp else "STALE"


def rate(model):
    return 0.5 if ("flash" in model or "turbo" in model) else 1.0


def tts(key, cfg, text, prev=None, nxt=None):
    body = {"text": text, "model_id": cfg["model_id"], "voice_settings": cfg["voice_settings"]}
    if "v3" not in cfg["model_id"]:  # request stitching: neighbours give continuous intonation, not billed
        if prev:
            body["previous_text"] = prev
        if nxt:
            body["next_text"] = nxt
    return call("/v1/text-to-speech/%s?output_format=%s" % (cfg["voice_id"], cfg["output_format"]), key, body)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--voices", action="store_true", help="list available voices (free)")
    ap.add_argument("--sample", help="voice this short text as a test clip")
    ap.add_argument("--scenes", help="comma-separated scene ids to voice if missing/stale")
    ap.add_argument("--all", action="store_true", help="voice every missing/stale scene")
    ap.add_argument("--force", action="store_true", help="regenerate even scenes that are ok")
    ap.add_argument("--go", action="store_true", help="actually call the API and spend credits")
    a = ap.parse_args()
    cfg, key = load_cfg(), api_key()

    if a.voices:
        if not key:
            sys.exit("Set ELEVENLABS_API_KEY (env or .env) first.")
        for v in json.loads(call("/v1/voices", key))["voices"]:
            labels = ", ".join("%s" % x for x in (v.get("labels") or {}).values())
            print("%-22s %-28s %-10s %s" % (v["voice_id"], v["name"][:28], v.get("category", ""), labels))
        return

    all_scenes = scenes()
    rows, total = [], 0.0
    for i, (sid, raw) in enumerate(all_scenes):
        text = spoken(raw, cfg["pronounce"])
        fp = fingerprint(text, cfg)
        st = state(sid, fp)
        cost = len(text) * rate(cfg["model_id"])
        rows.append((i, sid, text, fp, st, cost))
    print("model %s, voice %s\n" % (cfg["model_id"], cfg["voice_id"] or "(none set in promo/eleven.json)"))
    for _, sid, text, _, st, cost in rows:
        print("  %-20s %5d chars  ~%5d credits  %s" % (sid, len(text), cost, st))
        if st != "ok":
            total += cost
    print("\n  to voice everything not ok: ~%d credits" % total)
    if key:
        try:
            sub = json.loads(call("/v1/user/subscription", key))
            print("  account: %d of %d credits used this period" % (sub["character_count"], sub["character_limit"]))
        except SystemExit as e:
            print("  (could not read balance: %s)" % e)
    for _, sid, _, _, st, _ in rows:
        if st == "unknown":
            print("  note: voice/%s.mp3 was not made by this script; build.py will use it as is" % sid)
    if any(r[4] == "STALE" for r in rows):
        print("  note: STALE recordings no longer match scenes.json, but build.py still uses them until replaced or removed")

    if not (a.sample or a.scenes or a.all):
        return
    if not cfg["voice_id"]:
        sys.exit("\nSet voice_id in promo/eleven.json first (see --voices).")
    if a.sample:
        text = spoken(a.sample, cfg["pronounce"])
        print("\nsample (as sent): %s" % text)
        print("sample: %d chars, ~%d credits" % (len(text), len(text) * rate(cfg["model_id"])))
        if not a.go:
            return print("dry run: add --go to generate it")
        if not key:
            sys.exit("Set ELEVENLABS_API_KEY (env or .env) first.")
        os.makedirs(BUILD, exist_ok=True)
        out = os.path.join(BUILD, "eleven-sample-%s-%s.mp3" % (cfg["voice_id"][:8], fingerprint(text, cfg)[:6]))
        with open(out, "wb") as f:
            f.write(tts(key, cfg, text))
        return print("wrote", out)

    wanted = {s.strip() for s in a.scenes.split(",")} if a.scenes else {r[1] for r in rows}
    unknown_ids = wanted - {r[1] for r in rows}
    if unknown_ids:
        sys.exit("unknown scene ids: %s" % ", ".join(sorted(unknown_ids)))
    todo = [r for r in rows if r[1] in wanted and (a.force or r[4] != "ok")]
    cost = sum(r[5] for r in todo)
    print("\nwould voice %d scene(s): %s  (~%d credits)" % (len(todo), ", ".join(r[1] for r in todo) or "-", cost))
    if not a.go or not todo:
        return print("dry run: add --go to generate" if todo else "nothing to do")
    if not key:
        sys.exit("Set ELEVENLABS_API_KEY (env or .env) first.")
    os.makedirs(VOICE_DIR, exist_ok=True)
    for i, sid, text, fp, _, _ in todo:
        prev = rows[i - 1][2] if i > 0 else None
        nxt = rows[i + 1][2] if i + 1 < len(rows) else None
        audio = tts(key, cfg, text, prev, nxt)
        with open(os.path.join(VOICE_DIR, sid + ".mp3"), "wb") as f:
            f.write(audio)
        with open(os.path.join(VOICE_DIR, sid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"fingerprint": fp, "text": text, "voice_id": cfg["voice_id"], "model_id": cfg["model_id"],
                       "voice_settings": cfg["voice_settings"]}, f, indent=1)
        print("  voiced", sid)
    print("done. Now run: python3 promo/build.py")


if __name__ == "__main__":
    main()
