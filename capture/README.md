# Capture

Automatic capture from an AI-assisted research project into Episteme. Nothing here needs a pip install.

| Source | How | What becomes a raw event |
|---|---|---|
| Claude Code | hook (`claude_hook.py`) | your instructions, each tool call, failures, the agent's final message per turn |
| git | `post-commit` hook (`git_post_commit`) | each commit: hash, message, changed file names, whether the agent or a person made it |

Raw events go to `POST /api/raw` and are kept in `.episteme/raw.jsonl`. Episteme groups them into episodes (`episteme/episodes.py`); the diary only shows the decisions.

## Switch it on

```bash
./run                                                   # start Episteme first
python3 capture/install.py /path/to/research-project    # once per project
```

This adds the hook to the project's `.claude/settings.local.json` and links the git hook. `--remove` undoes both. Then work in that project with Claude Code as usual.

If Episteme is not running, events are kept in `.episteme/spool.jsonl` and sent, in order, with the next event once it is.

## Report results as RESULT lines

Episodes close on results, so scripts should print them in this form:

```
RESULT spearman=0.71 split=random
RESULT auroc=0.81 seed=42
```

Numbers become metrics, anything else becomes context. One line per result; several key=value pairs per line are fine. Metrics whose name contains loss, error, rmse, mae, time and similar are treated as lower-is-better when checking for drops.

## What is captured, and what is not

- Captured: instruction text, tool names, shell commands, the last 3000 characters of command output (plus every RESULT line), names of files read or written, error messages, the agent's final message each turn, commit messages and file names.
- Not captured: file contents the agent writes or reads, diffs, the agent's intermediate messages within a turn.
- Paths inside the project are shortened to relative paths.
- Secrets are stripped before anything is written or sent (`episteme/redact.py`): common API key formats, bearer tokens, passwords in URLs, `key=value` pairs with secret-looking names, and the values of environment variables whose names contain KEY, TOKEN, SECRET or PASSWORD. This is pattern-based: a safety net, not a guarantee.

## Limits

- Claude Code only for agent capture. Other tools can send raw events to `POST /api/raw` (see `capture/send.py`).
- Decisions made outside the agent (a meeting, a chat) are not seen. The why-prompt and manual notes cover them.
- Long runs started in the background (cluster jobs, `nohup`) report their result outside the hook. Keep runs in the foreground, or log the result manually.
- The hook adds a few tens of milliseconds per tool call. It never blocks the agent and never fails a tool call.
