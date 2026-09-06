#!/usr/bin/env python3
"""Strip credentials out of the repo's copies of config files.

sync.sh runs this after copying. It edits only files under home/ in this repo,
never anything in $HOME, so the working machine keeps its real values.

The rule is per-file and deliberate rather than a blanket regex: a broad
search-and-replace over config is how you end up with a repo that silently
mangles settings. Add a handler when a new file starts carrying a secret.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).parent
PLACEHOLDER = "<set-me: see docs/04-secrets-and-logins.md>"

SECRET_SHAPE = re.compile(
    r"(gh[pousr]_[A-Za-z0-9]{16,}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{35}"
    r"|glpat-[A-Za-z0-9_-]{20,}"
    r"|npm_[A-Za-z0-9]{36})"
)


def scrub_claude_settings(path: pathlib.Path) -> list[str]:
    """Blank the `env` block's secret-shaped values in .claude/settings.json."""
    data = json.loads(path.read_text())
    env = data.get("env")
    if not isinstance(env, dict):
        return []

    changed = []
    for key, value in env.items():
        if isinstance(value, str) and SECRET_SHAPE.search(value):
            env[key] = PLACEHOLDER
            changed.append(key)

    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n")
    return changed


HANDLERS = {
    "home/.claude/settings.json": scrub_claude_settings,
}


def main() -> int:
    total = 0
    for rel, handler in HANDLERS.items():
        path = REPO / rel
        if not path.exists():
            continue
        for key in handler(path):
            print(f"  redacted {rel} :: {key}")
            total += 1

    # Backstop: if a secret shape survives anywhere under home/, fail loudly
    # rather than let it reach a commit.
    leaks = []
    for path in (REPO / "home").rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        if SECRET_SHAPE.search(text):
            leaks.append(path.relative_to(REPO))

    if leaks:
        print("\nREFUSING TO CONTINUE — credential-shaped strings still present:")
        for leak in leaks:
            print(f"  {leak}")
        print("Add a handler for these in sanitize.py.")
        return 1

    print(f"  sanitize: {total} value(s) redacted, no leaks detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
