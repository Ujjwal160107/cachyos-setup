"""Optional GitHub enrichment through the gh CLI. Absent gh is not an error.

Every function degrades to a safe default (False/None/"unknown"/empty) on any
subprocess failure, malformed JSON, or unexpected payload shape -- it never
raises. Every function also takes an injectable `runner` so tests never touch
the network or a real `gh` binary; `default_runner` is only exercised through
that seam in production.
"""

import json
import subprocess

PR_FIELDS = "number,title,body,additions,deletions,changedFiles,url,mergedAt,comments"

# A per-comment character cap (see fetch_pr) does not bound total payload
# size when the comment count itself is unbounded -- a PR with 300 comments
# would still produce ~600KB in one cluster. Keep only the earliest
# MAX_COMMENTS: DESIGN.md §7.1 uses review threads demanding change as the
# evidence for the Tension score, and those arrive early in a PR's life.
MAX_COMMENTS = 20


def default_runner(args, cwd):
    """Run a command, returning (returncode, stdout). Never raises.

    stdout is decoded as UTF-8 with replacement instead of letting
    subprocess fall back to the platform locale codec under strict error
    handling -- on Windows that's cp1252, and a PR body or review comment
    containing an emoji or CJK/Cyrillic text would otherwise raise
    UnicodeDecodeError (a ValueError, not caught by the tuple below) and
    crash a run that this module promises never crashes on absent/odd gh
    output. Mirrors scripts/detect.py's run_git, which carries the same fix
    for the same reason.
    """
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return (1, "")
    return (result.returncode, result.stdout)


def _run(runner, args, cwd):
    return (runner or default_runner)(args, cwd)


def gh_available(runner=None):
    code, _ = _run(runner, ["gh", "--version"], ".")
    return code == 0


def gh_authenticated(runner=None):
    """True when gh holds a usable credential.

    Installed and authenticated are different facts, and DESIGN.md §5.2 gives
    them separate keys (capabilities.gh, capabilities.gh_auth). Collapsing them
    makes a degraded run name the wrong missing signal, which §14 criterion 2
    forbids. `gh auth status` exits non-zero with no stored credential, and its
    output goes to stderr, so only the exit code is consulted.
    """
    code, _ = _run(runner, ["gh", "auth", "status"], ".")
    return code == 0


def _json_or_none(code, output):
    if code != 0 or not output.strip():
        return None
    try:
        return json.loads(output)
    except ValueError:
        return None


def repo_visibility(repo, runner=None):
    """Return 'public', 'private', or 'unknown' -- never a fourth value.

    GitHub Enterprise repos report visibility as INTERNAL. DESIGN.md §8
    keys redaction posture on public versus private-or-unknown, so INTERNAL
    is folded into 'private': an internal repo is not public, and that
    errs toward the safer stack-only redaction posture.
    """
    code, output = _run(runner, ["gh", "repo", "view", "--json", "visibility"], repo)
    data = _json_or_none(code, output)
    if not isinstance(data, dict):
        return "unknown"
    value = str(data.get("visibility", "")).lower()
    if value == "internal":
        return "private"
    return value if value in ("public", "private") else "unknown"


def fetch_pr(repo, number, runner=None):
    code, output = _run(
        runner, ["gh", "pr", "view", str(number), "--json", PR_FIELDS], repo
    )
    data = _json_or_none(code, output)
    if not isinstance(data, dict):
        return None

    comments = []
    for comment in (data.get("comments") or [])[:MAX_COMMENTS]:
        # gh's JSON is untrusted input: a list element that is not an object
        # would make .get() raise AttributeError, breaking the module
        # docstring's no-raise promise. Same guard shape pr_number_for_sha
        # already applies to its own list payload.
        if not isinstance(comment, dict):
            continue
        author = comment.get("author") or {}
        comments.append(
            {
                "author": author.get("login", "") if isinstance(author, dict) else "",
                "body": (comment.get("body") or "")[:2000],
            }
        )

    return {
        "number": data.get("number"),
        "title": data.get("title", ""),
        "body": (data.get("body") or "")[:8000],
        "comments": comments,
        "additions": data.get("additions", 0),
        "deletions": data.get("deletions", 0),
        "changed_files": data.get("changedFiles", 0),
        "url": data.get("url", ""),
        "merged_at": data.get("mergedAt"),
    }


def pr_number_for_sha(repo, sha, runner=None):
    code, output = _run(
        runner,
        ["gh", "pr", "list", "--state", "all", "--search", sha, "--json", "number", "--limit", "1"],
        repo,
    )
    data = _json_or_none(code, output)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0].get("number")
    return None
