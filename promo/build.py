#!/usr/bin/env python3
"""Build the Episteme promo video from promo/scenes.json.

    python3 promo/build.py                 # everything: voice, slides, subtitles, videos
    python3 promo/build.py --script-only   # only regenerate SCRIPT.md and voice-text/

Needs: ffmpeg/ffprobe, Google Chrome (renders the slides), and macOS `say` for the
placeholder voice. Python standard library only.

Replacing the voice (e.g. with ElevenLabs): record one audio file per scene, named after the
scene id, and put it in promo/voice/ (01-hook.mp3, 02-problem.mp3, ...; mp3, wav, m4a or aiff).
The text for each file is in promo/voice-text/<id>.txt. Run the build again: every scene with a
recording uses it, the slides and subtitles are re-timed to it, and scenes without one keep the
`say` voice. Within a scene, slide changes and subtitles are spread over the recording in
proportion to the length of each sentence.

Outputs (promo/out/):
    episteme-promo.mp4        voice + subtitles burned in
    episteme-promo-clean.mp4  voice, no burned-in subtitles (subtitle track you can switch on)
    episteme-promo.srt        the subtitles
    voiceover.wav             the voice track on its own
"""

import argparse
import concurrent.futures
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "out")
VOICE_DIR = os.path.join(HERE, "voice")
TEXT_DIR = os.path.join(HERE, "voice-text")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
W, H, FPS, RATE = 1920, 1080, 30, 44100
SHOT_W, SHOT_H = 1272, 810  # size of the screenshots in assets/
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aiff", ".aif", ".flac")


# ------------------------------------------------------------------ text
def chunks_of(text, max_words=12):
    """Split narration into subtitle-sized pieces: sentences, long ones cut at a comma or colon."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        out.extend(_split_long(sent, max_words))
    return [c for c in out if c]


def _split_long(s, max_words):
    words = s.split()
    if len(words) <= max_words and len(s) <= 66:
        return [s]
    mid = len(words) / 2
    cuts = [i + 1 for i, w in enumerate(words[:-1]) if w.endswith((",", ":", ";"))]
    cut = min(cuts, key=lambda i: abs(i - mid)) if cuts else int(mid)
    return _split_long(" ".join(words[:cut]), max_words) + _split_long(" ".join(words[cut:]), max_words)


def spoken(text, pronounce):
    for k, v in pronounce.items():
        text = re.sub(r"(?<![\w.])%s(?![\w])" % re.escape(k), v, text)
    return text


def inline(s):
    """*x* -> highlighted, `x` -> code; everything else escaped."""
    s = html.escape(s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


# ------------------------------------------------------------------ audio
def run(cmd):
    if cmd[0] == "ffmpeg":
        cmd = [cmd[0], "-nostdin", "-loglevel", "error"] + cmd[1:]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def to_wav(src, dst):
    run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", dst])


def read_wav(path):
    with wave.open(path) as w:
        return w.readframes(w.getnframes())


def silence(seconds):
    return b"\x00\x00" * int(round(seconds * RATE))


def secs(frames_bytes):
    return len(frames_bytes) / 2 / RATE


def say_chunk(text, voice, rate):
    key = hashlib.sha1(("%s|%s|%s" % (voice, rate, text)).encode()).hexdigest()[:16]
    wav = os.path.join(BUILD, "say", key + ".wav")
    if not os.path.exists(wav):
        aiff = wav[:-4] + ".aiff"
        run(["say", "-v", voice, "-r", str(rate), "-o", aiff, text])
        to_wav(aiff, wav)
        os.remove(aiff)
    return read_wav(wav)


def recording_for(scene_id):
    for ext in AUDIO_EXT:
        p = os.path.join(VOICE_DIR, scene_id + ext)
        if os.path.exists(p):
            return p
    return None


def scene_audio(scene, cfg):
    """Audio for one scene and the timing of every subtitle piece in it (seconds from scene start)."""
    pauses = cfg["pauses"]
    pieces = [(bi, c) for bi, beat in enumerate(scene["beats"]) for c in chunks_of(beat["say"])]
    rec = recording_for(scene["id"])
    if rec:
        wav = os.path.join(BUILD, "rec-" + scene["id"] + ".wav")
        to_wav(rec, wav)
        audio = read_wav(wav)
        total = secs(audio)
        weights = [len(c) + 12 for _, c in pieces]  # +12: every piece has some fixed cost
        t, timing = 0.0, []
        for (bi, c), wgt in zip(pieces, weights):
            d = total * wgt / sum(weights)
            timing.append({"beat": bi, "text": c, "start": t, "end": t + d})
            t += d
        return audio, timing, "recording " + os.path.relpath(rec, HERE)
    audio, timing = b"", []
    for i, (bi, c) in enumerate(pieces):
        if i:
            audio += silence(pauses["beat"] if bi != pieces[i - 1][0] else pauses["chunk"])
        clip = say_chunk(spoken(c, cfg["pronounce"]), cfg["voice"]["say_voice"], cfg["voice"]["say_rate"])
        timing.append({"beat": bi, "text": c, "start": secs(audio), "end": secs(audio) + secs(clip)})
        audio += clip
    return audio, timing, "say (%s)" % cfg["voice"]["say_voice"]


# ------------------------------------------------------------------ slides
CSS = """
:root { --navy:#0b1020; --navy2:#151b2e; --navy3:#1f2638; --ink:#0e1424; --blue:#3d5afe; --blue2:#8ea2ff;
  --tint:#e6eaff; --lime:#c8ff3d; --limet:#f0ffd0; --bg:#f4f5f8; --card:#fff; --border:#e3e6ee; --muted:#667085; --r:22px; }
* { box-sizing:border-box; margin:0; }
html, body { width:1920px; height:1080px; overflow:hidden; }
body { font-family:Inter, "Avenir Next", Helvetica, sans-serif; background:var(--bg); color:var(--ink); position:relative; }
body.dark { background:var(--navy); color:#fff; }
.serif, h1 { font-family:"Instrument Serif", Georgia, serif; font-weight:400; letter-spacing:-.01em; text-wrap:balance; }
h1 em { white-space:nowrap; }
h1 em { font-style:italic; background:linear-gradient(transparent 58%, var(--lime) 58%, var(--lime) 92%, transparent 92%); padding:0 .08em; }
body.dark h1 em { background:none; color:var(--lime); }
.kicker { font-size:24px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--blue); }
body.dark .kicker { color:var(--blue2); }
.brand { position:absolute; top:44px; right:64px; font-size:22px; font-weight:600; color:var(--muted); display:flex; gap:10px; align-items:center; }
body.dark .brand { color:#8790a8; }
.brand i { font-style:normal; color:var(--blue); } body.dark .brand i { color:var(--lime); }
.frame { position:absolute; left:120px; right:120px; top:110px; bottom:190px; }
code { font-family:Menlo, monospace; font-size:.85em; background:var(--tint); color:var(--blue); padding:.1em .35em; border-radius:8px; }
/* hero */
.hero { display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; gap:34px; }
.hero h1 { font-size:112px; line-height:1.05; max-width:1500px; }
.hero h1.name { font-size:170px; }
.hero .sub { font-size:42px; color:#b9c1d9; max-width:1300px; line-height:1.3; }
.hero .logo { font-size:120px; color:var(--lime); line-height:1; }
.hero .chips { display:flex; gap:18px; flex-wrap:wrap; justify-content:center; }
.chip { font-size:30px; font-weight:600; padding:14px 28px; border-radius:999px; background:var(--navy2); border:2px solid var(--navy3); color:#fff; }
.chip:nth-child(4) { background:var(--lime); color:var(--navy); border-color:var(--lime); }
.hero code { font-size:44px; background:var(--navy2); color:var(--lime); padding:16px 30px; border-radius:16px; border:2px solid var(--navy3); }
/* points */
.points { display:flex; flex-direction:column; gap:40px; }
.points h1 { font-size:96px; line-height:1.05; max-width:1600px; }
.points ul { list-style:none; padding:0; display:grid; gap:22px; margin-top:20px; }
.points li { font-size:44px; font-weight:500; padding:26px 36px; border-radius:var(--r); background:var(--card); border:2px solid var(--border); display:flex; gap:24px; align-items:center; }
.points li::before { content:""; width:18px; height:18px; border-radius:50%; background:var(--blue); flex:none; }
.points li.new { border-color:var(--blue); box-shadow:0 10px 40px rgba(61,90,254,.15); }
body.dark .points li { background:var(--navy2); border-color:var(--navy3); color:#fff; }
body.dark .points li::before { background:var(--lime); }
body.dark .points li.new { border-color:var(--lime); box-shadow:none; }
.points li.hidden { visibility:hidden; }
/* stat */
.stat { display:grid; grid-template-columns:auto 1fr; gap:24px 80px; align-content:center; }
.stat .kicker { grid-column:1 / -1; }
.stat .num { font-family:"Instrument Serif", Georgia, serif; font-size:330px; line-height:.9; color:var(--blue); }
.stat .label { font-size:58px; line-height:1.2; font-weight:500; align-self:center; }
.stat .source { grid-column:1 / -1; font-size:24px; color:var(--muted); }
.stat .note { grid-column:1 / -1; margin-top:30px; font-size:52px; padding:30px 40px; border-radius:var(--r); background:var(--navy); color:#fff; }
.stat .note em { font-style:normal; color:var(--lime); }
/* shot */
.shot { display:grid; grid-template-columns:520px 1fr; gap:60px; align-items:center; }
.shot h1 { font-size:76px; line-height:1.05; margin:18px 0 26px; }
.shot p { font-size:34px; line-height:1.4; color:var(--muted); }
.img { position:relative; border-radius:var(--r); overflow:hidden; border:2px solid var(--border); box-shadow:0 30px 80px rgba(11,16,32,.18); aspect-ratio:1272 / 810; background:#fff; }
.img img { width:100%; display:block; }
.spot { position:absolute; border:5px solid var(--lime); border-radius:14px; box-shadow:0 0 0 4000px rgba(11,16,32,.55), 0 0 40px rgba(200,255,61,.6); }
/* stream */
.stream { display:grid; grid-template-columns:560px 1fr; gap:60px; align-items:center; }
.stream h1 { font-size:84px; line-height:1.05; margin-top:18px; }
.term { background:var(--navy2); border:2px solid var(--navy3); border-radius:var(--r); padding:30px 34px; font-family:Menlo, monospace; font-size:22px; line-height:1.75; color:#c9d1e8; height:760px; overflow:hidden; position:relative; }
.term .l { display:flex; white-space:nowrap; } .term .t { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; }
.term .rid { color:#6b7591; flex:none; width:70px; } .term .k { flex:none; width:185px; color:var(--blue2); }
.term.lost .l { opacity:.35; }
.term .l.why { opacity:1; color:#fff; outline:3px solid var(--lime); outline-offset:4px; border-radius:6px; }
.term .tag { flex:none; margin-left:14px; font-family:Inter, sans-serif; font-size:20px; font-weight:700; background:var(--lime); color:var(--navy); padding:2px 14px; border-radius:999px; }
.term .more { color:#6b7591; margin-top:10px; }
/* flow */
.flow { display:flex; flex-direction:column; gap:90px; justify-content:center; }
.flow h1 { font-size:92px; line-height:1.05; margin-top:18px; }
.nodes { display:grid; grid-template-columns:1.15fr 70px 1fr 70px 1fr 70px 1.1fr; align-items:center; }
.node { background:var(--card); border:2px solid var(--border); border-radius:var(--r); padding:40px 36px; min-height:330px; display:flex; flex-direction:column; gap:12px; justify-content:center; }
.node b { font-size:46px; line-height:1.1; } .node span { font-size:31px; color:var(--muted); line-height:1.35; }
.node.focus { background:var(--navy); border-color:var(--navy); color:#fff; } .node.focus span { color:#b9c1d9; }
.node.focus b { color:var(--lime); }
.arrow { text-align:center; font-size:54px; color:var(--blue2); }
.hidden { visibility:hidden; }
/* badges */
.badges { display:flex; flex-direction:column; gap:60px; justify-content:center; }
.badges h1 { font-size:92px; line-height:1.05; margin-top:18px; }
.cards { display:grid; grid-auto-flow:column; grid-auto-columns:1fr; gap:30px; }
.bcard { background:var(--card); border:2px solid var(--border); border-radius:var(--r); padding:38px; display:flex; flex-direction:column; gap:20px; }
.bcard p { font-size:32px; line-height:1.4; }
.bcard .q { font-family:"Instrument Serif", Georgia, serif; font-size:40px; line-height:1.25; }
.badge { align-self:flex-start; font-size:24px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; padding:8px 18px; border-radius:999px; }
.b-ok { background:var(--limet); color:#3a5200; } .b-agent { background:var(--tint); color:var(--blue); }
.b-inf { background:#fff3d1; color:#7a4b00; border:2px dashed #e0b64a; }
/* doc */
.doc { display:grid; grid-template-columns:1fr 560px; gap:60px; align-items:center; }
.doc h1 { font-size:80px; line-height:1.05; margin:18px 0 34px; }
.md { background:var(--card); border:2px solid var(--border); border-radius:var(--r); padding:40px 44px; font-size:27px; line-height:1.55; box-shadow:0 30px 80px rgba(11,16,32,.12); }
.md h3 { font-size:32px; margin-bottom:14px; } .md li { margin-left:28px; } .md b { font-weight:600; }
.exports { display:grid; gap:24px; }
.exp { background:var(--navy); color:#fff; border-radius:var(--r); padding:34px 38px; }
.exp b { display:block; font-size:38px; color:var(--lime); margin-bottom:8px; } .exp span { font-size:28px; color:#b9c1d9; }
/* subtitles */
.cap { position:absolute; left:0; right:0; bottom:52px; display:flex; justify-content:center; }
.cap span { max-width:1600px; font-size:44px; line-height:1.3; font-weight:500; text-align:center; color:#fff; background:rgba(11,16,32,.88); padding:14px 32px; border-radius:16px; }
body.dark .cap span { background:rgba(31,38,56,.95); }
"""

STREAM = [
    ("R1", "instruction", "Let's start with a cheap, interpretable baseline for 30-day readmission"),
    ("R2", "action", "Write train_tfidf.py"),
    ("R3", "action", "Bash python3 train_tfidf.py --folds 5   [error]"),
    ("R4", "action", "Edit train_tfidf.py"),
    ("R5", "action", "Bash python3 train_tfidf.py --max-features 50000"),
    ("R6", "agent says", "The baseline reaches AUROC 0.54, barely above chance"),
    ("R7", "action", "Read results/fold_scores.csv"),
    ("R8", "instruction", "Switch to frozen PubMedBERT embeddings instead. N-grams lose the clinical semantics"),
    ("R9", "action", "Write embed_pubmedbert.py"),
    ("R10", "action", "Bash pip install transformers"),
    ("R11", "action", "Bash python3 embed_pubmedbert.py --folds 5"),
    ("R12", "action", "Edit embed_pubmedbert.py"),
    ("R13", "action", "Bash python3 embed_pubmedbert.py --seed 42"),
    ("R14", "commit", "a3f9c21 Replace TF-IDF pipeline with PubMedBERT embeddings"),
    ("R15", "action", "Grep max_len"),
    ("R16", "agent says", "Frozen PubMedBERT embeddings reach AUROC 0.81"),
]
FLOW = [("Claude Code + git hooks", "Every instruction, command, result and commit"),
        ("Raw log", "Everything, on your machine. Append-only."),
        ("Episodes", "The stream, grouped into units of work"),
        ("Diary", "Plans, runs, surprises, pivots. With the why.")]


def head(kicker):
    return '<div class="kicker">%s</div>' % inline(kicker) if kicker else ""


def slide_body(s):
    t = s["type"]
    if t == "hero":
        parts = ['<div class="logo">◈</div>'] if s.get("logo") else []
        parts.append('<h1 class="%s">%s</h1>' % ("name" if s.get("logo") else "", inline(s["title"])))
        if s.get("sub"):
            parts.append('<div class="sub">%s</div>' % inline(s["sub"]))
        if s.get("chips"):
            parts.append('<div class="chips">%s</div>' % "".join('<span class="chip">%s</span>' % inline(c) for c in s["chips"]))
        if s.get("code"):
            parts.append("<code>%s</code>" % html.escape(s["code"]))
        return True, '<div class="frame hero">%s</div>' % "".join(parts)
    if t == "points":
        n = s.get("show", len(s["items"]))
        lis = "".join('<li class="%s">%s</li>' % ("new" if i == n - 1 else ("hidden" if i >= n else ""), inline(it))
                      for i, it in enumerate(s["items"]))
        return s.get("dark", False), '<div class="frame points">%s<h1>%s</h1><ul>%s</ul></div>' % (head(s.get("kicker")), inline(s["title"]), lis)
    if t == "stat":
        note = '<div class="note">%s</div>' % inline(s["note"]) if s.get("note") else ""
        return False, ('<div class="frame stat">%s<div class="num">%s</div><div class="label">%s</div>'
                       '<div class="source">%s</div>%s</div>') % (head(s.get("kicker")), html.escape(s["number"]),
                                                                 inline(s["label"]), html.escape(s["source"]), note)
    if t == "shot":
        spot = ""
        if s.get("spot"):
            x, y, w, h = s["spot"]
            spot = '<div class="spot" style="left:%.3f%%;top:%.3f%%;width:%.3f%%;height:%.3f%%"></div>' % (
                100 * x / SHOT_W, 100 * y / SHOT_H, 100 * w / SHOT_W, 100 * h / SHOT_H)
        src = "file://" + os.path.join(ASSETS, s["img"])
        return False, ('<div class="frame shot"><div>%s<h1>%s</h1><p>%s</p></div>'
                       '<div class="img"><img src="%s">%s</div></div>') % (head(s.get("kicker")), inline(s["title"]),
                                                                          inline(s.get("body", "")), src, spot)
    if t == "stream":
        lines = STREAM[:s["lines"]]
        rows = []
        for rid, kind, text in lines:
            why = s.get("lost") and rid == "R8"
            rows.append('<div class="l%s"><span class="rid">%s</span><span class="k">%s</span><span class="t">%s</span>%s</div>' % (
                " why" if why else "", rid, kind, html.escape(text), '<span class="tag">the decision</span>' if why else ""))
        more = '<div class="more">… R312 actions by the end of the afternoon</div>' if s.get("lost") else ""
        return True, ('<div class="frame stream"><div>%s<h1>%s</h1></div><div class="term%s">%s%s%s</div></div>') % (
            head(s.get("kicker")), inline(s["title"]), " lost" if s.get("lost") else "", "".join(rows), more, "")
    if t == "flow":
        n, focus = s.get("show", 4), s.get("focus", -1)
        cells = []
        for i, (b, sp) in enumerate(FLOW):
            if i:
                cells.append('<div class="arrow%s">→</div>' % (" hidden" if i >= n else ""))
            cls = "node" + (" focus" if i == focus else "") + (" hidden" if i >= n else "")
            cells.append('<div class="%s"><b>%s</b><span>%s</span></div>' % (cls, b, sp))
        return False, '<div class="frame flow"><div>%s<h1>%s</h1></div><div class="nodes">%s</div></div>' % (
            head(s.get("kicker")), inline(s["title"]), "".join(cells))
    if t == "badges":
        if s["mode"] == "stated":
            cards = [("b-ok", "stated · quote found", '<p class="q">“N-grams lose the clinical semantics we need: negations collapse into the same features as positives.”</p><p>The model’s reason is checked word for word against what the researcher wrote at the time.</p>'),
                     ("b-inf", "inferred · no quote", "<p>No matching words in the record? Then it is labelled <b>inferred</b>: shown with lower trust, never as fact.</p><p>The model’s own wording is kept apart from the record.</p>")]
        else:
            cards = [("b-ok", "researcher", "<p>Stated by the person doing the research, at the time, or confirmed by them in one click.</p>"),
                     ("b-agent", "agent", "<p>Stated by the AI agent while it worked: its commands, results and reports.</p>"),
                     ("b-inf", "inferred", "<p>Reconstructed by Episteme’s own rules. Useful, and clearly marked as lower trust.</p>")]
        body = "".join('<div class="bcard"><span class="badge %s">%s</span>%s</div>' % c for c in cards)
        return False, '<div class="frame badges"><div>%s<h1>%s</h1></div><div class="cards">%s</div></div>' % (
            head(s.get("kicker")), inline(s["title"]), body)
    if t == "doc":
        md = ('<h3>[Step 4] Pivot: Change of approach</h3><ul>'
              '<li><b>Stated by:</b> stated by the researcher</li>'
              '<li><b>Reason:</b> N-grams lose the clinical semantics we need: negations collapse into the same features as positives.</li>'
              '<li><b>Raw evidence:</b> R8</li><li><b>Linked to:</b> E3, E4</li></ul>')
        ex = ('<div class="exports"><div class="exp"><b>Decision appendix</b><span>Markdown, for the paper or supplementary material</span></div>'
              '<div class="exp"><b>W3C PROV-JSON</b><span>For provenance tools. Keeps who stated, classified and confirmed each step</span></div></div>')
        return False, '<div class="frame doc"><div>%s<h1>%s</h1><div class="md">%s</div></div>%s</div>' % (
            head(s.get("kicker")), inline(s["title"]), md, ex)
    raise ValueError("unknown slide type: %s" % t)


def slide_html(slide, caption=None):
    dark, body = slide_body(slide)
    brand = "" if slide.get("logo") else '<div class="brand"><i>◈</i> Episteme</div>'
    cap = '<div class="cap"><span>%s</span></div>' % html.escape(caption) if caption else ""
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&display=block" rel="stylesheet">'
            '<style>%s</style></head><body class="%s">%s%s%s</body></html>') % (CSS, "dark" if dark else "", brand, body, cap)


def render(page):
    """HTML -> PNG with headless Chrome; cached by content."""
    key = hashlib.sha1(page.encode()).hexdigest()[:16]
    png = os.path.join(BUILD, "frames", key + ".png")
    if not os.path.exists(png):
        src = os.path.join(BUILD, "html", key + ".html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(page)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--window-size=%d,%d" % (W, H), "--virtual-time-budget=4000", "--allow-file-access-from-files",
                        "--screenshot=" + png, "file://" + src],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    return png


# ------------------------------------------------------------------ outputs
def ts(t, sep=","):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d%s%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, sep, ms % 1000)


def write_script(cfg, timeline=None):
    os.makedirs(TEXT_DIR, exist_ok=True)
    lines = ["# Episteme promo: script", "",
             "Generated from `promo/scenes.json` by `promo/build.py`. Edit the JSON, not this file.", "",
             "To replace the voice, record one file per scene (text in `promo/voice-text/<id>.txt`), save it as",
             "`promo/voice/<id>.mp3` and run `python3 promo/build.py` again. See the top of `build.py`.", ""]
    total_words = 0
    for sc in cfg["scenes"]:
        text = " ".join(b["say"] for b in sc["beats"])
        total_words += len(text.split())
        with open(os.path.join(TEXT_DIR, sc["id"] + ".txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        when = ""
        if timeline and sc["id"] in timeline:
            a, b = timeline[sc["id"]]
            when = " (%s to %s)" % (ts(a, ".")[3:8], ts(b, ".")[3:8])
        lines += ["## %s%s" % (sc["id"], when), ""]
        for i, b in enumerate(sc["beats"], 1):
            s = b["slide"]
            what = s.get("title", "")
            if s["type"] == "shot":
                what += " [screenshot: %s]" % s["img"]
            lines += ["**Slide %d** (%s): %s" % (i, s["type"], what.replace("*", "")), "", "> " + b["say"], ""]
    lines.insert(2, "About %d words. %s" % (total_words, "" if not timeline else "Length with the current voice: %s." % ts(max(v[1] for v in timeline.values()), ".")[3:8]))
    lines.insert(3, "")
    with open(os.path.join(HERE, "SCRIPT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def concat_list(path, items):
    """items: [(png, seconds)] -> ffmpeg concat-demuxer file."""
    with open(path, "w") as f:
        for png, d in items:
            f.write("file '%s'\nduration %.3f\n" % (png, d))
        f.write("file '%s'\n" % items[-1][0])  # the demuxer ignores the last duration otherwise


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--script-only", action="store_true", help="only write SCRIPT.md and voice-text/")
    ap.add_argument("--jobs", type=int, default=6, help="slides rendered in parallel")
    a = ap.parse_args()
    with open(os.path.join(HERE, "scenes.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    if a.script_only:
        return write_script(cfg)
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit("needs %s on PATH" % tool)
    if not os.path.exists(CHROME):
        sys.exit("needs Google Chrome; set CHROME=/path/to/chrome")
    for d in (BUILD, OUT, os.path.join(BUILD, "say"), os.path.join(BUILD, "frames"), os.path.join(BUILD, "html")):
        os.makedirs(d, exist_ok=True)

    # 1. voice, and the timeline it implies
    p = cfg["pauses"]
    audio = silence(p["lead_in"])
    caps, beats, timeline = [], [], {}
    for sc in cfg["scenes"]:
        clip, timing, src = scene_audio(sc, cfg)
        t0 = secs(audio)
        print("%-20s %6.1fs  %s" % (sc["id"], secs(clip), src))
        audio += clip + silence(p["scene"])
        t_end = secs(audio)
        timeline[sc["id"]] = (t0, t_end)
        for i, c in enumerate(timing):
            nxt = timing[i + 1]["start"] + t0 if i + 1 < len(timing) else t_end
            caps.append({"slide": sc["beats"][c["beat"]]["slide"], "text": c["text"], "start": c["start"] + t0,
                         "end": c["end"] + t0, "until": nxt})
        for bi, beat in enumerate(sc["beats"]):
            mine = [c for c in timing if c["beat"] == bi]
            beats.append({"slide": beat["slide"], "start": mine[0]["start"] + t0})
    for i, b in enumerate(beats):
        b["until"] = beats[i + 1]["start"] if i + 1 < len(beats) else secs(audio)
    beats[0]["start"] = 0.0  # the first slide is up during the lead-in
    voice_wav = os.path.join(OUT, "voiceover.wav")
    with wave.open(voice_wav, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio)

    # 2. subtitles and script
    with open(os.path.join(OUT, "episteme-promo.srt"), "w", encoding="utf-8") as f:
        for i, c in enumerate(caps, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, ts(c["start"]), ts(c["end"] + 0.2), c["text"]))
    write_script(cfg, timeline)

    # 3. slides: one per beat (clean) and one per subtitle piece (captioned)
    pages = [slide_html(b["slide"]) for b in beats] + [slide_html(c["slide"], c["text"]) for c in caps]
    print("rendering %d slides..." % len(set(pages)))
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        pngs = list(ex.map(render, pages))
    clean_pngs, cap_pngs = pngs[:len(beats)], pngs[len(beats):]

    # 4. videos
    clean = [(png, b["until"] - b["start"]) for png, b in zip(clean_pngs, beats)]
    capped = [(clean_pngs[0], caps[0]["start"])]  # the lead-in: first slide, no subtitle yet
    for i, (png, c) in enumerate(zip(cap_pngs, caps)):
        end = caps[i + 1]["start"] if i + 1 < len(caps) else secs(audio)
        capped.append((png, end - c["start"]))
    srt = os.path.join(OUT, "episteme-promo.srt")
    for name, items in (("episteme-promo.mp4", capped), ("episteme-promo-clean.mp4", clean)):
        lst = os.path.join(BUILD, name + ".txt")
        concat_list(lst, items)
        target = os.path.join(OUT, name) if items is capped else os.path.join(BUILD, name)
        print("encoding %s..." % name)
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", voice_wav, "-map", "0:v", "-map", "1:a",
             "-vf", "fps=%d,format=yuv420p" % FPS, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-tune", "stillimage",
             "-c:a", "aac", "-b:a", "192k", "-t", "%.3f" % secs(audio), "-movflags", "+faststart", target])
    # the clean version gets the subtitles as a track you can switch on, added without re-encoding
    run(["ffmpeg", "-y", "-i", os.path.join(BUILD, "episteme-promo-clean.mp4"), "-i", srt, "-map", "0", "-map", "1",
         "-c", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-movflags", "+faststart",
         os.path.join(OUT, "episteme-promo-clean.mp4")])
    print("done: %s long. Outputs in %s" % (ts(secs(audio), ".")[3:8], os.path.relpath(OUT)))


if __name__ == "__main__":
    main()
