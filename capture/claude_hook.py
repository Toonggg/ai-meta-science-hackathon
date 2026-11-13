#!/usr/bin/env python3
"""Claude Code hook: turn agent activity into Episteme raw events.

Register it for UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop
(see capture/README.md). Claude Code passes one JSON payload on stdin per event:

  UserPromptSubmit    {"prompt": ...}                           -> instruction (human)
  PostToolUse         {"tool_name", "tool_input", "tool_response"} -> action
  PostToolUseFailure  {"tool_name", "tool_input", "error"}      -> action, error=true
  Stop                {"last_assistant_message": ...}           -> agent_text + stop

All payloads carry session_id and cwd. Paths under cwd are shortened to relative
paths. File contents written by the agent are not captured, only their names.
Outputs keep every RESULT line plus the last OUTPUT_TAIL characters.

Always exits 0 and prints nothing, whatever happens.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_TAIL = 3000
TEXT_MAX = 4000
RESULT_LINE = re.compile(r"^\s*RESULT\b.*$", re.M)
FILE_TOOLS = ("Write", "Edit", "MultiEdit", "Read", "NotebookEdit", "NotebookRead")


def rel(text, cwd):
    if not text or not cwd:
        return text
    return text.replace(cwd.rstrip("/") + "/", "")


def clip_output(out):
    out = out or ""
    if len(out) <= OUTPUT_TAIL:
        return out
    results = RESULT_LINE.findall(out)
    tail = out[-OUTPUT_TAIL:]
    kept = [r for r in results if r not in tail]
    return ("\n".join(kept) + "\n[...]\n" if kept else "[...]\n") + tail


def files_of(tool_input, cwd):
    out = []
    for k in ("file_path", "notebook_path", "path"):
        v = tool_input.get(k)
        if isinstance(v, str) and v:
            out.append(rel(v, cwd))
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and edit.get("file_path"):
            out.append(rel(edit["file_path"], cwd))
    return out


def bash_output(resp):
    if isinstance(resp, dict):
        parts = [resp.get("stdout") or "", resp.get("stderr") or ""]
        return "\n".join(p for p in parts if p)
    return str(resp or "")


def to_raw(p):
    event = p.get("hook_event_name")
    cwd = p.get("cwd") or ""
    base = {"source": "agent", "session": (p.get("session_id") or "")[:8]}

    if event == "UserPromptSubmit":
        return [dict(base, kind="instruction", text=(p.get("prompt") or "")[:TEXT_MAX])]

    if event in ("PostToolUse", "PostToolUseFailure"):
        tool = p.get("tool_name") or ""
        ti = p.get("tool_input") or {}
        ev = dict(base, kind="action", tool=tool, files=files_of(ti, cwd))
        if tool == "Bash":
            ev["command"] = rel(ti.get("command") or "", cwd)
            if ti.get("description"):
                ev["intent"] = ti["description"][:300]
        elif tool in ("Grep", "Glob"):
            ev["command"] = "%s %s" % (tool, ti.get("pattern") or "")
        if event == "PostToolUseFailure":
            ev["error"] = True
            ev["output"] = clip_output(rel(p.get("error") or "", cwd))
        elif tool == "Bash":
            ev["output"] = clip_output(rel(bash_output(p.get("tool_response")), cwd))
            if isinstance(p.get("tool_response"), dict) and p["tool_response"].get("interrupted"):
                ev["error"] = True
        return [ev]

    if event == "Stop":
        out = []
        msg = p.get("last_assistant_message") or ""
        if msg.strip():
            out.append(dict(base, kind="agent_text", text=rel(msg, cwd)[:TEXT_MAX]))
        out.append(dict(base, kind="stop"))
        return out

    return []


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        events = to_raw(payload)
        if events:
            from send import send
            send(events)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
