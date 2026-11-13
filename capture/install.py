#!/usr/bin/env python3
"""Switch Episteme capture on (or off) for one research project.

    python3 capture/install.py /path/to/research-project            # on
    python3 capture/install.py /path/to/research-project --remove   # off

On:
  * adds the Claude Code hook to <project>/.claude/settings.local.json
    (the per-user settings file, usually not committed), keeping anything else there;
  * links capture/git_post_commit as <project>/.git/hooks/post-commit, if the
    project is a git repo and has no other post-commit hook.
Off: removes exactly those two things.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "claude_hook.py")
GIT_HOOK = os.path.join(HERE, "git_post_commit")
EVENTS = {"UserPromptSubmit": None, "PostToolUse": "*", "PostToolUseFailure": "*", "Stop": None}


def command():
    return "python3 " + json.dumps(HOOK) if " " in HOOK else "python3 " + HOOK


def is_ours(entry):
    return any(HOOK in (h.get("command") or "") for h in entry.get("hooks") or [])


def settings_path(project):
    return os.path.join(project, ".claude", "settings.local.json")


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def install(project):
    path = settings_path(project)
    data = load(path)
    hooks = data.setdefault("hooks", {})
    for event, matcher in EVENTS.items():
        entries = [e for e in hooks.get(event, []) if not is_ours(e)]
        entry = {"hooks": [{"type": "command", "command": command(), "timeout": 10}]}
        if matcher:
            entry["matcher"] = matcher
        hooks[event] = entries + [entry]
    save(path, data)
    print("Claude Code hook: added to %s" % path)

    git_dir = os.path.join(project, ".git")
    target = os.path.join(git_dir, "hooks", "post-commit")
    if not os.path.isdir(git_dir):
        print("git hook: skipped (%s is not a git repo)" % project)
    elif os.path.lexists(target) and os.path.realpath(target) != os.path.realpath(GIT_HOOK):
        print("git hook: skipped, %s already exists (not ours). Call capture/git_post_commit from it." % target)
    else:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.lexists(target):
            os.symlink(GIT_HOOK, target)
        print("git hook: linked %s" % target)
    print("\nStart Episteme (./run) before working; events sent while it is down are kept and sent later.")


def remove(project):
    path = settings_path(project)
    data = load(path)
    hooks = data.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [e for e in hooks[event] if not is_ours(e)]
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        data.pop("hooks", None)
    if os.path.exists(path):
        save(path, data)
    print("Claude Code hook: removed from %s" % path)
    target = os.path.join(project, ".git", "hooks", "post-commit")
    if os.path.islink(target) and os.path.realpath(target) == os.path.realpath(GIT_HOOK):
        os.remove(target)
        print("git hook: removed %s" % target)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1 or not os.path.isdir(args[0]):
        print(__doc__)
        return 1
    project = os.path.abspath(args[0])
    (remove if "--remove" in argv else install)(project)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
