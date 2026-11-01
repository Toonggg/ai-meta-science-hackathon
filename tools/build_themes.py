#!/usr/bin/env python3
"""Build episteme/static/themes.css from well-known editor palettes, with WCAG checks.

Each theme maps semantic roles (page, panel, text, muted, accent, and one colour
per event type) to the palette's *official* hex values. The script then checks
every text-on-surface pair the UI actually renders against WCAG AA (4.5:1 for
normal text) and, where an official colour falls short, nudges it toward the
theme's text colour just enough to pass. Every nudge is reported, so the deviation
from the original palette is explicit.

    python3 tools/build_themes.py          # rebuild + report
    python3 tools/build_themes.py --check  # report only, exit 1 if anything fails

To add a theme: add an entry to THEMES and rerun.
"""

import colorsys
import os
import sys

TARGET = 4.5  # WCAG AA, normal-size text
OUT = os.path.join(os.path.dirname(__file__), "..", "episteme", "static", "themes.css")

# Roles: page (window bg), panel (cards), input, line (borders), ink (text), muted (secondary text),
# accent (buttons, focus), link, and event/status colours used as text and tints.
THEMES = {
    "tokyo-night": dict(
        label="Tokyo Night", scheme="dark", source="github.com/folke/tokyonight.nvim (night)",
        page="#16161e", panel="#1a1b26", input="#16161e", line="#292e42", ink="#c0caf5", muted="#a9b1d6",
        accent="#7aa2f7", link="#7dcfff",
        plan="#7aa2f7", run="#9ece6a", surprise="#ff9e64", pivot="#f7768e", note="#a9b1d6", artifact="#bb9af7",
        question="#7dcfff", ok="#9ece6a", warn="#e0af68", bad="#f7768e"),
    "dracula": dict(
        label="Dracula", scheme="dark", source="draculatheme.com/contribute",
        page="#21222c", panel="#282a36", input="#21222c", line="#44475a", ink="#f8f8f2", muted="#6272a4",
        accent="#bd93f9", link="#8be9fd",
        plan="#bd93f9", run="#50fa7b", surprise="#ffb86c", pivot="#ff79c6", note="#6272a4", artifact="#f1fa8c",
        question="#8be9fd", ok="#50fa7b", warn="#ffb86c", bad="#ff5555"),
    "catppuccin-mocha": dict(
        label="Catppuccin Mocha", scheme="dark", source="catppuccin.com/palette (mocha)",
        page="#181825", panel="#1e1e2e", input="#181825", line="#313244", ink="#cdd6f4", muted="#a6adc8",
        accent="#89b4fa", link="#89dceb",
        plan="#89b4fa", run="#a6e3a1", surprise="#fab387", pivot="#f5c2e7", note="#9399b2", artifact="#cba6f7",
        question="#94e2d5", ok="#a6e3a1", warn="#f9e2af", bad="#f38ba8"),
    "one-dark": dict(
        label="One Dark", scheme="dark", source="github.com/atom/atom one-dark-syntax",
        page="#21252b", panel="#282c34", input="#21252b", line="#3e4451", ink="#dcdfe4", muted="#9da5b4",
        accent="#61afef", link="#56b6c2",
        plan="#61afef", run="#98c379", surprise="#d19a66", pivot="#e06c75", note="#9da5b4", artifact="#c678dd",
        question="#56b6c2", ok="#98c379", warn="#e5c07b", bad="#e06c75"),
    "catppuccin-latte": dict(
        label="Catppuccin Latte (light)", scheme="light", source="catppuccin.com/palette (latte)",
        page="#e6e9ef", panel="#eff1f5", input="#e6e9ef", line="#ccd0da", ink="#4c4f69", muted="#6c6f85",
        accent="#1e66f5", link="#1e66f5",
        plan="#1e66f5", run="#40a02b", surprise="#fe640b", pivot="#ea76cb", note="#6c6f85", artifact="#8839ef",
        question="#179299", ok="#40a02b", warn="#df8e1d", bad="#d20f39"),
}
DEFAULT = "tokyo-night"
EVENT_ROLES = ["plan", "run", "surprise", "pivot", "note", "artifact", "question", "ok", "warn", "bad"]
TEXT_ROLES = ["ink", "muted", "accent", "link"] + EVENT_ROLES

# Tints used behind coloured text (must match style.css): chips/pills 18%, banners 10%.
CHIP, BANNER = 0.18, 0.10


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):  # t of a over b (like color-mix(in srgb, a t, b))
    a, b = rgb(a), rgb(b)
    return hexc([a[i] * t + b[i] * (1 - t) for i in range(3)])


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def surfaces(t, fg_role, fg):
    """Every background a given text colour is drawn on in the UI."""
    s = {"page": t["page"], "panel": t["panel"], "input": t["input"]}
    if fg_role in EVENT_ROLES or fg_role in ("accent", "link"):
        s["own chip tint"] = mix(fg, t["panel"], CHIP)
        s["own banner tint"] = mix(fg, t["panel"], BANNER)
    if fg_role == "muted":
        s["muted chip tint"] = mix(fg, t["panel"], CHIP)
    if fg_role in ("ink", "muted"):
        for r in ("accent", "pivot", "warn", "bad", "ok"):
            s["%s banner" % r] = mix(t[r], t["panel"], BANNER)
    return s


def worst(t, role, fg):
    return min((contrast(fg, bg), name) for name, bg in surfaces(t, role, fg).items())


def fix(t, role):
    """Shift lightness only (hue and saturation kept) until the colour passes everywhere:
    lighter on dark themes, darker on light themes. Keeps the palette's character."""
    r, g, b = (v / 255 for v in rgb(t[role]))
    h, l, s_ = colorsys.rgb_to_hls(r, g, b)
    sign = 1 if t["scheme"] == "dark" else -1
    fg = t[role]
    while worst(t, role, fg)[0] < TARGET and 0 <= l <= 1:
        l += sign * 0.005
        fg = hexc([v * 255 for v in colorsys.hls_to_rgb(h, min(1, max(0, l)), s_)])
    return fg


def on_colour(t):
    """Text drawn on solid event colours (timeline dots, primary button): prefer the theme's own
    page colour (dark themes) or white (light themes); fall back to black/white if needed."""
    cands = [t["page"], "#000000"] if t["scheme"] == "dark" else ["#ffffff", "#000000"]
    for c in cands:
        if min(contrast(c, t[r]) for r in ["accent"] + EVENT_ROLES) >= TARGET:
            return c
    return cands[-1]


def build(check_only=False):
    report, failures, blocks = [], 0, []
    for name, t in THEMES.items():
        t = dict(t)
        changes = []
        for role in TEXT_ROLES:
            before = t[role]
            r0, where = worst(t, role, before)
            if r0 < TARGET:
                t[role] = fix(t, role)
                r1, _ = worst(t, role, t[role])
                changes.append("  %-9s %s -> %s  (%.2f -> %.2f on %s)" % (role, before, t[role], r0, r1, where))
        on = on_colour(t)
        dot_min = min((contrast(on, t[r]), r) for r in ["accent"] + EVENT_ROLES)
        final_min = min((worst(t, r, t[r])[0], r) for r in TEXT_ROLES)
        ok = final_min[0] >= TARGET and dot_min[0] >= TARGET
        failures += not ok
        report.append("%s %-24s min text contrast %.2f (%s), on-colour %s min %.2f (%s)%s" % (
            "PASS" if ok else "FAIL", t["label"], final_min[0], final_min[1], on, dot_min[0], dot_min[1],
            ("\n" + "\n".join(changes)) if changes else "  [official colours unchanged]"))
        sel = ':root[data-theme="%s"]' % name
        if name == DEFAULT:
            sel = ":root, " + sel
        dark = t["scheme"] == "dark"
        vars_ = {
            "bg": t["page"], "panel": t["panel"], "input": t["input"], "line": t["line"], "ink": t["ink"],
            "muted": t["muted"], "accent": t["accent"], "accent-ink": on, "on-c": on, "link": t["link"],
            **{r: t[r] for r in EVENT_ROLES},
            "shadow": "0 1px 2px rgba(0,0,0,.35), 0 4px 14px rgba(0,0,0,.25)" if dark else
                      "0 1px 2px rgba(0,0,0,.05), 0 2px 8px rgba(0,0,0,.05)",
            "backdrop": "rgba(0,0,0,.6)" if dark else "rgba(30,30,50,.35)",
        }
        body = "\n".join("  --%s: %s;" % kv for kv in vars_.items())
        blocks.append("/* %s - %s */\n%s {\n  color-scheme: %s;\n%s\n}" % (t["label"], t["source"], sel, t["scheme"], body))

    print("\n".join(report))
    if not check_only:
        css = ("/* GENERATED by tools/build_themes.py - edit the palettes there, not here.\n"
               "   Every text/background pair is checked against WCAG AA (%.1f:1). */\n\n" % TARGET) + "\n\n".join(blocks) + "\n"
        with open(OUT, "w") as f:
            f.write(css)
        print("wrote", os.path.relpath(OUT))
    return failures


if __name__ == "__main__":
    sys.exit(1 if build("--check" in sys.argv) else 0)
