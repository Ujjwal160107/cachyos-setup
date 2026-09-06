#!/usr/bin/env python3
"""Collect recent authored work from any git repo as one JSON document.

Usage:
    python scripts/harvest.py [--since 14d] [--author EMAIL] [--repo PATH] [--json PATH]
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts import cluster, collect, detect, github
except ImportError:  # running as `python scripts/harvest.py`
    import cluster
    import collect
    import detect
    import github

RELATIVE = re.compile(r"^(\d+)([dwm])$")
DAYS_PER_UNIT = {"d": 1, "w": 7, "m": 30}

# One `git rev-list` runs per local branch, each with a 30-second timeout, and
# all of it happens before the tool emits anything. A repo with hundreds of
# stale branches would otherwise pay hundreds of subprocesses for signal it
# almost never uses. Branches are listed newest-commit-first, so the cap keeps
# the ones plausibly holding work inside the window.
MAX_BRANCHES = 50

# DESIGN.md §4 PR-linkage strategy (c) costs one `gh pr list` per cluster that
# carries no (#N) suffix, plus a `gh pr view` when it resolves. A freeform repo
# clusters per author-day, so a long window can propose dozens of clusters and
# the per-cluster bound alone would still leave the total unbounded -- the same
# fan-out shape already bounded by MAX_DOCS, MAX_COMMENTS and MAX_BRANCHES.
# Clusters are proposed newest-first, so the cap keeps the most recent work.
MAX_PR_LOOKUPS = 20


def parse_since(value, today=None):
    today = today or date.today()
    match = RELATIVE.match(value.strip().lower())
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        return (today - timedelta(days=amount * DAYS_PER_UNIT[unit])).isoformat()
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError(
            "--since must be Nd, Nw, Nm, or YYYY-MM-DD (got {!r})".format(value)
        )


def _branch_commits(repo, default_branch):
    """Map each non-default local branch to the SHAs unique to it.

    SHAs come back from `git rev-list` at full 40-character length and stay
    that way: cluster.propose_clusters matches them against commit["sha"],
    which collect.collect_commits fills from git's %H. Abbreviating here would
    make every branch cluster silently fail to match.

    Bounded at MAX_BRANCHES branches queried -- counted per branch examined,
    not per branch kept, so a repo full of already-merged branches cannot slip
    past the cap.
    """
    if not default_branch:
        return {}
    listing = detect.run_git(
        ["branch", "--format=%(refname:short)", "--sort=-committerdate"], repo
    )
    if not listing:
        return {}
    mapping = {}
    examined = 0
    for name in (line.strip() for line in listing.splitlines()):
        if not name or name == default_branch:
            continue
        # A detached HEAD adds a `(HEAD detached at abc1234)` pseudo-entry to
        # the listing. It is not a rev, so querying it burns a subprocess and a
        # slot in the budget for a call that can only fail.
        if name.startswith("("):
            continue
        if examined >= MAX_BRANCHES:
            break
        examined += 1
        revisions = detect.run_git(
            ["rev-list", "{}..{}".format(default_branch, name)], repo
        )
        if revisions:
            shas = [line.strip() for line in revisions.splitlines() if line.strip()]
            if shas:
                mapping[name] = shas
    return mapping


def _capabilities(host, runner):
    """Resolve the three independent capability facts DESIGN.md §5.2 names.

    They are genuinely distinct, and conflating them makes a degraded run
    report the wrong reason: an authenticated gh pointed at a GitLab remote has
    working auth, and only the host disqualifies PR enrichment.
    """
    gh_ok = github.gh_available(runner)
    gh_auth = gh_ok and github.gh_authenticated(runner)
    pr_enrichment = gh_auth and host == "github"
    return gh_ok, gh_auth, pr_enrichment


def build(repo, since, author, runner=None):
    repo = Path(repo)
    warnings = []

    default_branch = detect.default_branch(repo)
    if not default_branch:
        warnings.append("No default branch found; branch clustering disabled.")

    host = detect.remote_host(repo)
    convention = detect.commit_convention(repo)
    candidates = detect.author_candidates(repo, since)

    # This .lower() is NORMALISATION FOR REPORTING, not the case-insensitivity
    # guarantee. detect.author_candidates lowercases the emails it returns, so
    # `selected` has to be lowercased too for the `known` membership check
    # below -- and hence the "no commits in this window" warning -- to mean
    # anything. The guarantee that a case difference cannot empty the document
    # lives one layer down, in collect._window_args, which passes
    # --regexp-ignore-case to git. Do not delete either one on the grounds that
    # the other exists: without the git flag a mixed-case address silently
    # matches zero commits, and without this .lower() a mixed-case address
    # raises a false "no commits" warning on a run that did find commits.
    selected = (author or detect.run_git(["config", "user.email"], repo) or "").strip().lower()
    if not selected:
        selected = candidates[0]["email"] if candidates else ""
        if selected:
            warnings.append(
                "git config user.email is unset; defaulting to the most active author "
                "in the window ({}).".format(selected)
            )

    known = {candidate["email"] for candidate in candidates}
    if selected and selected not in known:
        warnings.append(
            "Author {} has no commits in this window. Authors present: {}. "
            "Re-run with --author to pick one.".format(
                selected, ", ".join(sorted(known)) or "none"
            )
        )

    gh_ok, gh_auth, pr_enrichment = _capabilities(host, runner)
    visibility = github.repo_visibility(repo, runner) if pr_enrichment else "unknown"

    if not gh_ok:
        warnings.append(
            "gh CLI unavailable: no PR bodies, review comments, or visibility detection. "
            "Redaction posture defaults to stack-only."
        )
    elif not gh_auth:
        warnings.append(
            "gh CLI is present but not authenticated: no PR bodies, review comments, "
            "or visibility detection. Run 'gh auth login'. "
            "Redaction posture defaults to stack-only."
        )
    elif host == "none":
        # detect.remote_host returns "none" when there is no origin at all, so
        # "the host is not GitHub" would name the wrong missing signal.
        warnings.append(
            "No git remote is configured: PR bodies and review comments are "
            "unavailable. Redaction posture defaults to stack-only."
        )
    elif host != "github":
        warnings.append(
            "Remote host is '{}': PR enrichment is GitHub-only.".format(host)
        )
    elif visibility == "unknown":
        warnings.append(
            "gh could not read repo visibility; treating the repo as private. "
            "Redaction posture defaults to stack-only."
        )

    areas = detect.detect_areas(repo)
    commits = collect.collect_commits(repo, since, None, selected or None)
    proposed = cluster.propose_clusters(
        commits, default_branch, _branch_commits(repo, default_branch), convention
    )

    clusters = []
    searches = 0
    searches_skipped = 0
    for item in proposed:
        hints = [item["title"], item["id"]]
        pull = None
        if pr_enrichment:
            number = None
            if item["id"].startswith("pr-"):
                # DESIGN.md §4 PR linkage (a): the (#N) subject suffix, which
                # cluster.propose_clusters has already parsed into the id.
                number = int(item["id"][3:])
            elif item["id"].startswith("branch-") and item["commits"]:
                # DESIGN.md §4 PR linkage (c): ask gh which PR carries the
                # commit. Without this a branch cluster on an authed GitHub
                # repo reports pr: null even when a PR exists, losing the
                # review threads §7.1 names as the primary Tension evidence.
                #
                # Restricted to `branch-*` clusters on purpose. The resolved
                # PR is attached to the WHOLE cluster, so the probe is only
                # sound when every commit in it plausibly belongs to one PR --
                # which is what a branch cluster is. A coarse cluster (an
                # author-day, an ISO week) is a mechanical grouping instead:
                # five commits sharing a scope and a week routinely come from
                # five separate PRs, and attaching one of them to all five
                # hands four of them a PR body, a diffstat, review threads and
                # a doc-search hint describing work they did not do. That is
                # false evidence for the two criteria rubric.md weights most,
                # and it breaks SKILL.md stage 5's rule that every factual
                # claim trace to a commit, PR body or doc. Those clusters keep
                # `pr: null`, which §5.2 blesses as unavailable, not an error.
                #
                # One search per cluster, never one per commit. Every commit
                # in a branch cluster is on the same branch and so resolves to
                # the same PR, so which one is probed does not change the
                # answer.
                if searches < MAX_PR_LOOKUPS:
                    searches += 1
                    number = github.pr_number_for_sha(
                        repo, item["commits"][0]["sha"], runner
                    )
                else:
                    searches_skipped += 1
            if number is not None:
                pull = github.fetch_pr(repo, number, runner)
                if pull:
                    hints.append(pull.get("title", ""))

        clusters.append(
            {
                "id": item["id"],
                "strategy": item["strategy"],
                "title": item["title"],
                "pr": pull,
                "commits": item["commits"],
                "docs": collect.find_docs(repo, item["commits"], hints),
                "signals": collect.commit_signals(item["commits"], areas),
            }
        )

    if searches_skipped:
        # A cap that binds silently is indistinguishable from a repo that
        # genuinely has no PRs. DESIGN.md §10 item 5 requires the coverage note
        # to state which signals were unavailable, and §14 criterion 2 requires
        # naming every one of them, so this truncation has to announce itself.
        warnings.append(
            "PR lookup by commit is capped at {} clusters per run; {} older "
            "cluster(s) were left unenriched and report pr: null even if a PR "
            "exists. Narrow --since to bring them inside the cap.".format(
                MAX_PR_LOOKUPS, searches_skipped
            )
        )

    until = date.today().isoformat()
    # A --since in the future would otherwise report a negative window.
    window_days = max(
        0,
        (
            datetime.strptime(until, "%Y-%m-%d") - datetime.strptime(since, "%Y-%m-%d")
        ).days,
    )

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "repo_root": str(repo),
            "repo_name": repo.name,
            "host": host,
            "visibility": visibility,
            "default_branch": default_branch,
            "window": {"since": since, "until": until, "days": window_days},
            "author": {"selected": selected, "candidates": candidates},
            "commit_convention": convention,
            "capabilities": {
                "gh": gh_ok,
                "gh_auth": gh_auth,
                "pr_enrichment": pr_enrichment,
            },
            "warnings": warnings,
        },
        "areas": areas,
        "clusters": clusters,
    }


def write_stdout(text):
    """Write text to stdout as UTF-8, whatever the platform's locale codec is.

    On Windows, sys.stdout falls back to the locale codec (cp1252 here) as soon
    as it is not a console -- a pipe or a shell redirect is enough. A plain
    print() of ensure_ascii=False JSON then raises UnicodeEncodeError on the
    first non-ASCII character, and a single arrow in a commit body kills the
    default, no --json run. Found by piping a real run of this repo, not by
    reading the code. The --json path never had the bug because write_text
    names its encoding explicitly; stdout has to do the same.

    Falls back to print() when stdout has no binary buffer, which is the case
    whenever it has been replaced by a text-only stand-in.
    """
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:
        print(text)
        return
    sys.stdout.flush()  # keep ordering with any text-mode writes
    stream.write(text.encode("utf-8") + b"\n")
    stream.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="14d", help="Nd, Nw, Nm, or YYYY-MM-DD")
    parser.add_argument("--author", default=None, help="Author email to filter on")
    parser.add_argument("--repo", default=".", help="Path to the repository")
    parser.add_argument("--json", dest="out", default=None, help="Write JSON here")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    root = detect.run_git(["rev-parse", "--show-toplevel"], repo)
    if not root:
        print("error: {} is not inside a git repository".format(repo), file=sys.stderr)
        return 2

    try:
        since = parse_since(args.since)
    except ValueError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2

    document = build(Path(root.strip()), since, args.author)
    payload = json.dumps(document, indent=2, ensure_ascii=False)

    if args.out:
        # A missing parent directory or a read-only location is a user mistake,
        # not a crash: every other failure path here exits 2 with a message.
        try:
            Path(args.out).write_text(payload, encoding="utf-8")
        except OSError as error:
            print(
                "error: could not write {}: {}".format(args.out, error),
                file=sys.stderr,
            )
            return 2
        write_stdout("wrote {}".format(args.out))
    else:
        write_stdout(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
