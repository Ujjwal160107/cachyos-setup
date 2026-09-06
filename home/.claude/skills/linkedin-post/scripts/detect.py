"""Repo-shape detection. Every function degrades instead of raising."""

import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

CONVENTIONAL = re.compile(r"^(\w+)(\([^)]*\))?!?: .+")

WORKSPACE_MANIFESTS = (
    "pnpm-workspace.yaml",
    "lerna.json",
    "turbo.json",
    "nx.json",
    "go.work",
    "settings.gradle",
)

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".tf": "terraform",
}

SKIP_DIRECTORIES = {
    ".git", "node_modules", "vendor", "target", "dist", "build",
    "__pycache__", ".venv", "venv", ".next", ".terraform",
}


# --- Filesystem seam -------------------------------------------------------
# Every filesystem access in this module goes through one of these helpers.
# Path.is_dir()/is_file()/exists() only swallow ENOENT/ENOTDIR/EBADF/ELOOP --
# they genuinely raise PermissionError (EACCES) on a restrictive ACL, and
# iterdir() can fail mid-iteration. Routing every call through this seam means
# a single unreadable entry prunes exactly that entry and nothing else, instead
# of aborting a loop and silently truncating results already collected.
#
# The guards catch OSError only (PermissionError is an OSError subclass).
# Bare Exception would swallow TypeError/AttributeError/KeyError -- programming
# errors, which must still propagate.


def safe_is_dir(path):
    """True if path is a directory, False on any filesystem error."""
    try:
        return path.is_dir()
    except OSError:
        return False


def safe_is_file(path):
    """True if path is a regular file, False on any filesystem error."""
    try:
        return path.is_file()
    except OSError:
        return False


def safe_is_symlink(path):
    """True if path is a symlink, False on any filesystem error."""
    try:
        return path.is_symlink()
    except OSError:
        return False


def _safe_exists(path):
    """True if path exists, False on any filesystem error."""
    try:
        return path.exists()
    except OSError:
        return False


def safe_iterdir(path):
    """Sorted children of path, empty list on any filesystem error."""
    try:
        return sorted(path.iterdir())
    except OSError:
        return []


def safe_read_text(path):
    """Text content of path, empty string on any filesystem error."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def run_git(args, repo):
    """Run git, returning stdout or None on any failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def default_branch(repo):
    head = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], repo)
    if head:
        head = head.strip()
        prefix = "refs/remotes/origin/"
        if head.startswith(prefix):
            head = head[len(prefix):]
        return head
    for candidate in ("main", "master", "develop", "trunk"):
        if run_git(["rev-parse", "--verify", "--quiet", candidate], repo):
            return candidate
    return None


def remote_host(repo):
    url = run_git(["remote", "get-url", "origin"], repo)
    if not url:
        return "none"
    url = url.strip().lower()

    # Extract host from URL, prioritizing scheme-based parsing
    host = None
    if "://" in url:
        # Real URL (https://, ssh://, git://, etc.) — use proper parsing, guard against ValueError
        try:
            parsed = urlparse(url)
            host = parsed.hostname or parsed.netloc.split(":")[0]
        except ValueError:
            # Invalid URL (e.g., malformed IPv6) — degrade to other
            host = None
    else:
        # SCP-like form: [user@]host:path
        if ":" in url:
            # Split on last @ to separate optional userinfo from host:path
            if "@" in url:
                after_at = url.rsplit("@", 1)[1]
            else:
                after_at = url
            # Extract host before first :
            candidate_host = after_at.split(":")[0]
            # Only accept if it looks like a hostname: contains dot and not a drive letter
            # (to avoid Windows paths like C:\repos\thing)
            if "." in candidate_host and len(candidate_host) > 1:
                host = candidate_host

    if not host:
        return "other"

    # Strip port if present
    host = host.split(":")[0]

    # Match forge by checking domain patterns and first label for enterprise
    def matches_forge(host, forge):
        """Check if host matches a forge (github, gitlab, bitbucket)."""
        # Direct public domain match
        if host == forge + ".com" or host == forge + ".org":
            return True
        # Subdomain match (e.g., github.example.com ends with .github.com)
        if host.endswith("." + forge + ".com") or host.endswith("." + forge + ".org"):
            return True
        # Enterprise match: first label is the forge name (e.g., github.example.com)
        first_label = host.split(".")[0]
        if first_label == forge:
            return True
        return False

    if matches_forge(host, "github"):
        return "github"
    if matches_forge(host, "gitlab"):
        return "gitlab"
    if matches_forge(host, "bitbucket"):
        return "bitbucket"

    return "other"


def commit_convention(repo, sample=50):
    log = run_git(["log", "-n", str(sample), "--no-merges", "--pretty=format:%s"], repo)
    if not log:
        return "freeform"
    subjects = [line for line in log.splitlines() if line.strip()]
    if not subjects:
        return "freeform"
    matched = sum(1 for subject in subjects if CONVENTIONAL.match(subject))
    return "conventional" if matched * 2 > len(subjects) else "freeform"


def author_candidates(repo, since):
    log = run_git(
        ["log", "--since", since, "--no-merges", "--pretty=format:%aE"], repo
    )
    if not log:
        return []
    counts = Counter(line.strip().lower() for line in log.splitlines() if line.strip())
    return [
        {"email": email, "commits": count}
        for email, count in counts.most_common()
    ]


def _languages_under(directory):
    """Count languages under directory, pruning unreadable subtrees.

    Walks explicitly instead of using rglob: an OSError raised part-way
    through a generator ends the whole generator, so one unreadable entry
    would truncate the rest of the walk and silently drop languages from
    directories that were never visited. Here an unreadable directory prunes
    only its own subtree and the walk continues everywhere else.

    Symlinked directories are not descended into, matching rglob's default
    (recurse_symlinks=False) and keeping a symlink cycle from looping forever.
    """
    counts = Counter()
    stack = [directory]
    while stack:
        for child in safe_iterdir(stack.pop()):
            if child.name in SKIP_DIRECTORIES:
                continue
            if safe_is_dir(child):
                if not safe_is_symlink(child):
                    stack.append(child)
                continue
            if safe_is_file(child):
                language = LANGUAGE_BY_SUFFIX.get(child.suffix)
                if language:
                    counts[language] += 1
    return [language for language, _ in counts.most_common(3)]


def _workspace_package_paths(repo):
    """Directories that look like workspace packages, relative to the repo root.

    Every filesystem call goes through the safe seam, so a failure at either
    level prunes exactly one candidate: an unreadable child skips that child
    only, and an unreadable grandchild skips that grandchild only -- its
    siblings, and every later child, are still visited.
    """
    paths = []
    for child in safe_iterdir(repo):
        if child.name in SKIP_DIRECTORIES or not safe_is_dir(child):
            continue
        for grandchild in safe_iterdir(child):
            if grandchild.name in SKIP_DIRECTORIES or not safe_is_dir(grandchild):
                continue
            if _languages_under(grandchild):
                paths.append("{}/{}".format(child.name, grandchild.name))
    return paths


def _top_level_code_areas(repo):
    """Areas for the top-level directories that actually contain code.

    DESIGN.md §4's middle tier, between workspace manifests and the single
    root area. Without it `area_count` is 1 for every repository that is not a
    declared monorepo, which is most of them, and §7.3's first complexity
    signal ("areas crossed") is constant and therefore dead.

    A directory qualifies when the language walk under it finds anything, so
    `docs/` and `.github/` drop out on their own rather than needing a
    name list. SKIP_DIRECTORIES still prunes vendored trees, and every
    filesystem call goes through the safe seam, so an unreadable directory
    costs exactly itself.
    """
    areas = []
    for child in safe_iterdir(repo):
        if child.name in SKIP_DIRECTORIES or not safe_is_dir(child):
            continue
        languages = _languages_under(child)
        if languages:
            areas.append(
                {"name": child.name, "kind": "directory", "languages": languages}
            )
    return areas


def detect_areas(repo):
    """Detect areas in repo, degrading on any filesystem error."""
    try:
        repo = Path(repo)
        is_monorepo = any(
            _safe_exists(repo / manifest) for manifest in WORKSPACE_MANIFESTS
        )

        if not is_monorepo:
            cargo = repo / "Cargo.toml"
            if _safe_exists(cargo) and "[workspace]" in safe_read_text(cargo):
                is_monorepo = True

        if is_monorepo:
            packages = _workspace_package_paths(repo)
            if packages:
                return [
                    {
                        "name": name,
                        "kind": "workspace-package",
                        "languages": _languages_under(repo / name),
                    }
                    for name in packages
                ]

        directories = _top_level_code_areas(repo)
        if directories:
            return directories

        # Flat repo: no code below the root, or nothing readable there.
        return [{"name": ".", "kind": "root", "languages": _languages_under(repo)}]
    except OSError:
        # Backstop for the module's no-raise contract. Every filesystem call
        # above already goes through the safe seam, so nothing here is expected
        # to reach this handler -- it exists so a future edit cannot break the
        # public promise of this entry point by accident.
        return [{"name": ".", "kind": "root", "languages": []}]
