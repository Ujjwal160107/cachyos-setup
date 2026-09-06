"""Commit collection and signal extraction."""

import re
from datetime import datetime

try:
    from scripts.detect import run_git, safe_is_dir, safe_is_file, safe_iterdir, safe_read_text, safe_is_symlink, SKIP_DIRECTORIES
except ImportError:  # running as `python scripts/harvest.py`
    from detect import run_git, safe_is_dir, safe_is_file, safe_iterdir, safe_read_text, safe_is_symlink, SKIP_DIRECTORIES

RECORD = "\x1e"
UNIT = "\x1f"

TEST_DIRECTORY_NAMES = {"test", "tests", "spec", "specs", "__tests__", "testing"}
TEST_FILENAME = re.compile(
    r"(^test_)|(_test\.)|(\.test\.)|(_spec\.)|(\.spec\.)|(Test\.\w+$)|(Tests\.\w+$)"
)

# A figure is meaningful when it carries a unit, a multiplier, a percent sign,
# a decimal point, or is at least three digits. Bare "2" is noise.
# Use (?!\w) negative lookahead to reject following word characters while allowing %.
NUMBER = re.compile(
    r"\b\d[\d,]*\.?\d*\s?(?:ms|s|m|h|kb|mb|gb|tb|k|x|%|req/s|rps|qps|bp)(?!\w)"
    r"|\b\d[\d,]*\.\d+\b"
    r"|\b\d{3,}\b",
    re.IGNORECASE,
)

REVERT = re.compile(r"^revert[\s:\"']", re.IGNORECASE)
CONVENTIONAL_TYPE = re.compile(r"^(\w+)(\([^)]*\))?!?:")

# A git trailer is `Token: value` where the token is one unbroken run of
# letters and hyphens, and trailers live in the body's final paragraph
# (`Co-Authored-By:`, `Signed-off-by:`, `Reviewed-by:`, `Fixes:`). Same shape
# git-interpret-trailers uses.
TRAILER_LINE = re.compile(r"^[A-Za-z][A-Za-z-]*:\s")


def strip_trailers(body):
    """Return body without its trailing block of git trailers.

    Trailers are commit metadata, not narrative, and their text was reaching
    `numbers_found`: a `Co-Authored-By: Claude Opus 4.8 (1M context)` trailer
    contributed "4.8" and "1M" to a real run, which then fed the x2
    Concrete-numbers criterion in rubric.md with figures that measure nothing.
    Any repository that signs its commits does this to itself, this one
    included.

    Only the final paragraph is considered, and inside it only the
    trailer-shaped lines are dropped -- prose sharing that paragraph survives,
    which matters because a trailer is often appended straight onto the last
    line of a body with no blank line before it. Prose containing a colon
    ("the fix: stop retrying after 3 attempts") is not trailer-shaped in the
    first place, since the token before the colon may not contain a space.

    What this deliberately does not do is scan the whole body: a mid-body
    "Note: 400ms was the budget" is prose in trailer clothing, and dropping it
    would cost real evidence. Restricting the rule to the final paragraph
    keeps that line, at the price of missing a trailer written somewhere no
    git tool would look for one.
    """
    lines = (body or "").rstrip().splitlines()
    start = len(lines)
    while start > 0 and lines[start - 1].strip():
        start -= 1
    kept = [line for line in lines[start:] if not TRAILER_LINE.match(line)]
    return "\n".join(lines[:start] + kept).strip()


def is_test_file(path):
    parts = path.replace("\\", "/").split("/")
    if TEST_DIRECTORY_NAMES.intersection(parts[:-1]):
        return True
    return bool(TEST_FILENAME.search(parts[-1]))


def extract_numbers(text):
    if not text:
        return []
    found = []
    for match in NUMBER.finditer(text):
        value = match.group(0).strip()
        if value not in found:
            found.append(value)
    return found


def _normalize_path(path):
    """Normalize git rename paths to destination."""
    normalized = path
    if " => " in path:
        # Check if it's a brace rename: "dir/{old => new}"
        if "{" in path and "}" in path:
            # Extract the part before {, the new name, and the part after }
            before_brace = path[: path.find("{")]
            after_brace = path[path.find("}") + 1 :]
            brace_content = path[path.find("{") + 1 : path.find("}")]
            if " => " in brace_content:
                _, new = brace_content.split(" => ", 1)
                normalized = before_brace + new + after_brace
        else:
            # Simple rename: "old => new"
            _, normalized = path.split(" => ", 1)

    # Collapse consecutive slashes and strip leading slash
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized


def _window_args(since, until, author):
    args = ["--no-merges", "--since", since]
    if until:
        args += ["--until", until]
    if author:
        # git's --author is a CASE-SENSITIVE basic regular expression, but
        # email case is not meaningful and the values being compared come from
        # sources that disagree about it: detect.author_candidates lowercases,
        # GitHub noreply addresses preserve username case
        # (12345+Name@users.noreply.github.com), and one person's git config
        # can differ in case from the commits they already authored on another
        # machine. A case-sensitive filter turns any of those mismatches into
        # an empty result set with no error -- the tool tells the author they
        # shipped nothing. Verified against git 2.52.0: `--author` with a
        # lowercased mixed-case address matches zero commits, and
        # --regexp-ignore-case matches them all while still excluding a
        # genuinely absent author.
        args += ["--regexp-ignore-case", "--author", author]
    return args


def _added_by_sha(repo, since, until, author):
    """Map each SHA to the paths that commit created (git's A filter)."""
    output = run_git(
        ["log"]
        + _window_args(since, until, author)
        + ["--diff-filter=A", "--name-only", "--pretty=format:" + RECORD + "%H"],
        repo,
    )
    if not output:
        return {}
    mapping = {}
    for chunk in output.split(RECORD):
        if not chunk.strip():
            continue
        sha, _, paths = chunk.partition("\n")
        mapping[sha.strip()] = [line.strip() for line in paths.splitlines() if line.strip()]
    return mapping


def collect_commits(repo, since, until, author):
    """Collect commits using three separate passes to avoid body-injection attacks."""
    # Pass A: metadata (subject, body) with NUL-separated records, no numstat
    metadata_args = (
        ["log", "-z"]
        + _window_args(since, until, author)
        + ["--pretty=format:" + "%H" + UNIT + "%aI" + UNIT + "%aE" + UNIT + "%s" + UNIT + "%b"]
    )
    metadata_output = run_git(metadata_args, repo)

    # Pass B: stats only (numstat format), no body
    stats_args = (
        ["log"]
        + _window_args(since, until, author)
        + ["--numstat", "--pretty=format:" + RECORD + "%H"]
    )
    stats_output = run_git(stats_args, repo)

    # Pass C: added files (rename-detection aware)
    added_by_sha = _added_by_sha(repo, since, until, author)

    # Parse metadata (Pass A)
    metadata_by_sha = {}
    if metadata_output:
        for chunk in metadata_output.split("\0"):
            if not chunk.strip():
                continue
            fields = chunk.split(UNIT, 4)  # maxsplit 4 preserves UNIT in body
            if len(fields) >= 4:
                sha, date, email, subject = fields[0], fields[1], fields[2], fields[3]
                body = fields[4] if len(fields) > 4 else ""
                metadata_by_sha[sha] = {
                    "sha": sha,
                    "date": date[:10],
                    "email": email.lower(),
                    "subject": subject,
                    "body": body.strip(),
                }

    # Parse stats (Pass B)
    stats_by_sha = {}
    if stats_output:
        for chunk in stats_output.split(RECORD):
            if not chunk.strip():
                continue
            lines = chunk.split("\n")
            if not lines:
                continue
            sha = lines[0].strip()
            files, insertions, deletions = [], 0, 0
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) == 3 and (parts[0].isdigit() or parts[0] == "-"):
                    added, removed, path = parts
                    path = _normalize_path(path)
                    files.append(path)
                    if added.isdigit():
                        insertions += int(added)
                    if removed.isdigit():
                        deletions += int(removed)
            stats_by_sha[sha] = {
                "files": files,
                "insertions": insertions,
                "deletions": deletions,
            }

    # Combine all three passes
    commits = []
    for sha, meta in metadata_by_sha.items():
        stats = stats_by_sha.get(sha, {"files": [], "insertions": 0, "deletions": 0})
        commit = {
            **meta,
            **stats,
            "added": added_by_sha.get(sha, []),
        }
        commits.append(commit)

    return commits


def _area_for(path, areas):
    normalised = path.replace("\\", "/")
    best = None
    for area in areas:
        name = area["name"]
        if name == ".":
            best = best or "."
        elif normalised.startswith(name + "/"):
            if best is None or len(name) > len(best):
                best = name
    return best


def commit_signals(commits, areas):
    reverts = sum(1 for c in commits if REVERT.match(c["subject"]))

    fix_after_feat = 0
    seen_feature_files = set()
    # Iterate in reverse (oldest-first) so feat is seen before fix
    for commit in reversed(commits):
        match = CONVENTIONAL_TYPE.match(commit["subject"])
        kind = match.group(1).lower() if match else ""
        if kind in ("feat", "feature"):
            seen_feature_files.update(commit["files"])
        elif kind == "fix" and seen_feature_files.intersection(commit["files"]):
            fix_after_feat += 1

    touched_areas = []
    for commit in commits:
        for path in commit["files"]:
            area = _area_for(path, areas)
            if area and area not in touched_areas:
                touched_areas.append(area)

    dates = sorted(c["date"] for c in commits if c.get("date"))
    span_days = 0
    if len(dates) >= 2:
        first = datetime.strptime(dates[0], "%Y-%m-%d")
        last = datetime.strptime(dates[-1], "%Y-%m-%d")
        span_days = (last - first).days

    numbers = []
    for commit in commits:
        narrative = commit["subject"] + " " + strip_trailers(commit["body"])
        for value in extract_numbers(narrative):
            if value not in numbers:
                numbers.append(value)

    all_files = {path for commit in commits for path in commit["files"]}
    added_files = {path for commit in commits for path in commit.get("added", [])}

    return {
        "reverts": reverts,
        "fix_after_feat": fix_after_feat,
        "test_files_touched": sum(1 for path in all_files if is_test_file(path)),
        "areas": touched_areas,
        "area_count": len(touched_areas),
        "new_files": len(added_files),
        "span_days": span_days,
        "numbers_found": numbers[:20],
    }


DOC_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")
EXCERPT_LIMIT = 4000
MAX_DOCS = 12

DOC_SEARCH_DIRECTORIES = ("docs", "doc", "rfcs", "adr", "decisions", "design", ".github")

DOC_KIND_RULES = (
    ("adr", ("adr", "decisions")),
    ("rfc", ("rfc",)),
    ("design", ("design",)),
    ("spec", ("spec",)),
    ("plan", ("plan",)),
)

STOPWORDS = {
    "feat", "fix", "docs", "chore", "refactor", "test",
    "update", "updates", "change", "changes",
    "add", "adds", "added", "remove", "removes",
    "design", "spec", "plan", "notes", "readme",
    "main", "master",
}


def classify_doc(path):
    lowered = path.replace("\\", "/").lower()
    name = lowered.rsplit("/", 1)[-1]
    if name in ("readme.md", "readme.rst", "readme.txt"):
        return "readme"
    for kind, tokens in DOC_KIND_RULES:
        if any(token in lowered for token in tokens):
            return kind
    return "doc"


def _slug_tokens(text):
    return {
        token
        for token in re.split(r"[^a-z0-9]+", text.lower())
        if len(token) >= 4 and not token.isdigit() and token not in STOPWORDS
    }


def _read_excerpt(repo, relative):
    content = safe_read_text(repo / relative)
    return content[:EXCERPT_LIMIT]


def find_docs(repo, commits, hints):
    """Find design docs, touched and hint-matched, with graceful error handling.

    Two passes: touched docs (from commits) and name-matched docs (from hints).
    If a directory is unreadable, only that subtree is pruned; the walk continues
    elsewhere. Returns up to MAX_DOCS results, preferring touched docs over matches.
    """
    touched = {}
    matched = {}

    # Pass 1: Collect all markdown files touched by commits
    for commit in commits:
        for path in commit["files"]:
            if path.lower().endswith(DOC_SUFFIXES):
                touched[path] = None

    # Pass 2: Search directories for hint-matched docs (only if hints provided)
    hint_tokens = set()
    for hint in hints:
        hint_tokens |= _slug_tokens(hint)

    if hint_tokens:
        for directory in DOC_SEARCH_DIRECTORIES:
            root = repo / directory
            if not safe_is_dir(root):
                continue
            # Explicit stack walk instead of rglob: one unreadable entry only prunes
            # that entry's subtree, not the entire search. Skip vendored
            # directories. The symlink check only prunes descent into
            # symlinked *directories* (preventing cycles); a symlinked
            # regular file is still eligible to match, matching
            # _languages_under's shape in detect.py.
            stack = [root]
            while stack:
                current = stack.pop()
                for child in safe_iterdir(current):
                    if child.name in SKIP_DIRECTORIES:
                        continue
                    if safe_is_dir(child):
                        if not safe_is_symlink(child):
                            stack.append(child)
                        continue
                    if not safe_is_file(child):
                        continue
                    if not child.name.lower().endswith(DOC_SUFFIXES):
                        continue
                    relative = child.relative_to(repo).as_posix()
                    if relative in touched or relative in matched:
                        continue
                    if _slug_tokens(child.stem) & hint_tokens:
                        matched[relative] = None

    # Merge results: touched first (stronger signal), then matched, up to MAX_DOCS
    merged = list(touched.keys())
    for path in sorted(matched.keys()):
        if path not in merged:
            merged.append(path)
    merged = merged[:MAX_DOCS]

    return [
        {
            "path": path,
            "kind": classify_doc(path),
            "excerpt": _read_excerpt(repo, path),
        }
        for path in sorted(merged)
    ]
