"""Mechanical clustering. The agent re-clusters semantically afterwards."""

import re
from datetime import datetime

PR_SUFFIX = re.compile(r"\(#(\d+)\)\s*$")
CONVENTIONAL_HEAD = re.compile(r"^(\w+)(?:\(([^)]*)\))?!?:\s*(.+)$")

# Fixed, deterministic fallback week label used when a commit's `date`
# cannot be parsed as YYYY-MM-DD (see _iso_week). Using one sentinel value
# rather than the raw bad string keeps every malformed-date commit in a
# given scope in the same cluster, run after run.
UNKNOWN_WEEK = "invalid-date"


def _clean_title(subject):
    subject = PR_SUFFIX.sub("", subject).strip()
    match = CONVENTIONAL_HEAD.match(subject)
    return match.group(3).strip() if match else subject


def _scope(subject):
    match = CONVENTIONAL_HEAD.match(subject)
    if match and match.group(2):
        return match.group(2)
    return "general"


def _iso_week(date_string):
    """ISO year+week for a commit's `date` (expected format YYYY-MM-DD).

    `collect_commits` sets `date` from `date[:10]` of git's `%aI`
    (scripts/collect.py:137). For any commit made through normal
    `git commit`, `%aI` is a strict ISO-8601 timestamp, so this always
    succeeds. But a repository can contain a commit object with a
    corrupted author line -- verified empirically by building one with
    `git hash-object -t commit -w --literally` (which bypasses git's own
    fsck validation). For such a commit, git log's `%aI` placeholder does
    not expand at all and comes through verbatim, so `collect_commits`
    ends up setting `date` to the literal text "%aI" rather than a real
    date; slicing that to 10 characters is still "%aI", and
    `datetime.strptime` raises ValueError on it. An empty `date` is
    guarded the same way -- scripts/collect.py:221 already treats a
    missing `date` as a possibility (`if c.get("date")`), and an empty
    string or None both fail to parse here too (TypeError for None).
    Degrade to a fixed bucket instead of letting one bad commit's date
    crash clustering for the whole run.
    """
    try:
        parsed = datetime.strptime(date_string, "%Y-%m-%d").isocalendar()
    except (ValueError, TypeError):
        return UNKNOWN_WEEK
    return "{}W{:02d}".format(parsed[0], parsed[1])


def _key_for(commit, branch_by_sha, convention):
    match = PR_SUFFIX.search(commit["subject"])
    if match:
        return "pr-{}".format(match.group(1)), "pr-suffix"

    branch = branch_by_sha.get(commit["sha"])
    if branch:
        return "branch-{}".format(branch), "branch"

    if convention == "conventional":
        return (
            "scope-{}-{}".format(_scope(commit["subject"]), _iso_week(commit["date"])),
            "scope-week",
        )

    return "day-{}".format(commit["date"]), "day"


def _earliest_commit(commits):
    """Pick the commit that opens the story, as the cluster's title source.

    `collect_commits` returns commits newest-first (git log order). Taking
    commits[0] -- the first one encountered while grouping -- would take
    the NEWEST commit in a cluster as the title source, typically a late
    fixup like "fix: typo", which makes a poor label for the story. We
    want the chronologically earliest commit instead: the one that started
    it.

    Deterministic rule: the commit with the minimum `date` wins. `date` is
    day granularity only, so commits sharing the same date can't be
    ordered by date alone; on a tie, keep advancing to whichever tied
    commit appears LATER in the newest-first input list -- later position
    in a newest-first list means older, so this always resolves ties the
    same way for a given input, never "whichever sorts first by
    accident". This is a single left-to-right scan, not a sort, so no
    sort-stability assumptions are involved either.
    """
    earliest = commits[0]
    for candidate in commits[1:]:
        if candidate["date"] <= earliest["date"]:
            earliest = candidate
    return earliest


def propose_clusters(commits, default_branch, branch_commits, convention):
    # default_branch is part of the interface Task 7 calls (and the plan's
    # binding signature) but is not needed by any strategy implemented
    # here -- branch attribution comes entirely from branch_commits, which
    # Task 7 already computes relative to the default branch. Left unused
    # deliberately rather than dropped, to keep that interface stable.
    branch_by_sha = {}
    for branch, shas in (branch_commits or {}).items():
        for sha in shas:
            branch_by_sha.setdefault(sha, branch)

    grouped_commits = {}
    strategies = {}
    order = []
    for commit in commits:
        key, strategy = _key_for(commit, branch_by_sha, convention)
        if key not in grouped_commits:
            grouped_commits[key] = []
            strategies[key] = strategy
            order.append(key)
        grouped_commits[key].append(commit)

    clusters = []
    for key in order:
        cluster_commits = grouped_commits[key]
        clusters.append(
            {
                "id": key,
                "strategy": strategies[key],
                "title": _clean_title(_earliest_commit(cluster_commits)["subject"]),
                "commits": cluster_commits,
            }
        )
    return clusters
