# linkedin-post Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repo-agnostic Claude Code skill that scans recent authored work in any git repository, ranks it for LinkedIn post-worthiness, and drafts the strongest post.

**Architecture:** A Python harvest script does all deterministic collection (git history, `gh` PR enrichment, design-doc discovery, mechanical clustering) and emits one JSON document. Markdown skill files then drive the agent's judgment stages (semantic re-clustering, scoring, drafting) by loading only at the stage that needs them. The two halves communicate solely through the JSON contract in `DESIGN.md` §5.2.

**Tech Stack:** Python 3.9+ standard library, `unittest`, git, optional `gh` CLI, Markdown.

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3.9+, standard library only.** No third-party runtime *or* test dependencies. Tests use `unittest`, never `pytest`.
- **Test command:** `python -m unittest discover -s tests -t . -v` run from the repo root.
- **Cross-platform:** Windows, macOS, Linux. Use `pathlib.Path` for all paths. Never use `shell=True`. Always pass `subprocess` arguments as a list.
- **All subprocess calls take `timeout=30`** and must not raise on non-zero exit where `DESIGN.md` §4 defines a fallback.
- **No file in this repo may name or describe a specific private codebase**, its directory layout, its product concepts, or its conventions. Examples use `example-repo`, `services/api`, `dev@example.com`.
- **`SKILL.md` must stay under 500 words** (`DESIGN.md` §11).
- **Never use `@path` file links** in Markdown skill files. They force-load and burn context (`writing-skills` convention).
- **Commit convention:** Conventional Commits. End every commit message body with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- **License:** MIT, copyright Ujjwal.

**Refinement of `DESIGN.md` §11:** the spec lists `scripts/harvest.py` as a single file. Implementation splits it into four modules in the same directory (`detect.py`, `collect.py`, `cluster.py`, `github.py`, orchestrated by `harvest.py`, so five files in total). Python adds a script's own directory to `sys.path`, so plain sibling imports work when run as `python scripts/harvest.py`. §11 was updated accordingly in Task 14.

**Reconciliation note (Task 14).** Every Python code block below now reproduces the shipped file in `scripts/` or `tests/` **verbatim**, and that property is mechanically checkable: extract each block, concatenate the create-block with its append-block where a file is built in two tasks, and diff against the file on disk. All thirteen match.

They did not match when they were first written. This plan was drafted before the code existed, and implementation found bugs the plan's own blocks still contained. Three worth naming, because they are the reason this reconciliation was made a release gate rather than a tidy-up:

- `run_git` and `default_runner` originally omitted `encoding="utf-8", errors="replace"`. On Windows, `subprocess` falls back to the locale codec (cp1252 here), so a single emoji or accented character in a commit body raised `UnicodeDecodeError` — a `ValueError`, not caught by the `(OSError, subprocess.SubprocessError)` tuple, in two functions whose whole contract is never to raise.
- The Task 12 installer test asserted `assertNotIn("local ", self.sh)`. `install.sh`'s own help text contains the line `--local   install to ./.claude/skills in the current directory`, so that assertion could never pass against the script it was written to guard. The shipped test matches a POSIX-illegal `local` *declaration* by regex instead.
- The Task 3 `commit_signals` fixture listed commits oldest-first. `collect_commits` returns them newest-first, which is git log order, and `commit_signals` reverses them on that basis. Run against the shipped module, the plan's fixture asserted `fix_after_feat == 1` and got `0`.

A plan published alongside the code it produced is read as documentation of that code. These blocks are now that.

---

### Task 1: Scaffolding and the temp-repo test harness

Everything downstream is tested against throwaway git repositories. This task builds that harness first.

**Files:**
- Create: `LICENSE`
- Create: `tests/__init__.py` (empty)
- Create: `tests/helpers.py`
- Create: `tests/test_helpers.py`

**Interfaces:**
- Consumes: nothing
- Produces: `tests.helpers.TempRepo` with methods `commit(subject, files=None, body="", date=None, author=None) -> str` (returns full SHA), `branch(name) -> None`, `checkout(name) -> None`, `path` (a `pathlib.Path`), `cleanup() -> None`. Also `tests.helpers.git(args, cwd) -> str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_helpers.py`:

```python
import os
import unittest

from tests.helpers import TempRepo, git


class TestTempRepo(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def test_commit_returns_sha_and_lands_in_log(self):
        sha = self.repo.commit("feat: first", files={"a.txt": "hello"})
        self.assertEqual(len(sha), 40)
        log = git(["log", "--oneline"], self.repo.path)
        self.assertIn("feat: first", log)

    def test_commit_writes_nested_files(self):
        self.repo.commit("feat: nested", files={"services/api/main.py": "x = 1"})
        self.assertTrue((self.repo.path / "services" / "api" / "main.py").exists())

    def test_fixed_date_is_honoured(self):
        """Verify that explicit date= is used, even with ambient GIT_AUTHOR_DATE."""
        old_date = os.environ.get("GIT_AUTHOR_DATE")
        try:
            # Set an ambient date far in the past to verify it's not used
            os.environ["GIT_AUTHOR_DATE"] = "2020-01-01T00:00:00"
            # Commit with an explicit date
            self.repo.commit("feat: dated", date="2026-01-15T10:00:00")
            log = git(["log", "-1", "--pretty=format:%aI"], self.repo.path)
            self.assertTrue(log.startswith("2026-01-15"),
                          f"Commit date {log} was affected by ambient GIT_AUTHOR_DATE")
        finally:
            if old_date is None:
                os.environ.pop("GIT_AUTHOR_DATE", None)
            else:
                os.environ["GIT_AUTHOR_DATE"] = old_date

    def test_branch_and_checkout(self):
        self.repo.commit("feat: base")
        self.repo.branch("feature/x")
        self.repo.commit("feat: on branch")
        self.repo.checkout("main")
        log = git(["log", "--oneline"], self.repo.path)
        self.assertNotIn("on branch", log)

    def test_git_author_email_isolation(self):
        """Verify that GIT_AUTHOR_EMAIL environment variable doesn't override config."""
        # Temporarily set a bogus GIT_AUTHOR_EMAIL in the environment
        old_email = os.environ.get("GIT_AUTHOR_EMAIL")
        try:
            os.environ["GIT_AUTHOR_EMAIL"] = "wrong@example.com"
            sha = self.repo.commit("feat: isolation test", files={"test.txt": "isolated"})
            # Verify the commit uses the configured email, not the environment variable
            log = git(["log", "-1", "--pretty=format:%ae"], self.repo.path)
            self.assertEqual(log.strip(), "dev@example.com")
        finally:
            if old_email is None:
                os.environ.pop("GIT_AUTHOR_EMAIL", None)
            else:
                os.environ["GIT_AUTHOR_EMAIL"] = old_email

    def test_git_author_date_defaults_to_now_not_ambient(self):
        """Verify that without explicit date, commit date is 'now', not the ambient GIT_AUTHOR_DATE."""
        old_date = os.environ.get("GIT_AUTHOR_DATE")
        try:
            # Set an ambient date far in the past
            os.environ["GIT_AUTHOR_DATE"] = "2020-01-01T00:00:00"
            # Commit without an explicit date
            sha = self.repo.commit("feat: default now", files={"test.txt": "now"})
            # Verify the commit date is NOT the ambient 2020 date
            log = git(["log", "-1", "--pretty=format:%aI"], self.repo.path)
            self.assertFalse(log.startswith("2020"),
                           f"Commit date {log} was affected by ambient GIT_AUTHOR_DATE")
        finally:
            if old_date is None:
                os.environ.pop("GIT_AUTHOR_DATE", None)
            else:
                os.environ["GIT_AUTHOR_DATE"] = old_date


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_helpers -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.helpers'`

- [ ] **Step 3: Write the harness**

Create `tests/__init__.py` as an empty file. Create `tests/helpers.py`:

```python
"""Throwaway git repositories for tests. Standard library only."""

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


def _clean_env(extra=None):
    """Return a clean environment for git calls, stripped of git variables."""
    env = os.environ.copy()
    # Remove git environment variables that could interfere with isolation
    for var in [
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_AUTHOR_DATE",
        "GIT_COMMITTER_DATE",
    ]:
        env.pop(var, None)
    if extra:
        env.update(extra)
    return env


def _run_command(command, cwd, env=None):
    """Run a subprocess command and return stdout. Raises on non-zero exit with stderr."""
    if env is None:
        env = _clean_env()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            env=env,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        msg = "{} failed\nstderr: {}\nstdout: {}".format(
            " ".join(command), e.stderr, e.stdout
        )
        raise RuntimeError(msg) from e


def git(args, cwd):
    """Run a git command and return stdout. Raises on non-zero exit."""
    return _run_command(["git"] + args, cwd)


def _force_remove(func, path, _exc_info):
    """Windows marks files under .git read-only, which defeats rmtree."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


class TempRepo:
    """A git repository in a temporary directory, built commit by commit."""

    def __init__(self, default_branch="main"):
        self.path = Path(tempfile.mkdtemp(prefix="lps-test-"))
        git(["init", "-q"], self.path)
        git(["symbolic-ref", "HEAD", "refs/heads/{}".format(default_branch)], self.path)

        git(["config", "user.email", "dev@example.com"], self.path)
        git(["config", "user.name", "Test Dev"], self.path)
        git(["config", "commit.gpgsign", "false"], self.path)
        # Disable global git hooks by pointing to a non-existent directory
        git(["config", "core.hooksPath", str(self.path / ".git-hooks-disabled")], self.path)

    def commit(self, subject, files=None, body="", date=None, author=None):
        """Write files, stage everything, and commit. Returns the full SHA."""
        if files is None:
            files = {"README.md": subject}
        for relative, content in files.items():
            target = self.path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(["add", "-A"], self.path)

        message = subject if not body else "{}\n\n{}".format(subject, body)
        command = ["git", "commit", "-q", "-m", message]
        if author:
            command += ["--author", author]

        extra = {}
        if date:
            extra["GIT_AUTHOR_DATE"] = date
            extra["GIT_COMMITTER_DATE"] = date
        env = _clean_env(extra)

        _run_command(command, self.path, env)
        return git(["rev-parse", "HEAD"], self.path).strip()

    def branch(self, name):
        git(["checkout", "-q", "-b", name], self.path)

    def checkout(self, name):
        git(["checkout", "-q", name], self.path)

    def cleanup(self):
        shutil.rmtree(str(self.path), onerror=_force_remove)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_helpers -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Add the LICENSE**

Create `LICENSE` with the standard MIT text, `Copyright (c) 2026 Ujjwal`.

- [ ] **Step 6: Commit**

```bash
git add LICENSE tests/
git commit -m "test: temp git repo harness for portability tests"
```

---

### Task 2: Detection layer

Implements `DESIGN.md` §4. Every function returns a fallback rather than raising.

**Files:**
- Create: `scripts/detect.py`
- Create: `tests/test_detect.py`

**Interfaces:**
- Consumes: `tests.helpers.TempRepo`
- Produces:
  - `detect.default_branch(repo: Path) -> str | None`
  - `detect.remote_host(repo: Path) -> str` — one of `github`, `gitlab`, `bitbucket`, `other`, `none`
  - `detect.commit_convention(repo: Path, sample: int = 50) -> str` — `conventional` or `freeform`
  - `detect.author_candidates(repo: Path, since: str) -> list[dict]` — `[{"email": str, "commits": int}]`, descending by count
  - `detect.detect_areas(repo: Path) -> list[dict]` — `[{"name": str, "kind": str, "languages": list[str]}]`
  - `detect.run_git(args: list[str], repo: Path) -> str | None` — returns `None` on any failure

- [ ] **Step 1: Write the failing test**

Create `tests/test_detect.py`:

```python
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import detect
from tests.helpers import TempRepo, git


class TestRunGit(unittest.TestCase):
    def test_returns_none_on_git_failure(self):
        # Test that run_git returns None for a failing git command
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        result = detect.run_git(["invalid-command"], repo.path)
        self.assertIsNone(result)

    def test_returns_none_for_nonexistent_repo(self):
        # Test that run_git returns None when repo path doesn't exist
        nonexistent = Path("/nonexistent/repo")
        result = detect.run_git(["status"], nonexistent)
        self.assertIsNone(result)

    def test_handles_cyrillic_in_output(self):
        # Test that Cyrillic characters in git output don't crash
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: тест", files={"f.txt": "тест"})
        # Should not crash when getting log with Cyrillic
        result = detect.run_git(
            ["log", "-n", "1", "--pretty=format:%s"], repo.path
        )
        self.assertIsNotNone(result)


class TestDefaultBranch(unittest.TestCase):
    def test_falls_back_to_local_main(self):
        repo = TempRepo(default_branch="main")
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        self.assertEqual(detect.default_branch(repo.path), "main")

    def test_falls_back_to_local_master(self):
        repo = TempRepo(default_branch="master")
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        self.assertEqual(detect.default_branch(repo.path), "master")

    def test_slash_containing_branch_name(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        # Create a branch with slashes
        git(["checkout", "-b", "release/2.0"], repo.path)
        # Set up the symbolic-ref to point to the branch with slashes
        git(["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release/2.0"], repo.path)
        # The full name should be resolved correctly, not truncated to "2.0"
        self.assertEqual(detect.default_branch(repo.path), "release/2.0")


class TestRemoteHost(unittest.TestCase):
    def test_none_without_remote(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        self.assertEqual(detect.remote_host(repo.path), "none")

    def test_github_https(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        git(["remote", "add", "origin", "https://github.com/o/r.git"], repo.path)
        self.assertEqual(detect.remote_host(repo.path), "github")

    def test_github_ssh(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        git(["remote", "add", "origin", "git@github.com:o/r.git"], repo.path)
        self.assertEqual(detect.remote_host(repo.path), "github")

    def test_gitlab(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        git(["remote", "add", "origin", "https://gitlab.com/o/r.git"], repo.path)
        self.assertEqual(detect.remote_host(repo.path), "gitlab")

    def test_bitbucket(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        git(["remote", "add", "origin", "https://bitbucket.org/o/r.git"], repo.path)
        self.assertEqual(detect.remote_host(repo.path), "bitbucket")

    def test_self_hosted_returns_other(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        git(["remote", "add", "origin", "https://git.example.com/o/r.git"], repo.path)
        self.assertEqual(detect.remote_host(repo.path), "other")

    def test_gitlab_path_with_github_substring(self):
        # Ensure we don't match "github" in the path
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x")
        git(["remote", "add", "origin", "https://gitlab.com/org/github.io-site.git"], repo.path)
        self.assertEqual(detect.remote_host(repo.path), "gitlab")

    def test_comprehensive_url_forms(self):
        # Test all 8 standard git remote URL forms as regression test
        test_cases = [
            ("https://gitlab.com/org/github.io-site.git", "gitlab"),
            ("git@github.com:o/r.git", "github"),
            ("https://github.com/o/r.git", "github"),
            ("https://github.example.com/o/r.git", "github"),
            ("ssh://git@bitbucket.org/o/r.git", "bitbucket"),
            ("git@bitbucket.org:o/r.git", "bitbucket"),
            ("https://bitbucket.org/o/r.git", "bitbucket"),
            ("https://git.example.com/o/r.git", "other"),
        ]
        for url, expected in test_cases:
            with self.subTest(url=url):
                repo = TempRepo()
                self.addCleanup(repo.cleanup)
                repo.commit("feat: x")
                git(["remote", "add", "origin", url], repo.path)
                result = detect.remote_host(repo.path)
                self.assertEqual(result, expected, f"URL {url} should return {expected}, got {result}")

    def test_remote_host_never_raises(self):
        # Contract test: remote_host must never raise, degrading to a string instead
        hostile_urls = [
            "https://[::1/o/r.git",              # Invalid IPv6 (unclosed bracket)
            "ssh://[::1/o/r.git",                # Invalid IPv6 with scheme
            "git://[::1/o/r.git",                # Invalid IPv6 with git scheme
            "https://[::1]:8080/o/r.git",        # Valid IPv6 with port (should work)
            "C:\\repos\\thing",                   # Windows path
            "github.com:o/r.git",                # SCP-like without user@ (expect github)
            "https://user:token@github.com/o/r.git",  # With credentials
        ]
        expected_results = [
            "other",     # Invalid IPv6
            "other",     # Invalid IPv6 with ssh
            "other",     # Invalid IPv6 with git
            "other",     # Valid IPv6 (well-formed but unrecognized)
            "other",     # Windows path (no scheme, no dot in C)
            "github",    # SCP-like github.com:path
            "github",    # github.com with credentials
        ]
        for url, expected in zip(hostile_urls, expected_results):
            with self.subTest(url=url):
                repo = TempRepo()
                self.addCleanup(repo.cleanup)
                repo.commit("feat: x")
                git(["remote", "add", "origin", url], repo.path)
                # This must not raise and must return a string
                result = detect.remote_host(repo.path)
                self.assertIsInstance(result, str)
                self.assertEqual(result, expected)


class TestCommitConvention(unittest.TestCase):
    def test_conventional_when_majority_match(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        for subject in ["feat: a", "fix(api): b", "docs: c", "chore!: d"]:
            repo.commit(subject, files={"f.txt": subject})
        self.assertEqual(detect.commit_convention(repo.path), "conventional")

    def test_freeform_when_majority_do_not(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        for subject in ["added a thing", "fixed stuff", "wip", "feat: only one"]:
            repo.commit(subject, files={"f.txt": subject})
        self.assertEqual(detect.commit_convention(repo.path), "freeform")

    def test_no_commits_returns_freeform(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        # Create a repo with no commits
        self.assertEqual(detect.commit_convention(repo.path), "freeform")


class TestAuthorCandidates(unittest.TestCase):
    def test_counts_and_orders_by_commits(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: a", files={"a.txt": "a"})
        repo.commit("feat: b", files={"b.txt": "b"})
        repo.commit("feat: c", files={"c.txt": "c"}, author="Other <other@example.com>")
        candidates = detect.author_candidates(repo.path, "2000-01-01")
        self.assertEqual(candidates[0]["email"], "dev@example.com")
        self.assertEqual(candidates[0]["commits"], 2)
        self.assertEqual(candidates[1]["commits"], 1)

    def test_unicode_emoji_in_commit_message(self):
        # Test that emoji in commit messages don't crash author_candidates
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: 🎉 add feature", files={"a.txt": "a"})
        repo.commit("feat: ✨ add feature 2", files={"b.txt": "b"})
        candidates = detect.author_candidates(repo.path, "2000-01-01")
        self.assertEqual(candidates[0]["email"], "dev@example.com")
        self.assertEqual(candidates[0]["commits"], 2)

    def test_cjk_in_author_name(self):
        # Test that CJK characters in author names don't crash
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: a", files={"a.txt": "a"})
        repo.commit("feat: b", files={"b.txt": "b"}, author="张三 <zh@example.com>")
        candidates = detect.author_candidates(repo.path, "2000-01-01")
        self.assertEqual(len(candidates), 2)
        # Just verify it doesn't crash and returns both authors


class TestDetectAreas(unittest.TestCase):
    def test_single_area_for_flat_repo(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit("feat: x", files={"main.py": "x = 1"})
        areas = detect.detect_areas(repo.path)
        self.assertEqual([a["name"] for a in areas], ["."])
        self.assertIn("python", areas[0]["languages"])

    def test_top_level_directories_are_areas_without_any_manifest(self):
        """DESIGN.md §4's middle tier: workspace manifests, THEN top-level
        directories, then file extensions. Without it every repository that is
        not a declared monorepo reports the single root area, `area_count` is 1
        for all of them, and §7.3's first complexity signal never varies."""
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: three services",
            files={
                "api/handlers.py": "x = 1",
                "web/app.ts": "export const x = 1",
                "worker/main.go": "package main",
                "README.md": "# readme",
            },
        )

        areas = detect.detect_areas(repo.path)

        self.assertEqual(
            areas,
            [
                {"name": "api", "kind": "directory", "languages": ["python"]},
                {"name": "web", "kind": "directory", "languages": ["typescript"]},
                {"name": "worker", "kind": "directory", "languages": ["go"]},
            ],
        )

    def test_directories_holding_no_code_are_not_areas(self):
        """A prose directory is not an area, and a repo made only of prose
        directories still degrades to the single root area rather than to an
        empty list."""
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "docs: write it down",
            files={
                "docs/design.md": "# design",
                "notes/thoughts.txt": "thinking",
            },
        )

        areas = detect.detect_areas(repo.path)

        self.assertEqual([a["name"] for a in areas], ["."])
        self.assertEqual(areas[0]["kind"], "root")

    def test_skipped_directories_are_never_areas(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: x",
            files={
                "src/main.py": "x = 1",
                "node_modules/pkg/index.js": "module.exports = {}",
                "vendor/github.com/pkg/code.go": "package main",
            },
        )

        areas = detect.detect_areas(repo.path)

        self.assertEqual([a["name"] for a in areas], ["src"])

    def test_a_workspace_manifest_still_outranks_top_level_directories(self):
        """Tier order, not just tier presence: the manifest tier reports
        `services/api`, not `services`."""
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: mono",
            files={
                "go.work": "go 1.22\n",
                "services/api/main.go": "package main",
                "services/web/main.go": "package main",
            },
        )

        areas = detect.detect_areas(repo.path)

        self.assertEqual(
            [a["name"] for a in areas], ["services/api", "services/web"]
        )
        self.assertTrue(all(a["kind"] == "workspace-package" for a in areas))

    def test_workspace_manifest_marks_monorepo(self):
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: mono",
            files={
                "go.work": "go 1.22\n",
                "services/api/main.go": "package main",
                "services/web/main.go": "package main",
            },
        )
        areas = detect.detect_areas(repo.path)
        names = [a["name"] for a in areas]
        self.assertIn("services/api", names)
        self.assertIn("services/web", names)
        self.assertTrue(all(a["kind"] == "workspace-package" for a in areas))

    def test_skip_directories_excludes_node_modules(self):
        # Test that files in node_modules are excluded
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: x",
            files={
                "main.py": "x = 1",
                "node_modules/package/index.js": "module.exports = {}",
            },
        )
        areas = detect.detect_areas(repo.path)
        # Should only detect python, not javascript
        self.assertIn("python", areas[0]["languages"])
        self.assertNotIn("javascript", areas[0]["languages"])

    def test_skip_directories_excludes_vendor(self):
        # Test that files in vendor are excluded
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: x",
            files={
                "main.py": "x = 1",
                "vendor/github.com/pkg/code.go": "package main",
            },
        )
        areas = detect.detect_areas(repo.path)
        # Should only detect python, not go
        self.assertIn("python", areas[0]["languages"])
        self.assertNotIn("go", areas[0]["languages"])

    def test_permission_error_on_one_top_level_dir_preserves_siblings(self):
        # Regression: child.is_dir() in _workspace_package_paths used to sit
        # OUTSIDE the guarded inner try/except. A PermissionError raised by
        # is_dir() on just one top-level directory (restrictive ACLs raise
        # EACCES, which is_dir() does not swallow) escaped the inner guard
        # and was only caught by the OUTER try around the whole iterdir()
        # loop -- discarding every already-collected package, including
        # healthy siblings. The fix moves the check inside the inner guard
        # so only the offending directory is skipped.
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: mono",
            files={
                "go.work": "go 1.22\n",
                "aaa_bad/pkg/main.go": "package main",
                "bbb_good/pkg/main.go": "package main",
                "ccc_good/pkg/main.go": "package main",
            },
        )

        real_is_dir = Path.is_dir

        def flaky_is_dir(self):
            if self.name == "aaa_bad":
                raise PermissionError("simulated permission error")
            return real_is_dir(self)

        with patch("pathlib.Path.is_dir", flaky_is_dir):
            areas = detect.detect_areas(repo.path)

        names = [a["name"] for a in areas]
        self.assertIn("bbb_good/pkg", names)
        self.assertIn("ccc_good/pkg", names)
        self.assertNotIn("aaa_bad/pkg", names)

    def test_permission_error_on_grandchild_preserves_grandchild_siblings(self):
        # Regression: the GRANDCHILD loop in _workspace_package_paths used to
        # share one try/except with the whole inner loop, so a PermissionError
        # from grandchild.is_dir() continued to the next TOP-LEVEL child --
        # discarding every not-yet-visited grandchild of the current one. With
        # a single top-level directory holding several packages (the common
        # monorepo shape) that collapsed the entire repo to one root area.
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: mono",
            files={
                "go.work": "go 1.22\n",
                "apps/aaa_bad/pkg/main.go": "package main",
                "apps/bbb_good/pkg/main.go": "package main",
                "apps/ccc_good/pkg/main.go": "package main",
            },
        )

        real_is_dir = Path.is_dir

        def flaky_is_dir(self):
            if self.name == "aaa_bad":
                raise PermissionError("simulated permission error")
            return real_is_dir(self)

        with patch("pathlib.Path.is_dir", flaky_is_dir):
            areas = detect.detect_areas(repo.path)

        names = [a["name"] for a in areas]
        self.assertIn("apps/bbb_good", names)
        self.assertIn("apps/ccc_good", names)
        self.assertNotIn("apps/aaa_bad", names)

    def test_permission_error_on_grandchild_preserves_later_sorted_sibling(self):
        # Same class as above, with the poisoned grandchild in the MIDDLE of
        # its siblings and a second top-level child after it. A walk that
        # aborts the inner loop still reports apps/aaa_good and services/svc1,
        # so only apps/zzz_good -- which sorts after the poisoned entry --
        # exposes the truncation.
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        repo.commit(
            "feat: mono",
            files={
                "go.work": "go 1.22\n",
                "apps/aaa_good/pkg/main.go": "package main",
                "apps/mmm_bad/pkg/main.go": "package main",
                "apps/zzz_good/pkg/main.go": "package main",
                "services/svc1/pkg/main.go": "package main",
            },
        )

        real_is_dir = Path.is_dir

        def flaky_is_dir(self):
            if self.name == "mmm_bad":
                raise PermissionError("simulated permission error")
            return real_is_dir(self)

        with patch("pathlib.Path.is_dir", flaky_is_dir):
            areas = detect.detect_areas(repo.path)

        names = [a["name"] for a in areas]
        self.assertIn("apps/zzz_good", names)
        self.assertIn("apps/aaa_good", names)
        self.assertIn("services/svc1", names)
        self.assertNotIn("apps/mmm_bad", names)

    def test_permission_error_on_one_file_preserves_rest_of_walk(self):
        # Regression: _languages_under wrapped the whole rglob("*") loop --
        # including the per-path is_file() -- in one try/except. An OSError
        # raised part-way through a generator ends the generator, so a single
        # unreadable file aborted the remaining walk and dropped every
        # language that had not been counted yet.
        repo = TempRepo()
        self.addCleanup(repo.cleanup)
        # Everything sits under one top-level directory so a single
        # _languages_under walk covers the whole fixture: with the
        # top-level-directory tier in place, `src` is one area and `aaa`,
        # `poison.py` and `zzz` are all inside the same walk.
        repo.commit(
            "feat: x",
            files={
                "src/aaa/first.go": "package main",
                "src/aaa/poison.py": "x = 1",
                "src/zzz/later.rs": "fn main() {}",
            },
        )

        real_is_file = Path.is_file

        def flaky_is_file(self):
            if self.name == "poison.py":
                raise PermissionError("simulated permission error")
            return real_is_file(self)

        with patch("pathlib.Path.is_file", flaky_is_file):
            areas = detect.detect_areas(repo.path)

        languages = areas[0]["languages"]
        # The unreadable file itself is skipped, but the walk must continue:
        # later.rs lives in a directory sorted after the poisoned one.
        self.assertIn("rust", languages)
        self.assertIn("go", languages)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_detect -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts'`

- [ ] **Step 3: Write the implementation**

Create `scripts/__init__.py` as an empty file (so tests can import `scripts.detect`; `harvest.py` still runs standalone because Python puts a script's own directory on `sys.path`).

Create `scripts/detect.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_detect -v`
Expected: PASS, 33 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/detect.py tests/test_detect.py
git commit -m "feat: repo-shape detection with fallbacks for every signal"
```

---

### Task 3: Commit collection and signal extraction

Implements the `commits` and `signals` portions of `DESIGN.md` §5.2, plus §5.4 test detection.

**Files:**
- Create: `scripts/collect.py`
- Create: `tests/test_collect.py`

**Interfaces:**
- Consumes: `scripts.detect.run_git`
- Produces:
  - `collect.collect_commits(repo: Path, since: str, until: str | None, author: str | None) -> list[dict]` — each dict has `sha`, `date`, `email`, `subject`, `body`, `files`, `added`, `insertions`, `deletions`. `added` is the subset of `files` that this commit created, which feeds `new_files` and the "new abstractions" input to the complexity ranking.
  - `collect.is_test_file(path: str) -> bool`
  - `collect.extract_numbers(text: str) -> list[str]`
  - `collect.commit_signals(commits: list[dict], areas: list[dict]) -> dict` — the `signals` object

- [ ] **Step 1: Write the failing test**

Create `tests/test_collect.py`:

```python
import unittest

from scripts import collect
from tests.helpers import TempRepo


class TestIsTestFile(unittest.TestCase):
    def test_recognises_common_conventions(self):
        positives = [
            "tests/test_api.py",
            "src/__tests__/button.tsx",
            "spec/models/user_spec.rb",
            "internal/server_test.go",
            "src/lib/client.test.ts",
            "src/Foo/BarTest.java",
        ]
        for path in positives:
            self.assertTrue(collect.is_test_file(path), path)

    def test_rejects_non_test_paths(self):
        negatives = ["src/latest/index.ts", "docs/testing-guide.md", "app/contest.py"]
        for path in negatives:
            self.assertFalse(collect.is_test_file(path), path)


class TestExtractNumbers(unittest.TestCase):
    def test_pulls_meaningful_figures(self):
        text = "cut p95 from 1200ms to 340ms, a 3.5x win, and dropped 402 errors by 80%"
        found = collect.extract_numbers(text)
        self.assertIn("1200ms", found)
        self.assertIn("340ms", found)
        self.assertIn("3.5x", found)
        self.assertIn("80%", found)

    def test_ignores_bare_small_integers(self):
        self.assertEqual(collect.extract_numbers("fixed 2 things"), [])

    def test_rejects_embedded_multipliers(self):
        # Negative lookahead prevents matching 24x in "24x7" context
        found = collect.extract_numbers("available 24x7 now")
        self.assertEqual(found, [])

    def test_rejects_embedded_bandwidth(self):
        # Reject "100m" in "100mbps" context
        found = collect.extract_numbers("supports 100mbps throughput")
        self.assertEqual(found, [])

    def test_rejects_embedded_instance_size(self):
        # Reject "2x" in "2xlarge" context
        found = collect.extract_numbers("processed 2xlarge instances")
        self.assertEqual(found, [])

    def test_accepts_isolated_percent(self):
        # Accept "80%" with space after
        found = collect.extract_numbers("reduced by 80% capacity")
        self.assertIn("80%", found)


class TestCollectCommits(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def test_returns_files_and_stats(self):
        self.repo.commit(
            "feat: add handler",
            files={"services/api/handlers.py": "a\nb\nc\n"},
            body="Adds the handler.",
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["subject"], "feat: add handler")
        self.assertEqual(commits[0]["files"], ["services/api/handlers.py"])
        self.assertEqual(commits[0]["insertions"], 3)
        self.assertIn("Adds the handler.", commits[0]["body"])

    def test_filters_by_author(self):
        self.repo.commit("feat: mine", files={"a.txt": "a"})
        self.repo.commit(
            "feat: theirs", files={"b.txt": "b"}, author="Other <other@example.com>"
        )
        commits = collect.collect_commits(
            self.repo.path, "2000-01-01", None, "dev@example.com"
        )
        self.assertEqual([c["subject"] for c in commits], ["feat: mine"])

    def test_author_filter_ignores_email_case(self):
        """git's --author is a case-sensitive BRE, but the values compared here
        disagree about case by construction: detect.author_candidates
        lowercases, and a GitHub noreply address preserves username case
        (12345+Name@users.noreply.github.com). A case-sensitive filter returns
        nothing at all, which reads as "you shipped nothing this window" rather
        than as an error. Verified against git 2.52.0.
        """
        self.repo.commit(
            "feat: mine", files={"a.txt": "a"}, author="Dev <Dev@Example.COM>"
        )
        self.repo.commit(
            "feat: theirs", files={"b.txt": "b"}, author="Other <other@example.com>"
        )
        for spelling in ("dev@example.com", "Dev@Example.COM", "DEV@EXAMPLE.COM"):
            commits = collect.collect_commits(
                self.repo.path, "2000-01-01", None, spelling
            )
            self.assertEqual([c["subject"] for c in commits], ["feat: mine"], spelling)

    def test_author_filter_still_excludes_an_absent_author(self):
        """Case-insensitive must not degrade into match-everything."""
        self.repo.commit("feat: mine", files={"a.txt": "a"})
        commits = collect.collect_commits(
            self.repo.path, "2000-01-01", None, "nobody@example.com"
        )
        self.assertEqual(commits, [])

    def test_marks_created_files_as_added(self):
        self.repo.commit("feat: create", files={"src/new.py": "x = 1"})
        self.repo.commit("fix: edit", files={"src/new.py": "x = 2"})
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        by_subject = {c["subject"]: c for c in commits}
        self.assertEqual(by_subject["feat: create"]["added"], ["src/new.py"])
        self.assertEqual(by_subject["fix: edit"]["added"], [])

    def test_handles_multiline_body_without_breaking_parse(self):
        self.repo.commit(
            "feat: multi",
            files={"a.txt": "a"},
            body="line one\n\nline two\n\nline three",
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        self.assertEqual(len(commits), 1)
        self.assertIn("line three", commits[0]["body"])

    def test_normalizes_renamed_files(self):
        # Create initial file
        self.repo.commit("feat: create", files={"src/old.py": "x = 1"})
        # Rename it using git mv
        from pathlib import Path
        old_path = self.repo.path / "src" / "old.py"
        new_path = self.repo.path / "src" / "new.py"
        old_path.rename(new_path)
        # Commit the rename
        import subprocess
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo.path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "refactor: rename old to new"],
            cwd=self.repo.path,
            capture_output=True,
            env={**dict(subprocess.os.environ), "GIT_AUTHOR_DATE": "2026-07-02T00:00:00", "GIT_COMMITTER_DATE": "2026-07-02T00:00:00"},
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        # The renamed file should show the destination path "src/new.py"
        rename_commit = [c for c in commits if "rename" in c["subject"]]
        self.assertTrue(len(rename_commit) > 0, "Rename commit not found")
        self.assertIn("src/new.py", rename_commit[0]["files"])

    def test_normalizes_collapsed_directory_renames(self):
        # Create initial file in nested directory
        self.repo.commit("feat: create", files={"src/deeply/nested/util.py": "x = 1"})
        # Rename it to collapse the middle directory
        from pathlib import Path
        old_path = self.repo.path / "src" / "deeply" / "nested" / "util.py"
        new_path = self.repo.path / "src" / "util.py"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        # Clean up empty directories
        import shutil
        nested_dir = self.repo.path / "src" / "deeply"
        try:
            shutil.rmtree(nested_dir)
        except Exception:
            pass
        # Commit the rename
        import subprocess
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo.path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "refactor: move util to src root"],
            cwd=self.repo.path,
            capture_output=True,
            env={**dict(subprocess.os.environ), "GIT_AUTHOR_DATE": "2026-07-02T00:00:00", "GIT_COMMITTER_DATE": "2026-07-02T00:00:00"},
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        # The renamed file should be exactly "src/util.py" without double slashes
        move_commit = [c for c in commits if "move" in c["subject"]]
        self.assertTrue(len(move_commit) > 0, "Move commit not found")
        # Must be exact match, not substring, to catch double-slash bug
        self.assertEqual(move_commit[0]["files"], ["src/util.py"])


class TestPathNormalization(unittest.TestCase):
    def test_normalizes_simple_rename(self):
        self.assertEqual(collect._normalize_path("old.py => new.py"), "new.py")
        self.assertEqual(collect._normalize_path("old/path.py => new/path.py"), "new/path.py")

    def test_normalizes_brace_rename(self):
        self.assertEqual(collect._normalize_path("src/{old.py => new.py}"), "src/new.py")
        self.assertEqual(collect._normalize_path("lib/{x => y}/mod.py"), "lib/y/mod.py")

    def test_collapses_double_slashes_from_empty_new(self):
        # When new side is empty, we get double slashes that must be collapsed
        self.assertEqual(collect._normalize_path("src/{deeply/nested => }/util.py"), "src/util.py")
        self.assertEqual(collect._normalize_path("pkg/{a/b => }/mod.py"), "pkg/mod.py")
        self.assertEqual(collect._normalize_path("lib/{x/y/z => }/thing.py"), "lib/thing.py")

    def test_strips_leading_slash(self):
        # Edge case: if new is empty and before_brace is empty
        self.assertEqual(collect._normalize_path("{old => }/x.py"), "x.py")

    def test_passes_through_non_rename(self):
        self.assertEqual(collect._normalize_path("normal/file.py"), "normal/file.py")


class TestCommitSignals(unittest.TestCase):
    def test_counts_reverts_and_fix_after_feat_from_real_repo(self):
        """Test fix_after_feat using commits from a real repo (newest-first order)."""
        repo = TempRepo()
        self.addCleanup(repo.cleanup)

        # Build commits in chronological order (oldest-first)
        repo.commit("feat: add retry budget", files={"services/api/retry.py": "x = 1"})
        repo.commit("fix: retry budget off by one", files={"services/api/retry.py": "x = 2"})
        repo.commit('Revert "feat: add retry budget"', files={"services/api/retry.py": "x = 0"})

        # collect_commits returns them newest-first (as git log does)
        commits = collect.collect_commits(repo.path, "2000-01-01", None, None)
        areas = [{"name": "services/api", "kind": "workspace-package", "languages": ["python"]}]
        signals = collect.commit_signals(commits, areas)

        self.assertEqual(signals["reverts"], 1)
        self.assertEqual(signals["fix_after_feat"], 1,
                        "fix_after_feat should be 1 when fix comes after feat in time")
        self.assertEqual(signals["areas"], ["services/api"])
        self.assertEqual(signals["area_count"], 1)
        # Span from first commit to last commit
        self.assertGreaterEqual(signals["span_days"], 0)

    def test_fix_after_feat_fails_without_reverse(self):
        """Verify the reversed() fix is necessary: test fails if reverse is removed."""
        repo = TempRepo()
        self.addCleanup(repo.cleanup)

        repo.commit("feat: add thing", files={"src/thing.py": "a"})
        repo.commit("fix: fix thing", files={"src/thing.py": "b"})

        commits = collect.collect_commits(repo.path, "2000-01-01", None, None)
        areas = [{"name": "src", "kind": "root", "languages": []}]
        signals = collect.commit_signals(commits, areas)

        # Without reversed(), this would be 0 because git log returns newest-first
        # and the loop sees "fix" before "feat"
        self.assertEqual(signals["fix_after_feat"], 1)

    def _signals_for_body(self, body):
        commits = [
            {"subject": "perf: cut the retry storm", "body": body,
             "files": ["src/retry.py"], "added": [], "date": "2026-07-01",
             "sha": "1" * 40, "insertions": 5, "deletions": 0},
        ]
        return collect.commit_signals(
            commits, [{"name": ".", "kind": "root", "languages": []}]
        )

    def test_numbers_found_ignores_git_trailers(self):
        """numbers_found feeds rubric.md's x2 Concrete-numbers criterion, so a
        version string in a Co-Authored-By trailer is scored as a metric. This
        repository signs every commit that way, so it poisons its own runs."""
        signals = self._signals_for_body(
            "Bounded the retry budget.\n\n"
            "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@example.com>\n"
            "Signed-off-by: Dev <dev@example.com>"
        )
        self.assertEqual(signals["numbers_found"], [])

    def test_numbers_found_keeps_real_figures_beside_a_trailer(self):
        """The other direction, and the harder one: the trailer is appended to
        the last paragraph with no blank line, and that paragraph carries a
        real figure plus a colon in prose. Dropping the paragraph wholesale
        would cost the evidence the criterion is meant to score."""
        signals = self._signals_for_body(
            "Cut p99 from 1200ms to 300ms.\n\n"
            "The fix: stop retrying after 3 attempts, and 45% of the load "
            "disappeared.\n"
            "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@example.com>"
        )
        self.assertEqual(signals["numbers_found"], ["1200ms", "300ms", "45%"])

    def test_counts_test_files_and_new_files(self):
        commits = [
            {"subject": "test: add", "body": "",
             "files": ["tests/test_a.py", "src/a.py"], "added": ["tests/test_a.py"],
             "date": "2026-07-01", "sha": "1" * 40, "insertions": 5, "deletions": 0},
        ]
        signals = collect.commit_signals(commits, [{"name": ".", "kind": "root", "languages": []}])
        self.assertEqual(signals["test_files_touched"], 1)
        self.assertEqual(signals["new_files"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_collect -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.collect'`

- [ ] **Step 3: Write the implementation**

Create `scripts/collect.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_collect -v`
Expected: PASS, 26 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py tests/test_collect.py
git commit -m "feat: commit collection with revert, test, and figure signals"
```

---

### Task 4: Design-doc discovery

Implements `DESIGN.md` §5.3: two passes, merged and deduplicated, excerpts capped at 4000 characters.

**Files:**
- Modify: `scripts/collect.py` (append)
- Modify: `tests/test_collect.py` (append)

**Interfaces:**
- Consumes: `collect.collect_commits`
- Produces:
  - `collect.classify_doc(path: str) -> str` — one of `adr`, `design`, `spec`, `plan`, `rfc`, `readme`, `doc`
  - `collect.find_docs(repo: Path, commits: list[dict], hints: list[str]) -> list[dict]` — `[{"path", "kind", "excerpt"}]`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_collect.py` (before the `if __name__` block):

```python
class TestClassifyDoc(unittest.TestCase):
    def test_kinds(self):
        cases = {
            "docs/adr/0009-example.md": "adr",
            "docs/rfcs/0001-thing.md": "rfc",
            "docs/specs/2026-07-27-thing-design.md": "design",
            "notes/thing-spec.md": "spec",
            "docs/plans/rollout-plan.md": "plan",
            "README.md": "readme",
            "docs/guide.md": "doc",
        }
        for path, expected in cases.items():
            self.assertEqual(collect.classify_doc(path), expected, path)


class TestFindDocs(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def test_finds_touched_docs(self):
        self.repo.commit(
            "docs: write it down",
            files={"docs/adr/0001-choice.md": "# Choice\n\nWe picked X over Y."},
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        docs = collect.find_docs(self.repo.path, commits, [])
        self.assertEqual(docs[0]["path"], "docs/adr/0001-choice.md")
        self.assertEqual(docs[0]["kind"], "adr")
        self.assertIn("We picked X over Y.", docs[0]["excerpt"])

    def test_finds_name_matched_docs_by_hint(self):
        self.repo.commit(
            "chore: seed",
            files={"docs/specs/retry-budget-design.md": "# Retry budget\n\nBody."},
        )
        self.repo.commit("feat: add retry budget", files={"src/retry.py": "x = 1"})
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        recent = [c for c in commits if c["subject"].startswith("feat")]
        docs = collect.find_docs(self.repo.path, recent, ["retry-budget"])
        self.assertIn("docs/specs/retry-budget-design.md", [d["path"] for d in docs])

    def test_deduplicates_across_passes(self):
        self.repo.commit(
            "docs: retry budget",
            files={"docs/specs/retry-budget-design.md": "# Retry budget\n\nBody."},
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        docs = collect.find_docs(self.repo.path, commits, ["retry-budget"])
        self.assertEqual(len(docs), 1)

    def test_excerpt_is_capped(self):
        self.repo.commit("docs: long", files={"docs/long.md": "x" * 9000})
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        docs = collect.find_docs(self.repo.path, commits, [])
        self.assertEqual(len(docs[0]["excerpt"]), 4000)

    def test_unreadable_directory_prunes_only_that_subtree(self):
        """Explicit stack walk continues when one directory is unreadable.

        Regression: an earlier version of this test used hints=[] (skipping
        the whole hint-search block, so the guarded walk never ran) and later
        used a real hint but no injected fault (so nothing ever failed). Both
        versions passed even against the pre-fix rglob-based implementation.

        This version injects a genuine PermissionError into Path.is_dir()
        for the "docs" root only -- not a mock of the safe_* wrapper itself,
        which would trivially swallow anything regardless of what the
        production code does. The fixed find_docs routes every filesystem
        check through safe_is_dir()/safe_iterdir(), so the error is caught
        there: "docs" is pruned but "adr" (later in DOC_SEARCH_DIRECTORIES)
        is still walked and its doc still returned. Against the pre-fix
        implementation (raw, unguarded root.is_dir() / root.rglob("*") /
        candidate.is_file()), this same injected error propagates straight
        out of find_docs uncaught -- reverting the walk to raw rglob and
        re-running this test reproduces that escape, which is how the test
        was verified to have teeth.
        """
        from pathlib import Path
        from unittest.mock import patch

        self.repo.commit(
            "chore: seed",
            files={
                "docs/retry-budget-in-docs.md": "# Retry budget in docs/",
                "adr/retry-budget-design.md": "# Retry budget in adr/",
            },
        )

        real_is_dir = Path.is_dir

        def flaky_is_dir(self):
            if self.name == "docs":
                raise PermissionError("simulated permission error")
            return real_is_dir(self)

        with patch("pathlib.Path.is_dir", flaky_is_dir):
            docs = collect.find_docs(self.repo.path, [], ["retry-budget"])

        paths = [d["path"] for d in docs]
        # The poisoned subtree (docs/) is pruned -- nothing from it appears.
        self.assertNotIn("docs/retry-budget-in-docs.md", paths)
        # But adr/, a sibling later in DOC_SEARCH_DIRECTORIES, is still
        # searched and its doc is still returned.
        self.assertIn("adr/retry-budget-design.md", paths)

    def test_max_docs_truncation(self):
        """Results should be capped at MAX_DOCS."""
        # Create many matching docs
        files = {}
        for i in range(20):
            files[f"docs/design-{i:02d}.md"] = f"# Design {i}\n\nContent."
        self.repo.commit("chore: seed", files=files)

        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
        docs = collect.find_docs(self.repo.path, commits, [])

        self.assertEqual(len(docs), collect.MAX_DOCS)

    def test_touched_docs_survive_truncation_over_matched(self):
        """Touched docs should be preferred over hint-matched docs when truncating."""
        # Create more touched docs than MAX_DOCS
        touched_files = {}
        for i in range(collect.MAX_DOCS + 3):
            touched_files[f"docs/touched-{i:02d}.md"] = f"# Touched {i}"
        self.repo.commit("docs: many touched", files=touched_files)

        # Create name-matched docs
        matched_files = {}
        for i in range(10):
            matched_files[f"docs/retry-budget-{i:02d}.md"] = f"# Retry {i}"
        self.repo.commit("chore: seed", files=matched_files)

        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)

        # Get only the touched commits
        touched_commits = [c for c in commits if "many touched" in c["subject"]]
        docs = collect.find_docs(self.repo.path, touched_commits, ["retry-budget"])

        # All results should be from touched pass (touched-*.md)
        paths = [d["path"] for d in docs]
        self.assertTrue(
            all("touched-" in p for p in paths),
            f"Expected all touched docs, got {paths}"
        )

    def test_stopword_hint_returns_no_matches(self):
        """Stopwords like 'design' should not match files."""
        self.repo.commit(
            "chore: seed",
            files={"docs/retry-budget-design.md": "# Retry budget\n\nBody."},
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)

        # Empty commits (not touched), hint is just "design" (a stopword)
        docs = collect.find_docs(self.repo.path, [], ["design"])

        # Should find nothing because "design" is a stopword
        self.assertEqual(len(docs), 0)

    def test_dated_filename_matched_by_non_dated_hint(self):
        """A dated filename like 2026-07-27-retry-budget-design.md should match hint 'retry-budget'."""
        self.repo.commit(
            "chore: seed",
            files={"docs/specs/2026-07-27-retry-budget-design.md": "# Retry budget\n\nBody."},
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)

        # Clear the touched pass (use empty commits) and rely on hint matching
        docs = collect.find_docs(self.repo.path, [], ["retry-budget"])

        self.assertIn("docs/specs/2026-07-27-retry-budget-design.md", [d["path"] for d in docs])

    def test_skip_directories_excludes_vendored(self):
        """Vendored directories like node_modules should not be searched."""
        self.repo.commit(
            "chore: seed",
            files={
                "docs/retry-budget-design.md": "# Retry budget",
                "docs/node_modules/pkg/retry-budget.md": "# Fake retry in vendor",
            },
        )
        commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)

        # Search for "retry-budget" hint
        docs = collect.find_docs(self.repo.path, [], ["retry-budget"])

        paths = [d["path"] for d in docs]
        # Should find real doc
        self.assertIn("docs/retry-budget-design.md", paths)
        # Should NOT find vendor doc
        self.assertNotIn("docs/node_modules/pkg/retry-budget.md", paths)

    def test_symlink_cycle_does_not_hang(self):
        """A symlink cycle should not cause an infinite loop."""
        import os
        import subprocess

        # Create a real symlink cycle: docs/sub/loop -> docs
        (self.repo.path / "docs" / "sub").mkdir(parents=True, exist_ok=True)
        (self.repo.path / "docs" / "retry-budget.md").write_text("# Retry budget")

        loop_path = self.repo.path / "docs" / "sub" / "loop"
        try:
            os.symlink(self.repo.path / "docs", loop_path)
        except OSError as e:
            # Symlink creation may fail on Windows or restricted environments
            self.skipTest(f"Cannot create symlinks on this system: {e}")

        try:
            commits = collect.collect_commits(self.repo.path, "2000-01-01", None, None)
            # This should complete without hanging or infinite loop
            docs = collect.find_docs(self.repo.path, [], ["retry-budget"])

            # Should find the real doc
            paths = [d["path"] for d in docs]
            self.assertIn("docs/retry-budget.md", paths)
        finally:
            # Clean up symlink
            if loop_path.is_symlink():
                loop_path.unlink()

    def test_symlinked_doc_file_is_found(self):
        """A symlinked regular doc file must still be found, not dropped.

        Regression: the walk's symlink guard applied to every child before
        distinguishing file from directory, so a symlinked regular file was
        silently excluded even though it resolves to real content. Monorepos
        routinely symlink a shared ADR.md into several doc directories --
        exactly the documents find_docs exists to surface. This matches
        _languages_under's shape in detect.py, where the symlink check only
        prunes descent into symlinked *directories* and still counts
        symlinked regular files.
        """
        import os

        (self.repo.path / "docs").mkdir(parents=True, exist_ok=True)
        (self.repo.path / "adr").mkdir(parents=True, exist_ok=True)
        real_doc = self.repo.path / "docs" / "retry-budget-design.md"
        real_doc.write_text("# Retry budget\n\nBody.", encoding="utf-8")

        link_path = self.repo.path / "adr" / "retry-budget-design.md"
        try:
            os.symlink(real_doc, link_path)
        except OSError as e:
            # Symlink creation may fail on Windows or restricted environments
            self.skipTest(f"Cannot create symlinks on this system: {e}")

        try:
            docs = collect.find_docs(self.repo.path, [], ["retry-budget"])
            paths = [d["path"] for d in docs]
            # The real (non-symlinked) doc is found.
            self.assertIn("docs/retry-budget-design.md", paths)
            # Its symlinked twin must be found too, not silently dropped.
            self.assertIn("adr/retry-budget-design.md", paths)
        finally:
            if link_path.is_symlink():
                link_path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_collect -v`
Expected: FAIL with `AttributeError: module 'scripts.collect' has no attribute 'classify_doc'`

- [ ] **Step 3: Write the implementation**

Append to `scripts/collect.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_collect -v`
Expected: PASS, 39 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/collect.py tests/test_collect.py
git commit -m "feat: design-doc discovery by touch and slug match"
```

---

### Task 5: Mechanical clustering

Implements `DESIGN.md` §5.5: five strategies in priority order.

**Files:**
- Create: `scripts/cluster.py`
- Create: `tests/test_cluster.py`

**Interfaces:**
- Consumes: `collect.collect_commits` output
- Produces: `cluster.propose_clusters(commits: list[dict], default_branch: str | None, branch_commits: dict[str, list[str]], convention: str) -> list[dict]` — each cluster has `id`, `strategy`, `title`, `commits`

`branch_commits` maps a branch name to the list of SHAs reachable from it but not from the default branch. Task 7 builds it; pass `{}` to disable branch clustering.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cluster.py`:

```python
import unittest

from scripts import cluster


def commit(subject, sha, date="2026-07-01", files=None):
    return {
        "sha": sha,
        "date": date,
        "email": "dev@example.com",
        "subject": subject,
        "body": "",
        "files": files or ["src/a.py"],
        "insertions": 1,
        "deletions": 0,
    }


class TestPropose(unittest.TestCase):
    def test_pr_suffix_groups_by_number(self):
        commits = [
            commit("feat: a (#12)", "a" * 40),
            commit("fix: b (#12)", "b" * 40),
            commit("feat: c (#13)", "c" * 40),
        ]
        clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        ids = sorted(c["id"] for c in clusters)
        self.assertEqual(ids, ["pr-12", "pr-13"])
        by_id = {c["id"]: c for c in clusters}
        self.assertEqual(len(by_id["pr-12"]["commits"]), 2)
        self.assertEqual(by_id["pr-12"]["strategy"], "pr-suffix")

    def test_branch_strategy_when_no_pr_suffix(self):
        commits = [commit("feat: a", "a" * 40), commit("fix: b", "b" * 40)]
        branch_commits = {"feature/retry": ["a" * 40, "b" * 40]}
        clusters = cluster.propose_clusters(commits, "main", branch_commits, "conventional")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["id"], "branch-feature/retry")
        self.assertEqual(clusters[0]["strategy"], "branch")

    def test_scope_week_for_conventional_without_pr_or_branch(self):
        commits = [
            commit("feat(api): a", "a" * 40, date="2026-07-01"),
            commit("fix(api): b", "b" * 40, date="2026-07-02"),
            commit("feat(web): c", "c" * 40, date="2026-07-02"),
        ]
        clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        self.assertEqual(len(clusters), 2)
        self.assertTrue(all(c["strategy"] == "scope-week" for c in clusters))

    def test_day_strategy_for_freeform(self):
        commits = [
            commit("did a thing", "a" * 40, date="2026-07-01"),
            commit("did another", "b" * 40, date="2026-07-01"),
            commit("next day", "c" * 40, date="2026-07-02"),
        ]
        clusters = cluster.propose_clusters(commits, "main", {}, "freeform")
        self.assertEqual(len(clusters), 2)
        self.assertTrue(all(c["strategy"] == "day" for c in clusters))

    def test_mixed_repo_uses_highest_priority_available_per_commit(self):
        commits = [
            commit("feat: a (#12)", "a" * 40),
            commit("did a thing", "b" * 40, date="2026-07-05"),
        ]
        clusters = cluster.propose_clusters(commits, "main", {}, "freeform")
        strategies = sorted(c["strategy"] for c in clusters)
        self.assertEqual(strategies, ["day", "pr-suffix"])

    def test_title_comes_from_first_commit_subject(self):
        commits = [commit("feat: add retry budget (#12)", "a" * 40)]
        clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        self.assertEqual(clusters[0]["title"], "add retry budget")

    # --- Resolution 1: title must come from the chronologically earliest
    # commit in the cluster, not the newest (collect_commits is newest-first).

    def test_title_comes_from_earliest_commit_not_newest(self):
        # Newest-first order, as collect_commits would produce: the fixup
        # "fix: typo" is encountered FIRST because it happened last.
        commits = [
            commit("fix: typo (#12)", "b" * 40, date="2026-07-05"),
            commit("feat: add retry budget (#12)", "a" * 40, date="2026-07-01"),
        ]
        clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        self.assertEqual(len(clusters), 1)
        # Must be the story-opening commit's title, not "typo" from the
        # newest (first-encountered) commit.
        self.assertEqual(clusters[0]["title"], "add retry budget")

    def test_title_tiebreak_on_same_date_is_deterministic(self):
        # Three commits sharing the same date (day granularity can't order
        # them). Documented rule: on a date tie, keep advancing to the
        # later-positioned commit in the newest-first input -- i.e. the
        # LAST commit in list order wins the tie, every time.
        commits = [
            commit("feat: c (#12)", "c" * 40, date="2026-07-01"),
            commit("feat: b (#12)", "b" * 40, date="2026-07-01"),
            commit("feat: a (#12)", "a" * 40, date="2026-07-01"),
        ]
        clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        self.assertEqual(clusters[0]["title"], "a")
        # Re-run to confirm the result is stable, not incidental.
        clusters_again = cluster.propose_clusters(commits, "main", {}, "conventional")
        self.assertEqual(clusters_again[0]["title"], "a")

    # --- Resolution 2: a malformed/empty `date` must degrade to a
    # deterministic fallback bucket instead of raising. Verified empirically
    # that collect_commits can emit such a date: a commit object built with
    # `git hash-object --literally` and a corrupted author line causes
    # git's %aI placeholder to pass through unexpanded, so
    # `date[:10]` (scripts/collect.py:137) yields "%aI", not YYYY-MM-DD.

    def test_malformed_date_does_not_crash_scope_week_clustering(self):
        commits = [commit("feat(api): a", "a" * 40, date="%aI")]
        try:
            clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        except ValueError:
            self.fail("propose_clusters raised ValueError on a malformed commit date")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["strategy"], "scope-week")

    def test_empty_date_does_not_crash_scope_week_clustering(self):
        commits = [commit("feat(api): a", "a" * 40, date="")]
        try:
            clusters = cluster.propose_clusters(commits, "main", {}, "conventional")
        except ValueError:
            self.fail("propose_clusters raised ValueError on an empty commit date")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["strategy"], "scope-week")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cluster -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.cluster'`

- [ ] **Step 3: Write the implementation**

Create `scripts/cluster.py`:

```python
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
```

Note: `merge-commit` from `DESIGN.md` §5.5 is not a separate strategy here. `collect_commits` passes `--no-merges`, so merge commits never reach the clusterer; the PR numbers they would have supplied are recovered by the `pr-suffix` and `branch` strategies. Record this in Task 14's spec update.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cluster -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/cluster.py tests/test_cluster.py
git commit -m "feat: mechanical clustering with four fallback strategies"
```

---

### Task 6: GitHub enrichment

Implements the `gh` half of `DESIGN.md` §4 and the `pr` object in §5.2. Every function takes an injectable `runner` so tests never touch the network.

**Files:**
- Create: `scripts/github.py`
- Create: `tests/test_github.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `github.default_runner(args: list[str], cwd: Path) -> tuple[int, str]`
  - `github.gh_available(runner=None) -> bool`
  - `github.repo_visibility(repo: Path, runner=None) -> str` — `public`, `private`, or `unknown`
  - `github.fetch_pr(repo: Path, number: int, runner=None) -> dict | None`
  - `github.pr_number_for_sha(repo: Path, sha: str, runner=None) -> int | None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_github.py`:

```python
import json
import sys
import unittest
from pathlib import Path

from scripts import github


def fake_runner(responses):
    """Build a runner returning canned (returncode, stdout) by command prefix."""

    def runner(args, cwd):
        for prefix, response in responses.items():
            if " ".join(args).startswith(prefix):
                return response
        return (1, "")

    return runner


class TestDefaultRunner(unittest.TestCase):
    def test_decodes_non_ascii_stdout_as_utf8(self):
        # Drive a real child process (not a fake runner) so this actually
        # exercises subprocess decoding. The payload is smuggled in as hex
        # so the non-ASCII text never has to survive the OS command-line
        # encoding -- only default_runner's own stdout decoding is under
        # test here.
        payload = "check \U0001F389 中文 тест".encode("utf-8")
        script = (
            "import sys; "
            "sys.stdout.buffer.write(bytes.fromhex('{}')); "
            "sys.stdout.buffer.flush()"
        ).format(payload.hex())

        code, output = github.default_runner([sys.executable, "-c", script], Path("."))

        self.assertEqual(code, 0)
        self.assertEqual(output, payload.decode("utf-8"))


class TestAvailability(unittest.TestCase):
    def test_available_when_version_succeeds(self):
        runner = fake_runner({"gh --version": (0, "gh version 2.92.0")})
        self.assertTrue(github.gh_available(runner))

    def test_unavailable_when_command_missing(self):
        self.assertFalse(github.gh_available(fake_runner({})))


class TestAuthentication(unittest.TestCase):
    """`gh` being installed and `gh` holding a credential are different facts.

    DESIGN.md §5.2 gives capabilities.gh and capabilities.gh_auth separate
    keys, and §14 criterion 2 requires a degraded run to name every
    unavailable signal -- which means naming the right one.
    """

    def test_authenticated_when_auth_status_succeeds(self):
        runner = fake_runner(
            {"gh auth status": (0, "Logged in to github.com account example")}
        )
        self.assertTrue(github.gh_authenticated(runner))

    def test_unauthenticated_when_auth_status_fails(self):
        # `gh auth status` exits 1 when no credential is stored.
        self.assertFalse(github.gh_authenticated(fake_runner({})))

    def test_asks_gh_for_auth_status(self):
        seen = []

        def runner(args, cwd):
            seen.append(args)
            return (0, "")

        self.assertTrue(github.gh_authenticated(runner))
        self.assertEqual(seen, [["gh", "auth", "status"]])


class TestVisibility(unittest.TestCase):
    def test_reads_visibility_field(self):
        runner = fake_runner(
            {"gh repo view": (0, json.dumps({"visibility": "PUBLIC"}))}
        )
        self.assertEqual(github.repo_visibility(Path("."), runner), "public")

    def test_unknown_on_failure(self):
        self.assertEqual(github.repo_visibility(Path("."), fake_runner({})), "unknown")

    def test_unknown_on_malformed_json(self):
        runner = fake_runner({"gh repo view": (0, "not json")})
        self.assertEqual(github.repo_visibility(Path("."), runner), "unknown")

    def test_internal_maps_to_private(self):
        # GitHub Enterprise repos report INTERNAL. DESIGN.md §8 only knows
        # public vs private-or-unknown, so INTERNAL must fold into the
        # safer "private" bucket rather than leaking a fourth value.
        runner = fake_runner(
            {"gh repo view": (0, json.dumps({"visibility": "INTERNAL"}))}
        )
        self.assertEqual(github.repo_visibility(Path("."), runner), "private")


class TestFetchPr(unittest.TestCase):
    def test_normalises_comment_shape(self):
        payload = {
            "number": 12,
            "title": "Add retry budget",
            "body": "Why it matters",
            "additions": 100,
            "deletions": 4,
            "changedFiles": 7,
            "url": "https://github.com/o/r/pull/12",
            "mergedAt": "2026-07-23T00:00:00Z",
            "comments": [{"author": {"login": "reviewer"}, "body": "Please split this"}],
        }
        runner = fake_runner({"gh pr view 12": (0, json.dumps(payload))})
        pull = github.fetch_pr(Path("."), 12, runner)
        self.assertEqual(pull["number"], 12)
        self.assertEqual(pull["changed_files"], 7)
        self.assertEqual(pull["merged_at"], "2026-07-23T00:00:00Z")
        self.assertEqual(pull["comments"][0]["author"], "reviewer")

    def test_none_when_gh_fails(self):
        self.assertIsNone(github.fetch_pr(Path("."), 12, fake_runner({})))

    def test_malformed_comment_element_degrades_instead_of_raising(self):
        # The module docstring promises fetch_pr never raises on an unexpected
        # payload shape, and pr_number_for_sha already guards the identical
        # list-of-objects assumption. A comment that is not an object must be
        # skipped, and the well-formed comment around it must survive.
        payload = {
            "number": 12,
            "title": "t",
            "body": "b",
            "additions": 1,
            "deletions": 1,
            "changedFiles": 1,
            "url": "https://github.com/o/r/pull/12",
            "mergedAt": None,
            "comments": [
                "not-an-object",
                {"author": {"login": "reviewer"}, "body": "real comment"},
            ],
        }
        runner = fake_runner({"gh pr view 12": (0, json.dumps(payload))})
        pull = github.fetch_pr(Path("."), 12, runner)
        self.assertEqual(
            pull["comments"], [{"author": "reviewer", "body": "real comment"}]
        )

    def test_caps_comment_count_and_keeps_earliest(self):
        # A per-comment character cap does not bound total payload size when
        # the comment count itself is unbounded. DESIGN.md §7.1 uses early
        # review threads as the Tension signal, so truncation must keep the
        # earliest comments, not just any 20.
        payload = {
            "number": 12,
            "title": "t",
            "body": "b",
            "additions": 1,
            "deletions": 1,
            "changedFiles": 1,
            "url": "https://github.com/o/r/pull/12",
            "mergedAt": None,
            "comments": [
                {"author": {"login": "u{}".format(i)}, "body": "comment {}".format(i)}
                for i in range(30)
            ],
        }
        runner = fake_runner({"gh pr view 12": (0, json.dumps(payload))})
        pull = github.fetch_pr(Path("."), 12, runner)
        self.assertEqual(len(pull["comments"]), 20)
        self.assertEqual(pull["comments"][0]["author"], "u0")
        self.assertEqual(pull["comments"][-1]["author"], "u19")


class TestPrNumberForSha(unittest.TestCase):
    def test_extracts_number_from_search(self):
        payload = [{"number": 42}]
        runner = fake_runner({"gh pr list": (0, json.dumps(payload))})
        self.assertEqual(github.pr_number_for_sha(Path("."), "a" * 40, runner), 42)

    def test_none_when_no_match(self):
        runner = fake_runner({"gh pr list": (0, "[]")})
        self.assertIsNone(github.pr_number_for_sha(Path("."), "a" * 40, runner))

    def test_none_on_malformed_list_element(self):
        # gh should always return a list of objects, but a malformed payload
        # (e.g. a list of bare strings) must degrade, not raise
        # AttributeError from data[0].get(...).
        runner = fake_runner({"gh pr list": (0, json.dumps(["not-an-object"]))})
        self.assertIsNone(github.pr_number_for_sha(Path("."), "a" * 40, runner))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_github -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.github'`

- [ ] **Step 3: Write the implementation**

Create `scripts/github.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_github -v`
Expected: PASS, 17 tests

- [ ] **Step 5: Commit**

```bash
git add scripts/github.py tests/test_github.py
git commit -m "feat: optional gh enrichment with injectable runner"
```

---

### Task 7: CLI and orchestration

Implements `DESIGN.md` §5.1 and assembles the full §5.2 document.

**Files:**
- Create: `scripts/harvest.py`
- Create: `tests/test_harvest.py`

**Interfaces:**
- Consumes: `detect`, `collect`, `cluster`, `github`
- Produces:
  - `harvest.parse_since(value: str, today: date) -> str` — ISO date string
  - `harvest.build(repo: Path, since: str, author: str | None, runner=None) -> dict` — the full §5.2 document
  - `harvest.main(argv: list[str]) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_harvest.py`:

```python
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from scripts import harvest
from tests.helpers import TempRepo, git


def no_gh(args, cwd):
    return (1, "")


def fake_gh(responses):
    """Build a runner returning canned (returncode, stdout) by command prefix."""

    def runner(args, cwd):
        for prefix, response in responses.items():
            if " ".join(args).startswith(prefix):
                return response
        return (1, "")

    return runner


GH_PRESENT = "gh version 2.92.0"
GH_AUTHED = "github.com\n  Logged in to github.com account example"
GITHUB_REMOTE = "https://github.com/example/example-repo.git"


def recording_gh(extra=None):
    """An authenticated-gh runner on GitHub, plus a log of every command seen."""
    responses = {
        "gh --version": (0, GH_PRESENT),
        "gh auth status": (0, GH_AUTHED),
        "gh repo view": (0, json.dumps({"visibility": "PUBLIC"})),
    }
    responses.update(extra or {})
    inner = fake_gh(responses)
    calls = []

    def runner(args, cwd):
        calls.append(" ".join(args))
        return inner(args, cwd)

    return runner, calls


def _pr_payload(number, title="Add a retry budget"):
    return {
        "number": number,
        "title": title,
        "body": "Why it matters",
        "additions": 120,
        "deletions": 4,
        "changedFiles": 3,
        "url": "https://github.com/example/example-repo/pull/{}".format(number),
        "mergedAt": "2026-07-23T00:00:00Z",
        "comments": [{"author": {"login": "reviewer"}, "body": "Please split this"}],
    }


def _subjects(document):
    return [
        commit["subject"]
        for cluster in document["clusters"]
        for commit in cluster["commits"]
    ]


class TestParseSince(unittest.TestCase):
    def test_relative_units(self):
        today = date(2026, 7, 27)
        self.assertEqual(harvest.parse_since("14d", today), "2026-07-13")
        self.assertEqual(harvest.parse_since("2w", today), "2026-07-13")
        self.assertEqual(harvest.parse_since("1m", today), "2026-06-27")

    def test_iso_passthrough(self):
        self.assertEqual(harvest.parse_since("2026-01-01", date(2026, 7, 27)), "2026-01-01")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            harvest.parse_since("soon", date(2026, 7, 27))


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def test_produces_full_document_without_gh(self):
        self.repo.commit("feat: add retry budget (#12)", files={"src/retry.py": "x = 1"})
        self.repo.commit("fix: retry budget off by one (#12)", files={"src/retry.py": "x = 2"})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        self.assertEqual(document["meta"]["host"], "none")
        self.assertEqual(document["meta"]["visibility"], "unknown")
        self.assertEqual(document["meta"]["default_branch"], "main")
        self.assertFalse(document["meta"]["capabilities"]["pr_enrichment"])
        self.assertEqual(len(document["clusters"]), 1)
        self.assertEqual(document["clusters"][0]["id"], "pr-12")
        self.assertIsNone(document["clusters"][0]["pr"])
        self.assertIn("signals", document["clusters"][0])

    def test_warns_when_configured_author_has_no_commits(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        document = harvest.build(
            self.repo.path, "2000-01-01", "nobody@example.com", runner=no_gh
        )
        self.assertEqual(document["clusters"], [])
        self.assertTrue(
            any("no commits" in warning.lower() for warning in document["meta"]["warnings"])
        )

    def test_records_missing_gh_as_a_warning(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)
        self.assertTrue(
            any("gh" in warning.lower() for warning in document["meta"]["warnings"])
        )

    def test_output_is_json_serialisable(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)
        json.dumps(document)

    def test_document_carries_every_key_design_5_2_names(self):
        """DESIGN.md §5.2 is the downstream contract; every key must be present."""
        self.repo.commit("feat: add retry budget (#12)", files={"src/retry.py": "x = 1"})
        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        self.assertEqual(sorted(document), ["areas", "clusters", "meta"])
        self.assertEqual(
            sorted(document["meta"]),
            [
                "author",
                "capabilities",
                "commit_convention",
                "default_branch",
                "generated_at",
                "host",
                "repo_name",
                "repo_root",
                "visibility",
                "warnings",
                "window",
            ],
        )
        self.assertEqual(sorted(document["meta"]["window"]), ["days", "since", "until"])
        self.assertEqual(sorted(document["meta"]["author"]), ["candidates", "selected"])
        self.assertEqual(
            sorted(document["meta"]["capabilities"]), ["gh", "gh_auth", "pr_enrichment"]
        )
        self.assertEqual(sorted(document["areas"][0]), ["kind", "languages", "name"])
        self.assertEqual(
            sorted(document["clusters"][0]),
            ["commits", "docs", "id", "pr", "signals", "strategy", "title"],
        )
        self.assertEqual(document["meta"]["repo_name"], self.repo.path.name)
        self.assertEqual(document["meta"]["commit_convention"], "conventional")
        self.assertEqual(
            document["meta"]["author"]["selected"], "dev@example.com"
        )
        self.assertEqual(
            document["meta"]["author"]["candidates"],
            [{"email": "dev@example.com", "commits": 1}],
        )

    def test_generated_at_is_utc_in_the_format_design_5_2_shows(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)
        self.assertRegex(
            document["meta"]["generated_at"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    # --- C1: an author's email case must never empty the document ---

    def test_mixed_case_author_argument_still_finds_commits(self):
        self.repo.commit(
            "feat: mine", files={"a.txt": "a"}, author="Dev <Dev@Example.com>"
        )

        document = harvest.build(
            self.repo.path, "2000-01-01", "Dev@Example.com", runner=no_gh
        )

        self.assertEqual(_subjects(document), ["feat: mine"])
        self.assertFalse(
            any("no commits" in w.lower() for w in document["meta"]["warnings"]),
            document["meta"]["warnings"],
        )

    def test_mixed_case_configured_user_email_still_finds_commits(self):
        git(["config", "user.email", "Dev@Example.com"], self.repo.path)
        self.repo.commit("feat: mine", files={"a.txt": "a"})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        self.assertEqual(_subjects(document), ["feat: mine"])
        self.assertEqual(document["meta"]["author"]["selected"], "dev@example.com")

    def test_github_noreply_address_keeps_its_username_case(self):
        """The real-world shape: GitHub hands out 12345+Name@users.noreply.github.com
        and preserves the username's case. Lowercasing that and handing it to a
        case-sensitive git filter yields zero commits, zero warnings, exit 0 --
        the tool reports that the author shipped nothing.
        """
        noreply = "12345+Ujjwal@users.noreply.github.com"
        git(["config", "user.email", noreply], self.repo.path)
        self.repo.commit("feat: mine", files={"a.txt": "a"})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        self.assertEqual(_subjects(document), ["feat: mine"])
        self.assertEqual(
            document["meta"]["author"]["candidates"],
            [{"email": noreply.lower(), "commits": 1}],
        )
        self.assertFalse(
            any("no commits" in w.lower() for w in document["meta"]["warnings"]),
            document["meta"]["warnings"],
        )

    # --- I1: the docs and signals wiring lines must have teeth ---

    def test_docs_touched_by_a_cluster_are_attached(self):
        self.repo.commit(
            "feat: add retry budget (#12)",
            files={
                "src/retry.py": "x = 1",
                "docs/adr/0009-retry-budget.md": (
                    "# Retry budget\n\nWhy we bounded retries.\n"
                ),
            },
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        docs = document["clusters"][0]["docs"]
        self.assertEqual([doc["path"] for doc in docs], ["docs/adr/0009-retry-budget.md"])
        self.assertEqual(docs[0]["kind"], "adr")
        self.assertIn("Why we bounded retries", docs[0]["excerpt"])

    def test_docs_are_found_from_cluster_hints_not_only_touched_files(self):
        """Pins the `hints` argument as well as the call itself: the doc lives
        in a different cluster, so only hint matching can reach it."""
        self.repo.commit(
            "docs: house the notes (#99)",
            files={"docs/retry-budget-rationale.md": "# Retry budget\n\nRationale.\n"},
        )
        self.repo.commit("feat: add retry budget (#12)", files={"src/retry.py": "x = 1"})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        by_id = {cluster["id"]: cluster for cluster in document["clusters"]}
        self.assertEqual(
            [doc["path"] for doc in by_id["pr-12"]["docs"]],
            ["docs/retry-budget-rationale.md"],
        )

    def test_signals_are_computed_against_the_detected_areas(self):
        """signals.areas/area_count is the primary input to DESIGN.md §7.3's
        complexity ranking, so passing the wrong areas silently mis-ranks."""
        self.repo.commit(
            "chore: declare the workspace",
            files={"pnpm-workspace.yaml": "packages:\n  - 'services/*'\n"},
        )
        self.repo.commit(
            "feat: add retry budget (#12)",
            files={
                "services/api/handlers.py": "x = 1",
                "services/api/test_handlers.py": "y = 1",
            },
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        self.assertEqual(
            document["areas"],
            [
                {
                    "name": "services/api",
                    "kind": "workspace-package",
                    "languages": ["python"],
                }
            ],
        )
        by_id = {cluster["id"]: cluster for cluster in document["clusters"]}
        signals = by_id["pr-12"]["signals"]
        self.assertEqual(signals["areas"], ["services/api"])
        self.assertEqual(signals["area_count"], 1)
        self.assertEqual(signals["test_files_touched"], 1)
        self.assertEqual(signals["new_files"], 2)

    def test_area_count_varies_in_a_repo_with_no_workspace_manifest(self):
        """End to end for DESIGN.md §4's middle tier. `area_count` is the first
        complexity signal §7.3 names; before top-level directories were areas
        it was 1 for every repository without a workspace manifest, so it
        ranked nothing."""
        self.repo.commit(
            "feat: cross two services (#7)",
            files={
                "api/handlers.py": "x = 1",
                "web/app.ts": "export const x = 1",
                "README.md": "# readme",
            },
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        self.assertEqual(
            [(a["name"], a["kind"]) for a in document["areas"]],
            [("api", "directory"), ("web", "directory")],
        )
        signals = document["clusters"][0]["signals"]
        self.assertEqual(sorted(signals["areas"]), ["api", "web"])
        self.assertEqual(signals["area_count"], 2)

    # --- Resolution 1: gh / gh_auth / pr_enrichment are three distinct facts ---

    def test_gh_absent_reports_all_three_capabilities_false(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)
        self.assertEqual(
            document["meta"]["capabilities"],
            {"gh": False, "gh_auth": False, "pr_enrichment": False},
        )

    def test_gh_present_but_unauthenticated_is_named_as_such(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        git(
            ["remote", "add", "origin", "https://github.com/example/example-repo.git"],
            self.repo.path,
        )
        runner = fake_gh({"gh --version": (0, GH_PRESENT)})  # `gh auth status` fails

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertEqual(
            document["meta"]["capabilities"],
            {"gh": True, "gh_auth": False, "pr_enrichment": False},
        )
        self.assertTrue(
            any(
                "not authenticated" in warning.lower()
                for warning in document["meta"]["warnings"]
            ),
            document["meta"]["warnings"],
        )

    def test_authenticated_gh_on_a_non_github_host_still_reports_gh_auth_true(self):
        """The reason enrichment is off must be the true reason (DESIGN.md §14.2).

        An authenticated gh against a GitLab remote has working auth; only the
        host disqualifies PR enrichment. Reporting gh_auth False here would name
        the wrong unavailable signal.
        """
        self.repo.commit("feat: x", files={"a.txt": "a"})
        git(
            ["remote", "add", "origin", "https://gitlab.com/example/example-repo.git"],
            self.repo.path,
        )
        runner = fake_gh(
            {"gh --version": (0, GH_PRESENT), "gh auth status": (0, GH_AUTHED)}
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertEqual(document["meta"]["host"], "gitlab")
        self.assertEqual(
            document["meta"]["capabilities"],
            {"gh": True, "gh_auth": True, "pr_enrichment": False},
        )
        self.assertTrue(
            any("gitlab" in warning.lower() for warning in document["meta"]["warnings"]),
            document["meta"]["warnings"],
        )
        self.assertFalse(
            any(
                "not authenticated" in warning.lower()
                for warning in document["meta"]["warnings"]
            ),
            document["meta"]["warnings"],
        )

    def test_authenticated_gh_on_github_enriches_the_pr(self):
        self.repo.commit("feat: add retry budget (#12)", files={"src/retry.py": "x = 1"})
        git(
            ["remote", "add", "origin", "https://github.com/example/example-repo.git"],
            self.repo.path,
        )
        pull = {
            "number": 12,
            "title": "Add a retry budget",
            "body": "Why it matters",
            "additions": 120,
            "deletions": 4,
            "changedFiles": 3,
            "url": "https://github.com/example/example-repo/pull/12",
            "mergedAt": "2026-07-23T00:00:00Z",
            "comments": [],
        }
        runner = fake_gh(
            {
                "gh --version": (0, GH_PRESENT),
                "gh auth status": (0, GH_AUTHED),
                "gh repo view": (0, json.dumps({"visibility": "PRIVATE"})),
                "gh pr view 12": (0, json.dumps(pull)),
            }
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertEqual(
            document["meta"]["capabilities"],
            {"gh": True, "gh_auth": True, "pr_enrichment": True},
        )
        self.assertEqual(document["meta"]["visibility"], "private")
        self.assertEqual(document["clusters"][0]["pr"]["number"], 12)
        self.assertEqual(document["clusters"][0]["pr"]["title"], "Add a retry budget")
        self.assertEqual(document["meta"]["warnings"], [])

    def test_authed_gh_with_no_remote_at_all_names_the_missing_remote(self):
        """detect.remote_host returns 'none' when there is no origin. Blaming
        the host for not being GitHub would name the wrong missing signal."""
        self.repo.commit("feat: x", files={"a.txt": "a"})
        runner = fake_gh(
            {"gh --version": (0, GH_PRESENT), "gh auth status": (0, GH_AUTHED)}
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertEqual(document["meta"]["host"], "none")
        self.assertFalse(document["meta"]["capabilities"]["pr_enrichment"])
        warnings = " ".join(document["meta"]["warnings"]).lower()
        self.assertIn("no git remote is configured", warnings)
        self.assertNotIn("github-only", warnings)

    def test_unreadable_visibility_is_reported_even_when_enrichment_works(self):
        """DESIGN.md §8 treats unknown visibility as private; §14 criterion 2
        requires the run to say so rather than silently tightening redaction."""
        self.repo.commit("feat: x", files={"a.txt": "a"})
        git(
            ["remote", "add", "origin", "https://github.com/example/example-repo.git"],
            self.repo.path,
        )
        runner = fake_gh(
            {"gh --version": (0, GH_PRESENT), "gh auth status": (0, GH_AUTHED)}
        )  # `gh repo view` fails

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertTrue(document["meta"]["capabilities"]["pr_enrichment"])
        self.assertEqual(document["meta"]["visibility"], "unknown")
        self.assertTrue(
            any(
                "visibility" in warning.lower()
                for warning in document["meta"]["warnings"]
            ),
            document["meta"]["warnings"],
        )

    # --- Resolution 4: the window can never report negative days ---

    def test_window_days_is_clamped_at_zero_for_a_future_since(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        future = (date.today() + timedelta(days=10)).isoformat()
        document = harvest.build(self.repo.path, future, None, runner=no_gh)
        self.assertEqual(document["meta"]["window"]["days"], 0)
        self.assertEqual(document["meta"]["window"]["since"], future)

    def test_window_days_counts_a_normal_window(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        since = (date.today() - timedelta(days=14)).isoformat()
        document = harvest.build(self.repo.path, since, None, runner=no_gh)
        self.assertEqual(document["meta"]["window"]["days"], 14)


class TestBranchCommits(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def test_returns_full_forty_character_shas(self):
        """cluster.propose_clusters matches on commit["sha"], which collect fills
        from git's %H (40 chars). Abbreviated SHAs here would silently never match.
        """
        self.repo.commit("initial", files={"a.txt": "a"})
        self.repo.branch("feature/thing")
        sha = self.repo.commit("wire up the thing", files={"b.txt": "b"})

        mapping = harvest._branch_commits(self.repo.path, "main")

        self.assertEqual(mapping, {"feature/thing": [sha]})
        self.assertEqual(len(mapping["feature/thing"][0]), 40)

    def test_a_branch_commit_actually_lands_in_a_branch_cluster(self):
        """End-to-end proof of the cross-task SHA contract through build()."""
        self.repo.commit("initial", files={"a.txt": "a"})
        self.repo.branch("feature/thing")
        self.repo.commit("wire up the thing", files={"b.txt": "b"})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=no_gh)

        by_id = {cluster["id"]: cluster for cluster in document["clusters"]}
        self.assertIn("branch-feature/thing", by_id)
        self.assertEqual(by_id["branch-feature/thing"]["strategy"], "branch")
        self.assertEqual(
            [commit["subject"] for commit in by_id["branch-feature/thing"]["commits"]],
            ["wire up the thing"],
        )

    def test_no_default_branch_means_no_queries(self):
        calls = []

        def recording(args, repo):
            calls.append(args)
            return ""

        with mock.patch.object(harvest.detect, "run_git", recording):
            self.assertEqual(harvest._branch_commits(Path("."), None), {})
        self.assertEqual(calls, [])

    # --- Resolution 2: the branch fan-out is bounded ---

    def test_orders_branches_newest_first_and_stops_at_max_branches(self):
        names = ["b{:03d}".format(index) for index in range(60)]
        listed = []
        queried = []

        def recording(args, repo):
            if args[0] == "branch":
                listed.append(args)
                return "\n".join(["main"] + names) + "\n"
            if args[0] == "rev-list":
                queried.append(args[1])
                return ""
            return None

        with mock.patch.object(harvest.detect, "run_git", recording):
            harvest._branch_commits(Path("."), "main")

        self.assertEqual(len(listed), 1)
        self.assertIn("--sort=-committerdate", listed[0])
        self.assertEqual(len(queried), harvest.MAX_BRANCHES)
        self.assertEqual(queried[0], "main..b000")
        self.assertEqual(queried[-1], "main..b049")
        self.assertNotIn("main..b050", queried)

    def test_branches_without_unique_commits_still_consume_the_budget(self):
        """The cap counts branches queried, not branches kept: a repo full of
        merged branches must not slip past MAX_BRANCHES subprocesses."""
        names = ["b{:03d}".format(index) for index in range(60)]
        queried = []

        def recording(args, repo):
            if args[0] == "branch":
                return "\n".join(names) + "\n"
            if args[0] == "rev-list":
                queried.append(args[1])
                return ""  # every branch is fully merged
            return None

        with mock.patch.object(harvest.detect, "run_git", recording):
            mapping = harvest._branch_commits(Path("."), "main")

        self.assertEqual(mapping, {})
        self.assertEqual(len(queried), harvest.MAX_BRANCHES)

    def test_skips_the_detached_head_pseudo_branch(self):
        """`git branch --format=%(refname:short)` emits `(HEAD detached at abc1234)`
        when HEAD is detached. It is not a rev, so querying it wastes a
        subprocess and a slot in the MAX_BRANCHES budget."""
        queried = []

        def recording(args, repo):
            if args[0] == "branch":
                return "(HEAD detached at e0afa5c)\nfeature/thing\nmain\n"
            if args[0] == "rev-list":
                queried.append(args[1])
                return "f" * 40 + "\n"
            return None

        with mock.patch.object(harvest.detect, "run_git", recording):
            mapping = harvest._branch_commits(Path("."), "main")

        self.assertEqual(queried, ["main..feature/thing"])
        self.assertEqual(mapping, {"feature/thing": ["f" * 40]})


class TestPrLinkage(unittest.TestCase):
    """DESIGN.md §4 PR linkage (c): resolve a PR from a commit SHA via gh.

    Without it, github.pr_number_for_sha has no caller and every cluster that
    is not named `pr-N` reports pr: null even on an authed GitHub repo, losing
    the PR body and review threads §7.1 names as the primary Tension evidence.
    """

    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def _with_remote(self):
        git(["remote", "add", "origin", GITHUB_REMOTE], self.repo.path)

    def test_resolves_a_pr_for_a_branch_cluster_via_sha_search(self):
        self.repo.commit("initial", files={"a.txt": "a"})
        self.repo.branch("feature/retry-budget")
        sha = self.repo.commit("wire up the retry budget", files={"b.txt": "b"})
        self._with_remote()
        runner, calls = recording_gh(
            {
                "gh pr list": (0, json.dumps([{"number": 42}])),
                "gh pr view 42": (0, json.dumps(_pr_payload(42))),
            }
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        by_id = {cluster["id"]: cluster for cluster in document["clusters"]}
        pull = by_id["branch-feature/retry-budget"]["pr"]
        self.assertIsNotNone(pull)
        self.assertEqual(pull["number"], 42)
        self.assertEqual(pull["comments"][0]["body"], "Please split this")
        self.assertTrue(
            any(call.startswith("gh pr list") and sha in call for call in calls),
            calls,
        )

    def test_no_sha_search_when_pr_enrichment_is_off(self):
        self.repo.commit("initial", files={"a.txt": "a"})
        # No remote configured, so pr_enrichment is off even though gh is authed.
        runner, calls = recording_gh()

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertFalse(document["meta"]["capabilities"]["pr_enrichment"])
        self.assertEqual([call for call in calls if call.startswith("gh pr")], [])
        self.assertIsNone(document["clusters"][0]["pr"])

    def test_pr_suffix_clusters_never_trigger_a_sha_search(self):
        self.repo.commit("feat: add retry budget (#12)", files={"src/retry.py": "x = 1"})
        self._with_remote()
        runner, calls = recording_gh(
            {"gh pr view 12": (0, json.dumps(_pr_payload(12)))}
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertEqual(document["clusters"][0]["pr"]["number"], 12)
        self.assertEqual([call for call in calls if call.startswith("gh pr list")], [])

    def test_at_most_one_sha_search_per_cluster(self):
        self.repo.commit("initial", files={"a.txt": "a"})
        self.repo.branch("feature/thing")
        for index in range(4):
            self.repo.commit(
                "step {}".format(index), files={"b{}.txt".format(index): str(index)}
            )
        self._with_remote()
        runner, calls = recording_gh({"gh pr list": (0, "[]")})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        by_id = {c["id"]: c for c in document["clusters"]}
        self.assertEqual(len(by_id["branch-feature/thing"]["commits"]), 4)
        searches = [call for call in calls if call.startswith("gh pr list")]
        # One search for the one branch cluster, and none for the `day-`
        # cluster holding the commit that never left the default branch.
        branch_clusters = [
            c for c in document["clusters"] if c["id"].startswith("branch-")
        ]
        self.assertEqual(len(branch_clusters), 1)
        self.assertGreater(len(document["clusters"]), len(branch_clusters))
        self.assertEqual(len(searches), 1)
        self.assertFalse(
            any("capped" in w for w in document["meta"]["warnings"]),
            document["meta"]["warnings"],
        )

    def test_a_coarse_cluster_never_borrows_one_commits_pull_request(self):
        """DESIGN.md §4 linkage (c) resolves ONE PR number and `harvest.build`
        attaches it to the WHOLE cluster, so probing a cluster whose commits
        can come from different PRs manufactures evidence.

        Five `feat(api):` commits in one ISO week, each really belonging to a
        different PR, collapse into one `scope-week` cluster. Attaching any one
        of those PRs to the cluster would give the other four a PR body, a
        diffstat, review threads (rubric.md's primary Tension evidence) and a
        doc-search hint describing work they did not do. `pr: null` is the
        honest answer, and DESIGN.md §5.2 states null is not an error.
        """
        for index in range(5):
            day = date(2026, 1, 5) + timedelta(days=index)  # all inside 2026W02
            self.repo.commit(
                "feat(api): change number {}".format(index),
                files={"api/f{}.py".format(index): "x = {}".format(index)},
                date="{}T12:00:00+00:00".format(day.isoformat()),
            )
        self._with_remote()
        runner, calls = recording_gh(
            {
                "gh pr list": (0, json.dumps([{"number": 5}])),
                "gh pr view 5": (0, json.dumps(_pr_payload(5, "PR five only"))),
            }
        )

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        self.assertTrue(document["meta"]["capabilities"]["pr_enrichment"])
        self.assertEqual(len(document["clusters"]), 1)
        cluster = document["clusters"][0]
        self.assertEqual(cluster["strategy"], "scope-week")
        self.assertEqual(len(cluster["commits"]), 5)
        self.assertIsNone(cluster["pr"])
        self.assertEqual([call for call in calls if call.startswith("gh pr ")], [])

    def test_sha_searches_are_capped_and_the_cap_announces_itself(self):
        """Unlike a silent cap, this one has to name the truncation: DESIGN.md
        §10 item 5 and §14 criterion 2 both require unavailable signals to be
        stated, and a silently capped run is indistinguishable from a repo that
        genuinely has no PRs.

        Building MAX_PR_LOOKUPS + 3 *branch* clusters takes some staging, now
        that linkage (c) probes branch clusters only. The commits form one
        chain off `main` so every one of them is reachable from HEAD and
        therefore collected, and each carries a branch ref. Author dates
        descend along the chain, so `git branch --sort=-committerdate` hands
        `_branch_commits` the branch whose tip is the OLDEST commit last: each
        branch then claims exactly the one commit its predecessors have not
        already claimed, instead of the newest branch swallowing the lot.
        """
        overflow = 3
        total = harvest.MAX_PR_LOOKUPS + overflow
        self.repo.commit("initial", files={"a.txt": "a"})
        self.repo.branch("work")
        for index in range(total):
            day = date(2026, 3, 1) - timedelta(days=index)
            sha = self.repo.commit(
                "work item {}".format(index),
                files={"f{}.txt".format(index): str(index)},
                date="{}T12:00:00+00:00".format(day.isoformat()),
            )
            git(["branch", "slice-{:02d}".format(index), sha], self.repo.path)
        self._with_remote()
        runner, calls = recording_gh({"gh pr list": (0, "[]")})

        document = harvest.build(self.repo.path, "2000-01-01", None, runner=runner)

        branch_clusters = [
            c for c in document["clusters"] if c["id"].startswith("branch-")
        ]
        self.assertEqual(len(branch_clusters), total)
        self.assertTrue(all(len(c["commits"]) == 1 for c in branch_clusters))
        searches = [call for call in calls if call.startswith("gh pr list")]
        self.assertEqual(len(searches), harvest.MAX_PR_LOOKUPS)
        capped = [w for w in document["meta"]["warnings"] if "capped at" in w]
        self.assertEqual(len(capped), 1, document["meta"]["warnings"])
        self.assertIn(str(harvest.MAX_PR_LOOKUPS), capped[0])
        self.assertIn("{} older cluster".format(overflow), capped[0])


class TestMain(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        self.scratch = Path(tempfile.mkdtemp(prefix="lps-out-"))
        self.addCleanup(shutil.rmtree, str(self.scratch), True)
        # main() takes no runner, so pin the module-level default: no test may
        # shell out to a real gh binary or touch the network.
        patcher = mock.patch.object(harvest.github, "default_runner", no_gh)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exits_non_zero_outside_a_repo(self):
        code = harvest.main(["--repo", str(Path(__file__).parent / "does-not-exist")])
        self.assertNotEqual(code, 0)

    def test_exits_non_zero_on_an_unparseable_since(self):
        code = harvest.main(["--repo", str(self.repo.path), "--since", "soon"])
        self.assertNotEqual(code, 0)

    def test_writes_the_document_to_the_requested_path(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        target = self.scratch / "harvest.json"

        code = harvest.main(
            ["--repo", str(self.repo.path), "--since", "30d", "--json", str(target)]
        )

        self.assertEqual(code, 0)
        document = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(sorted(document), ["areas", "clusters", "meta"])

    # --- I2: the --author flag must reach build and change the result ---

    def test_author_flag_reaches_build_and_filters_the_document(self):
        """Mixed-case on purpose, so this pins C1 and I2 together: it fails if
        --author is dropped on the way to build, and it fails again if the git
        author filter goes back to being case-sensitive."""
        git(["config", "user.email", "other@example.com"], self.repo.path)
        self.repo.commit(
            "feat: mine", files={"a.txt": "a"}, author="Dev <Dev@Example.com>"
        )
        self.repo.commit(
            "feat: theirs", files={"b.txt": "b"}, author="Other <other@example.com>"
        )
        target = self.scratch / "harvest.json"

        code = harvest.main(
            [
                "--repo", str(self.repo.path),
                "--since", "30d",
                "--author", "Dev@Example.com",
                "--json", str(target),
            ]
        )

        self.assertEqual(code, 0)
        document = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(_subjects(document), ["feat: mine"])
        self.assertEqual(document["meta"]["author"]["selected"], "dev@example.com")

    # --- Resolution 3: an unwritable --json path is an exit code, not a traceback ---

    def test_unwritable_json_path_exits_non_zero_without_raising(self):
        self.repo.commit("feat: x", files={"a.txt": "a"})
        target = self.scratch / "no-such-directory" / "harvest.json"

        code = harvest.main(["--repo", str(self.repo.path), "--json", str(target)])

        self.assertNotEqual(code, 0)
        self.assertFalse(target.exists())


class NarrowStdout:
    """Stand-in for a Windows stdout that is not a console.

    Python then encodes text-mode writes with the locale codec (cp1252 on a
    default Windows install), which rejects most non-ASCII. `.buffer` still
    accepts raw bytes, which is the escape hatch write_stdout uses.
    """

    encoding = "ascii"

    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, text):
        self.buffer.write(text.encode("ascii"))  # raises, exactly like cp1252
        return len(text)

    def flush(self):
        pass


class TestStdoutEncoding(unittest.TestCase):
    """Regression: `python scripts/harvest.py --repo . | ...` crashed with
    UnicodeEncodeError on Windows whenever any commit body held a non-ASCII
    character. Found by piping a real run, not by reading the code."""

    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        patcher = mock.patch.object(harvest.github, "default_runner", no_gh)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_stdout_emits_utf8_through_a_narrow_stdout(self):
        stdout = NarrowStdout()
        with mock.patch.object(sys, "stdout", stdout):
            harvest.write_stdout("pipeline → output")
        self.assertEqual(
            stdout.buffer.getvalue(), "pipeline → output\n".encode("utf-8")
        )

    def test_main_streams_a_non_ascii_document_to_a_narrow_stdout(self):
        self.repo.commit(
            "feat: widen the pipeline",
            files={"a.txt": "a"},
            body="harvest → cluster → score",
        )
        stdout = NarrowStdout()

        with mock.patch.object(sys, "stdout", stdout):
            code = harvest.main(["--repo", str(self.repo.path), "--since", "30d"])

        self.assertEqual(code, 0)
        document = json.loads(stdout.buffer.getvalue().decode("utf-8"))
        self.assertEqual(sorted(document), ["areas", "clusters", "meta"])
        self.assertIn(
            "→", document["clusters"][0]["commits"][0]["body"]
        )

    def test_write_stdout_falls_back_when_stdout_has_no_buffer(self):
        class TextOnly:
            def __init__(self):
                self.written = []

            def write(self, text):
                self.written.append(text)
                return len(text)

            def flush(self):
                pass

        stdout = TextOnly()
        with mock.patch.object(sys, "stdout", stdout):
            harvest.write_stdout("plain")
        self.assertEqual("".join(stdout.written), "plain\n")


class TestModuleEntryPoints(unittest.TestCase):
    def test_runs_as_a_script_and_as_a_package_module(self):
        """scripts/collect.py's try/except import idiom must hold for harvest too:
        `python scripts/harvest.py` and `python -m scripts.harvest` both work."""
        root = Path(__file__).resolve().parent.parent
        for command in (
            [sys.executable, str(root / "scripts" / "harvest.py"), "--help"],
            [sys.executable, "-m", "scripts.harvest", "--help"],
        ):
            result = subprocess.run(
                command, cwd=str(root), capture_output=True, text=True, timeout=30
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--since", result.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_harvest -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.harvest'`

- [ ] **Step 3: Write the implementation**

Create `scripts/harvest.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_harvest -v`
Expected: PASS, 45 tests

- [ ] **Step 5: Verify the whole suite and a real run**

```bash
python -m unittest discover -s tests -t . -v
python scripts/harvest.py --since 30d --repo . --json /tmp/harvest.json
```

Expected: all tests pass; the JSON file contains `meta`, `areas`, and `clusters` keys.

- [ ] **Step 6: Commit**

```bash
git add scripts/harvest.py tests/test_harvest.py
git commit -m "feat: harvest CLI producing the full JSON contract"
```

---

### Task 8: Skill-file structural validator

Markdown files get a real test too. This validator fails now and passes as Tasks 9 to 12 land, so each subsequent task has a red test to turn green.

**Files:**
- Create: `tests/test_skill_files.py`

**Interfaces:**
- Consumes: nothing
- Produces: no importable API; a test module only

- [ ] **Step 1: Write the failing test**

Create `tests/test_skill_files.py`:

```python
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BANNED_IN_DRAFT_EXAMPLES = {
    "em dash": "—",
    "curly double quote": "“",
    "curly single quote": "‘",
}

# Union of DESIGN.md §9.2's banned set (delve, leverage, landscape,
# testament, underscore, robust, seamless, unlock) and the task brief's list
# (which drops landscape/unlock and adds vibrant, tapestry, pivotal,
# showcase). The spec's eight are non-negotiable; the brief's extra four are
# real AI tells kept because they cost nothing to also ban, making the
# validator a strict superset of the spec.
AI_VOCABULARY = [
    "delve", "leverage", "landscape", "testament", "underscore",
    "robust", "seamless", "unlock", "vibrant", "tapestry",
    "pivotal", "showcase",
]

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class TestSkillMd(unittest.TestCase):
    def setUp(self):
        self.text = read("SKILL.md")

    def test_has_yaml_frontmatter_with_name_and_description(self):
        self.assertTrue(self.text.startswith("---\n"))
        end = self.text.index("\n---\n", 3)
        frontmatter = self.text[4:end]
        self.assertRegex(frontmatter, r"(?m)^name:\s*linkedin-post\s*$")
        self.assertRegex(frontmatter, r"(?m)^description:\s*Use when")

    def test_body_is_under_500_words(self):
        body = self.text.split("\n---\n", 1)[1]
        self.assertLess(len(body.split()), 500)

    def test_references_its_companion_files(self):
        for name in ("rubric.md", "drafting.md", "scripts/harvest.py"):
            self.assertIn(name, self.text)

    def test_uses_no_force_loading_at_links(self):
        self.assertNotRegex(self.text, r"(?m)^\s*@[\w./-]+")


class TestCompanionFilesExist(unittest.TestCase):
    def test_all_declared_files_present(self):
        for name in (
            "SKILL.md", "README.md", "LICENSE", "DESIGN.md",
            "rubric.md", "drafting.md", "scripts/harvest.py",
            "examples/sample-output.md", "install.sh", "install.ps1",
        ):
            self.assertTrue((ROOT / name).exists(), name)


class TestDraftingRules(unittest.TestCase):
    def setUp(self):
        self.text = read("drafting.md")

    def test_names_every_absolute_prohibition(self):
        for phrase in ("em dash", "emoji", "rule of three", "curly quote"):
            self.assertIn(phrase, self.text.lower(), phrase)

    def test_lists_the_ai_vocabulary_set(self):
        lowered = self.text.lower()
        for word in AI_VOCABULARY:
            self.assertIn(word, lowered, word)

    def test_defines_all_three_redaction_postures(self):
        # Substring checks alone were proven vacuous by the final-review
        # mutation sweep: gutting the whole posture table left them green
        # ("open" matched "open-ended", and the posture names survive in
        # prose elsewhere). Assert the actual structure: the section heading,
        # the table header with all five columns, and one table row per
        # posture.
        self.assertRegex(self.text, r"(?m)^## 1\. Redaction posture\s*$")
        self.assertRegex(
            self.text,
            r"(?m)^\| Posture \| Default when \| Names freely \| Abstracts \| Drops \|\s*$",
        )
        for posture in ("open", "stack-only", "maximum"):
            self.assertRegex(
                self.text,
                r"(?m)^\| `%s` \|" % re.escape(posture),
                "no posture-table row for {}".format(posture),
            )
        # The load-bearing cell: stack-only DROPS the company name. The
        # redaction-log example must never teach substituting it instead.
        stack_row = next(
            line
            for line in self.text.splitlines()
            if line.startswith("| `stack-only` |")
        )
        self.assertIn("Company name", stack_row.split("|")[-2])


class TestRubric(unittest.TestCase):
    def setUp(self):
        self.text = read("rubric.md")

    def test_names_all_six_criteria_and_the_gate(self):
        for phrase in (
            "Tension", "Transferable", "Concrete numbers",
            "One-idea", "Visual potential", "Freshness",
        ):
            self.assertIn(phrase, self.text, phrase)
        # A bare `"gate" in text` check was proven vacuous by the final-review
        # mutation sweep: renaming the heading to "## The aggregate" kept it
        # green, because "gate" is a substring of "aggregate". Pin the actual
        # heading, and the sentence that makes the gate a gate.
        self.assertRegex(self.text, r"(?m)^## The gate\s*$")
        self.assertIn("Confidentiality is a gate, not a criterion.", self.text)

    def test_excludes_raw_line_count_from_complexity(self):
        self.assertIn("line count", self.text.lower())


class TestSampleOutputDogfoodsTheRules(unittest.TestCase):
    """The example post must obey the rules the skill enforces."""

    def setUp(self):
        self.text = read("examples/sample-output.md")

    def test_contains_no_banned_characters(self):
        for label, character in BANNED_IN_DRAFT_EXAMPLES.items():
            self.assertNotIn(character, self.text, label)

    def test_contains_no_ai_vocabulary(self):
        lowered = self.text.lower()
        for word in AI_VOCABULARY:
            self.assertNotIn(word, lowered, word)


class TestNoPrivateRepoReferences(unittest.TestCase):
    """Opt-in local guard.

    The term list must never be committed: publishing "do not mention X"
    tells every reader exactly what X is. Put one lowercase term per line in
    .private-terms, which .gitignore excludes. The test skips when absent, so
    contributors who cloned the repo are unaffected.
    """

    def test_no_markdown_file_names_a_private_codebase(self):
        terms_file = ROOT / ".private-terms"
        if not terms_file.exists():
            self.skipTest(".private-terms not present; this guard is opt-in")
        terms = [
            line.strip().lower()
            for line in terms_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for term in terms:
                self.assertNotIn(term, lowered, "{} in {}".format(term, path.name))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_skill_files -v`
Expected: FAIL with `FileNotFoundError` for `SKILL.md`

- [ ] **Step 3: Commit the failing test**

The validator is the specification for Tasks 9 to 12. Commit it red on purpose.

```bash
git add tests/test_skill_files.py
git commit -m "test: structural validator for skill markdown files"
```

---

### Task 9: rubric.md

Expands `DESIGN.md` §7 into the file the agent loads at the scoring stage.

**Files:**
- Create: `rubric.md`

**Interfaces:**
- Consumes: the `signals` object from Task 3
- Produces: no code; consumed by `SKILL.md` stage 3

- [ ] **Step 1: Run the validator to see the rubric tests fail**

Run: `python -m unittest tests.test_skill_files.TestRubric -v`
Expected: FAIL with `FileNotFoundError: rubric.md`

- [ ] **Step 2: Write rubric.md**

Content, in order:

1. **Heading and one-line purpose.** "Load this at the scoring stage. Score every cluster; do not skip low scorers, they belong in the shortlist as evidence you looked."
2. **Post-worthiness table** — copy the six-row table from `DESIGN.md` §7.1 verbatim, including the Evidence column. Add a leading sentence: "Six criteria, each 0 to 5, weighted. Maximum 60."
3. **Weighting rationale** — copy the paragraph from §7.1 verbatim. This is what stops an agent from silently re-weighting toward scope.
4. **The gate** — copy the confidentiality-gate paragraph from §7.1. Add: "A blocked item is listed under a separate Blocked heading with its reason. Never silently omit it."
5. **Anti-signals** — copy §7.2 verbatim.
6. **Complexity ranking** — copy §7.3 verbatim, including the line-count exclusion and its reasoning.
7. **A worked example** — score this cluster by hand so the agent has a calibration anchor:

```
Cluster: "never let the third-party fallback fail the pipeline run"
  2 commits, 1 area, span 1 day, 0 reverts, 1 fix_after_feat,
  numbers_found: ["402"], docs: 1 design doc listing a rejected alternative

  Tension            4  x3 = 12   fix-after-feat plus a rejected alternative in the doc
  Transferable       5  x3 = 15   "isolate third-party failure from your own pipeline"
                                  survives stripping every product noun
  Concrete numbers   2  x2 =  4   one status code, no before/after figures
  One-idea           5  x2 = 10   single thesis
  Visual potential   3  x1 =  3   before/after error-handling diff
  Freshness          5  x1 =  5   this week
                          ----
                            49 / 60   Gate: PASS under stack-only
```

8. **Scoring discipline** — three rules: score from the evidence column, not from impression; a cluster with no design doc and no PR body caps Tension at 2 because there is no record of a wrong turn; never invent a number that is not in `numbers_found` or a diffstat.

- [ ] **Step 3: Run the validator to verify it passes**

Run: `python -m unittest tests.test_skill_files.TestRubric -v`
Expected: PASS, 2 tests

- [ ] **Step 4: Commit**

```bash
git add rubric.md
git commit -m "docs: scoring rubric for post-worthiness and complexity"
```

---

### Task 10: drafting.md

Expands `DESIGN.md` §8 and §9 into the file the agent loads at the drafting stage.

**Files:**
- Create: `drafting.md`

**Interfaces:**
- Consumes: the selected cluster and `meta.visibility`
- Produces: no code; consumed by `SKILL.md` stages 5 and 6

- [ ] **Step 1: Run the validator to see the drafting tests fail**

Run: `python -m unittest tests.test_skill_files.TestDraftingRules -v`
Expected: FAIL with `FileNotFoundError: drafting.md`

- [ ] **Step 2: Write drafting.md**

Content, in order:

1. **Redaction posture** — copy the §8 table verbatim (`open`, `stack-only`, `maximum`), plus the default-selection rule keyed to `meta.visibility`: `public` selects `open`, `private` or `unknown` selects `stack-only`, `maximum` only on explicit request. Then the hollow-draft rule from §8.
2. **Redaction log format** — a two-column table, `Original` and `Replacement`, one row per substitution, plus a final line naming the posture used.
3. **Post anatomy** — copy §9.1's four numbered parts.
4. **The four hook frameworks**, each with one worked example written to the rules in this file:
   - *Contrarian claim* — "Retries made our reliability worse."
   - *Specific number* — "One third-party API returned 402 and took down a pipeline that had nothing to do with it."
   - *Failure confession* — "I spent two days debugging our code. The bug was that we trusted someone else's."
   - *Unexpected comparison* — "Our error handling had no fuse box. One bad circuit took the house."
5. **The absolute prohibitions** — copy §9.2's absolute list verbatim. Present it as a checklist the agent runs against its own draft before showing it. Must literally contain the strings "em dash", "emoji", "rule of three", "curly quote", and every word in the AI vocabulary list enforced by `tests/test_skill_files.py`: delve, leverage, landscape, testament, underscore, robust, seamless, unlock, vibrant, tapestry, pivotal, showcase. That enforced list is a **union, not a verbatim copy of §9.2**: the spec's eight words are the non-negotiable part, and vibrant, tapestry, pivotal and showcase are four extra tells the task brief added. Reproducing only the ten-word variant would drop `landscape` and `unlock`, both of which §9.2 bans explicitly, so the checklist would pass a draft the spec forbids.
6. **The preserved formatting** — copy §9.2's preserved list, with the closing-question disqualifier stated as a test: "Would you read the answers? If not, the question is decoration. Rewrite it."
7. **humanizer handoff** — "If the humanizer skill is installed, invoke it on the draft and pass the two lists above as constraints. If not, run the checklist in section 5 manually and tell the user: `git clone https://github.com/blader/humanizer.git ~/.claude/skills/humanizer` improves results."
8. **Carousel spec** — copy §9.3. Add the slide template: slide 1 is the hook verbatim, slides 2 to N are one idea each with a layout note, the final slide is the closing question.
9. **Length discipline** — hook under 200 characters, body under 200 words, paragraphs of one to three sentences. State that these are hard limits, not targets.

- [ ] **Step 3: Run the validator to verify it passes**

Run: `python -m unittest tests.test_skill_files.TestDraftingRules -v`
Expected: PASS, 3 tests

- [ ] **Step 4: Commit**

```bash
git add drafting.md
git commit -m "docs: drafting rules, redaction postures, humanizer reconciliation"
```

---

### Task 11: SKILL.md

The workflow the agent actually follows. Under 500 words.

**Files:**
- Create: `SKILL.md`

**Interfaces:**
- Consumes: `scripts/harvest.py`, `rubric.md`, `drafting.md`
- Produces: the skill entry point

- [ ] **Step 1: Run the validator to see the SKILL.md tests fail**

Run: `python -m unittest tests.test_skill_files.TestSkillMd -v`
Expected: FAIL with `FileNotFoundError: SKILL.md`

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: linkedin-post
description: Use when the user wants to post on LinkedIn about work they have done in a code repository, asks what recent work is worth posting about, wants a draft written about a shipped feature or fix, or asks which of their tasks would make a good post. Works in any git repo.
license: MIT
---

# LinkedIn post from repo work

Turn recent authored work in the current git repo into a ranked shortlist of
post ideas and one finished draft.

## Workflow

Run these in order. Do not skip stage 3 even when one item looks obviously best.

### 1. Harvest

```bash
python <this-skill-dir>/scripts/harvest.py --since 14d --repo .
```

`<this-skill-dir>` is wherever this file is installed, for example
`~/.claude/skills/linkedin-post`. That path is the skill; `--repo .` is always
the repo you are standing in, never the skill's own directory. Widen with
`--since 30d` if fewer than three clusters come back. If `meta.warnings`
mentions an author with no commits, re-run with `--author <email>` before
going further.

### 2. Re-cluster

The script clusters mechanically and is often wrong at the story level. Read
each cluster's PR body and linked docs, then split any cluster whose description
needs the word "and". Every final cluster carries exactly one thesis, written as
one sentence. Splitting is common; merging is rare.

### 3. Score

Read `rubric.md` and score every cluster. Produce two tables: post-worthiness
(primary) and complexity (secondary). List gate-blocked items separately with
reasons. Never omit an item silently.

### 4. Select

Show both tables. Recommend the top post-worthiness item and say in one sentence
why it beats the runner-up. Ask the user to confirm or pick another.

### 5. Draft

Read `drafting.md`. Set the redaction posture from `meta.visibility`. Write three
hooks, the body, and a closing question. Every factual claim must trace to a
commit, PR body, or doc in the harvest. Invent nothing.

### 6. Humanize

Invoke the `humanizer` skill on the draft, passing the absolute prohibitions and
preserved formatting from `drafting.md`. If it is not installed, run that
checklist manually and say so.

### 7. Output

1. Shortlist tables, blocked items included
2. The draft: three hooks, body, closing question, first-comment link block
3. Carousel outline, only when visual potential scored 3 or higher
4. Redaction log with the posture used
5. Coverage note: window, author, cluster strategy, unavailable signals

## Rules

- Effort is not post-worthiness. The largest change is rarely the best post.
- Never state a number that is not in the harvest.
- Under `stack-only`, no company name, customer name, or internal identifier
  reaches the draft.
- The draft is a starting point. Say so, and offer to revise.
```

- [ ] **Step 3: Run the validator to verify it passes**

Run: `python -m unittest tests.test_skill_files.TestSkillMd -v`
Expected: PASS, 4 tests

- [ ] **Step 4: Verify the word count independently**

```bash
python -c "import pathlib; body = pathlib.Path('SKILL.md').read_text(encoding='utf-8').split(chr(10)+'---'+chr(10),1)[1]; print(len(body.split()))"
```

Expected: a number below 500.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "feat: skill entry point and seven-stage workflow"
```

---

### Task 12: One-command installers

Anyone must be able to install the skill with a single terminal command, either
globally (`~/.claude/skills/`, available in every repo) or into one workspace
(`./.claude/skills/`, checked in or not as they choose). Two scripts, because
the audience spans POSIX shells and PowerShell.

**Files:**
- Create: `install.sh`
- Create: `install.ps1`
- Modify: `tests/test_skill_files.py` (append)

**Interfaces:**
- Consumes: nothing at runtime; clones the published repo
- Produces: a skill directory at `$HOME/.claude/skills/linkedin-post` (default) or `./.claude/skills/linkedin-post` (with `--local`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skill_files.py` (before the `if __name__` block):

```python
class TestInstallers(unittest.TestCase):
    def setUp(self):
        self.sh = read("install.sh")
        self.ps1 = read("install.ps1")

    def test_both_support_global_and_local(self):
        for name, text in (("install.sh", self.sh), ("install.ps1", self.ps1)):
            self.assertIn("--global", text, name)
            self.assertIn("--local", text, name)

    def test_both_target_the_same_skill_directory_name(self):
        for name, text in (("install.sh", self.sh), ("install.ps1", self.ps1)):
            self.assertIn(".claude/skills", text.replace("\\", "/"), name)
            self.assertIn("linkedin-post", text, name)

    def test_shell_installer_is_posix_sh_not_bashisms(self):
        self.assertTrue(self.sh.startswith("#!/usr/bin/env sh"))
        # Raw substrings for the bashisms that do not collide with anything
        # legitimate in this script's text (help output, flag names, etc).
        for bashism in ("[[", "declare ", "function "):
            self.assertNotIn(bashism, self.sh, bashism)
        # "local " as a raw substring also matches inside the --help text
        # ("--local   install to ...") and the --local flag name itself,
        # neither of which is the bashism this probe is meant to catch.
        # What is actually forbidden in POSIX sh is a `local` variable
        # declaration. Match that specifically instead.
        self.assertNotRegex(
            self.sh, r"(?m)^\s*local\s+\S+=", "local variable declaration"
        )

    def test_shell_installer_fails_fast(self):
        self.assertIn("set -e", self.sh)

    def test_both_refuse_to_run_without_git(self):
        self.assertIn("command -v git", self.sh)
        self.assertIn("Get-Command git", self.ps1)

    def test_both_update_an_existing_install_instead_of_failing(self):
        self.assertIn("git -C", self.sh)
        self.assertIn("pull", self.sh)
        self.assertIn("pull", self.ps1)


class TestSubprocessDiscipline(unittest.TestCase):
    """timeout=30 on every subprocess call is a global constraint of this
    project, and the final-review mutation sweep proved that dropping it from
    BOTH call sites left all tests green. Behavioural tests cannot pin it
    without really hanging a child process, so this source inspection is the
    honest shape: every subprocess.run call in the two modules that spawn
    processes must carry the timeout."""

    SUBPROCESS_FILES = ("scripts/detect.py", "scripts/github.py")

    def test_every_subprocess_run_call_carries_timeout_30(self):
        for name in self.SUBPROCESS_FILES:
            text = read(name)
            calls = [
                match.start() for match in re.finditer(r"subprocess\.run\(", text)
            ]
            self.assertTrue(calls, "{} has no subprocess.run call".format(name))
            for start in calls:
                # The timeout must appear inside this call's argument list,
                # i.e. before the next `def ` after the call site.
                window = text[start:]
                cut = window.find("\ndef ")
                if cut != -1:
                    window = window[:cut]
                self.assertIn(
                    "timeout=30",
                    window,
                    "{}: subprocess.run at offset {} has no timeout=30".format(
                        name, start
                    ),
                )

    def test_no_other_module_spawns_processes(self):
        # The constraint stays checkable only while spawning is confined to
        # the two audited modules. Comments may say "subprocess"; an import
        # is what would open an unaudited call site.
        for name in ("scripts/harvest.py", "scripts/collect.py", "scripts/cluster.py"):
            self.assertNotRegex(
                read(name), r"(?m)^\s*(import subprocess|from subprocess)", name
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_skill_files.TestInstallers -v`
Expected: FAIL with `FileNotFoundError: install.sh`

- [ ] **Step 3: Write install.sh**

```sh
#!/usr/bin/env sh
# Install the linkedin-post skill for Claude Code.
#
#   Global (every repo):
#     curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh
#
#   This workspace only:
#     curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh -s -- --local
set -e

REPO_URL="https://github.com/Ujjwal160107/linkedin-post-skill.git"
SKILL_NAME="linkedin-post"
SCOPE="global"

for arg in "$@"; do
  case "$arg" in
    --global) SCOPE="global" ;;
    --local)  SCOPE="local" ;;
    -h|--help)
      echo "usage: install.sh [--global|--local]"
      echo "  --global  install to \$HOME/.claude/skills (default)"
      echo "  --local   install to ./.claude/skills in the current directory"
      exit 0
      ;;
    *)
      echo "install: unknown option '$arg' (try --help)" >&2
      exit 2
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "install: git is required but was not found on PATH" >&2
  exit 1
fi

if [ "$SCOPE" = "local" ]; then
  SKILLS_DIR="$(pwd)/.claude/skills"
else
  SKILLS_DIR="$HOME/.claude/skills"
fi
TARGET="$SKILLS_DIR/$SKILL_NAME"

mkdir -p "$SKILLS_DIR"

if [ -d "$TARGET/.git" ]; then
  echo "install: updating existing install at $TARGET"
  git -C "$TARGET" pull --ff-only --quiet
elif [ -e "$TARGET" ]; then
  echo "install: $TARGET already exists and is not a git clone." >&2
  echo "install: move or delete it, then re-run." >&2
  exit 1
else
  echo "install: cloning into $TARGET"
  git clone --depth 1 --quiet "$REPO_URL" "$TARGET"
fi

echo ""
echo "Installed $SKILL_NAME to $TARGET"
if [ "$SCOPE" = "local" ]; then
  echo "Scope: this workspace only."
else
  echo "Scope: global. Available in every repo."
fi
echo ""
echo "Use it by running /$SKILL_NAME inside any git repository."
echo ""
echo "Optional companion, improves the writing pass:"
echo "  git clone https://github.com/blader/humanizer.git \"$SKILLS_DIR/humanizer\""
```

- [ ] **Step 4: Write install.ps1**

```powershell
<#
.SYNOPSIS
  Install the linkedin-post skill for Claude Code.

.EXAMPLE
  # Global (every repo)
  irm https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.ps1 | iex

.EXAMPLE
  # This workspace only
  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.ps1))) --local
#>
param(
  [ValidateSet('--global', '--local')]
  [string]$Scope = '--global'
)

$ErrorActionPreference = 'Stop'

# Under `powershell -File install.ps1 --local`, PowerShell does not bind
# `--local` to the positional $Scope parameter at all: the argument lands in
# $args and the script would silently run with the default scope, installing
# globally when the user asked for a workspace install. Installing somewhere
# the user did not ask for is worse than refusing, so any unbound argument is
# a hard error naming the offender.
if ($args.Count -gt 0) {
  Write-Error ("install: unrecognized argument(s): {0}. Use --global or --local, e.g. & ([scriptblock]::Create((irm <url>))) --local" -f ($args -join ', '))
  exit 1
}

$RepoUrl = 'https://github.com/Ujjwal160107/linkedin-post-skill.git'
$SkillName = 'linkedin-post'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error 'install: git is required but was not found on PATH'
  exit 1
}

if ($Scope -eq '--local') {
  $SkillsDir = Join-Path (Get-Location) '.claude/skills'
} else {
  $SkillsDir = Join-Path $HOME '.claude/skills'
}
$Target = Join-Path $SkillsDir $SkillName

New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null

if (Test-Path (Join-Path $Target '.git')) {
  Write-Host "install: updating existing install at $Target"
  git -C $Target pull --ff-only --quiet
} elseif (Test-Path $Target) {
  Write-Error "install: $Target already exists and is not a git clone. Move or delete it, then re-run."
  exit 1
} else {
  Write-Host "install: cloning into $Target"
  git clone --depth 1 --quiet $RepoUrl $Target
}

Write-Host ''
Write-Host "Installed $SkillName to $Target"
if ($Scope -eq '--local') {
  Write-Host 'Scope: this workspace only.'
} else {
  Write-Host 'Scope: global. Available in every repo.'
}
Write-Host ''
Write-Host "Use it by running /$SkillName inside any git repository."
Write-Host ''
Write-Host 'Optional companion, improves the writing pass:'
Write-Host "  git clone https://github.com/blader/humanizer.git `"$SkillsDir/humanizer`""
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m unittest tests.test_skill_files.TestInstallers -v`
Expected: PASS, 6 tests

- [ ] **Step 6: Exercise both installers for real**

The scripts clone from a URL that does not exist until Task 14 pushes. Verify the local-path and argument logic now by pointing `REPO_URL` at the working copy in a scratch shell, without editing the committed file:

```bash
cd /tmp && mkdir -p install-probe && cd install-probe
sed "s|^REPO_URL=.*|REPO_URL=\"<absolute-path-to-working-copy>\"|" <working-copy>/install.sh > probe.sh
sh probe.sh --local
test -f .claude/skills/linkedin-post/SKILL.md && echo "LOCAL INSTALL OK"
sh probe.sh --local && echo "RE-RUN UPDATE OK"
sh probe.sh --bogus; test $? -eq 2 && echo "BAD ARG REJECTED"
```

Expected: all three lines print. Repeat the `--local` path with `install.ps1` in PowerShell.

- [ ] **Step 7: Commit**

```bash
git add install.sh install.ps1 tests/test_skill_files.py
git commit -m "feat: one-command global and workspace installers"
```

---

### Task 13: README and sample output

**Files:**
- Create: `README.md`
- Create: `examples/sample-output.md`

**Interfaces:**
- Consumes: everything
- Produces: the public face of the repo

- [ ] **Step 1: Run the validator to see the remaining tests fail**

Run: `python -m unittest tests.test_skill_files -v`
Expected: FAIL on `TestCompanionFilesExist` and `TestSampleOutputDogfoodsTheRules`

- [ ] **Step 2: Write examples/sample-output.md**

A complete run against a fictional `example-repo`. It must obey the rules the skill enforces, because Task 8 tests it: no em dashes, no curly quotes, none of the AI vocabulary words. Sections:

1. Shortlist table, four items with both scores and one-line theses
2. One blocked item with its reason
3. The full draft: three hooks, body under 200 words, closing question
4. Carousel outline, nine slides
5. Redaction log, four rows, posture `stack-only`
6. Coverage note

- [ ] **Step 3: Write README.md**

Sections:

1. **What it does** — three sentences, no marketing language.
2. **Install** — lead with the one-liners, since that is the advertised path. Present all four, each labelled with its scope:

```bash
# macOS / Linux / Git Bash (global, available in every repo)
curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh

# macOS / Linux / Git Bash (this workspace only)
curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh -s -- --local
```

```powershell
# Windows PowerShell (global)
irm https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.ps1 | iex

# Windows PowerShell (this workspace only)
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.ps1))) --local
```

Follow with a "prefer to see what you are running first" note offering the manual equivalent, because piping a URL into a shell deserves an alternative:

```bash
git clone https://github.com/Ujjwal160107/linkedin-post-skill.git ~/.claude/skills/linkedin-post
```

State plainly what global versus workspace means: global lands in `~/.claude/skills/` and works in every repo; `--local` lands in `./.claude/skills/` and travels with that one project, so a team can commit it. Re-running either command updates an existing install.

3. **Use** — `/linkedin-post` in any git repo. Note the `--since` widening.
4. **What it reads** — commits, PR bodies and review comments through `gh`, design docs. State plainly that nothing leaves the machine except the `gh` calls, and that it never posts anything.
5. **Requirements** — the §12 dependency table verbatim.
6. **How it ranks** — the six criteria with weights, plus one line on why line count is excluded from complexity.
7. **Redaction** — the three postures and the visibility-derived default.
8. **Sample output** — link to `examples/sample-output.md`.
9. **Credits** — humanizer by Siqi Chen, MIT, https://github.com/blader/humanizer, described as an optional companion.
10. **License** — MIT.

- [ ] **Step 4: Run the full suite**

Run: `python -m unittest discover -s tests -t . -v`
Expected: PASS, every test

- [ ] **Step 5: Commit**

```bash
git add README.md examples/
git commit -m "docs: README and a full sample run"
```

---

### Task 14: Acceptance validation and first push

Verifies `DESIGN.md` §14 against reality, then publishes.

**Files:**
- Modify: `DESIGN.md` (§11 and §5.5 notes)
- Create: `examples/validation-notes.md`

- [ ] **Step 1: Update DESIGN.md for the two implementation refinements**

In §11, replace the single `scripts/harvest.py` line with the five-module listing (`harvest.py`, `detect.py`, `collect.py`, `cluster.py`, `github.py`). In §5.5, note that `merge-commit` is not implemented as a distinct strategy because `--no-merges` filters merge commits out before clustering, and `pr-suffix` plus `branch` recover the same linkage. In §5.2, add `added` to the commit object: the subset of `files` that the commit created, which is what `new_files` counts.

- [ ] **Step 2: Run acceptance criteria 1 through 5**

Against any repo with conventional commits, a GitHub remote, and authed `gh`:

```bash
python scripts/harvest.py --since 30d --repo <path-to-repo-A> --json a.json
```

Then in a scratch repo with freeform commits and no remote:

```bash
git init -q scratch && cd scratch
git -c user.email=dev@example.com -c user.name=Dev commit -q --allow-empty -m "did a thing"
python <skill-path>/scripts/harvest.py --since 30d --repo . --json b.json
```

Record in `examples/validation-notes.md`, per run: cluster count, strategies used, warnings emitted, and whether any private identifier appeared in output.

- [ ] **Step 3: Run acceptance criterion 6, the judgment test**

Invoke the skill end to end against a repo with at least 30 days of history. Write down the top-ranked item and whether it is one the author would actually post.

If the ranking prefers the largest change over the most interesting one, the weights are wrong. Retune `rubric.md`, re-run, and record both the before and after ranking in the validation notes. Do not proceed to Step 5 until this criterion passes.

- [ ] **Step 4: Run acceptance criterion 7, the portability check**

Run the skill against a second repository with a different language, layout, and commit convention from the first. Confirm no output references the first repo's structure, and that `python -m unittest discover -s tests -t . -v` still passes.

- [ ] **Step 5: Commit and push**

```bash
git update-index --chmod=+x install.sh
git add DESIGN.md examples/validation-notes.md install.sh
git commit -m "docs: acceptance validation notes and spec refinements"
gh repo create Ujjwal160107/linkedin-post-skill --public --source=. --remote=origin --push
```

`--chmod=+x` matters: Windows checkouts do not carry the executable bit, and
without it `install.sh` is not directly runnable after a clone. The
`curl | sh` path works either way because `sh` reads from stdin.

Confirm with the user before running `gh repo create`. It is the first outward-facing action in this plan.

- [ ] **Step 6: Verify the advertised install commands against the live repo**

Only after the push, because these URLs do not resolve until then:

```bash
curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh -s -- --local
test -f .claude/skills/linkedin-post/SKILL.md && echo "PUBLIC INSTALL OK"
```

Run from a scratch directory outside the working copy. Repeat with the
PowerShell one-liner. Record both results in `examples/validation-notes.md`.
A README that advertises an install command nobody has run is a broken
promise; this step is what makes acceptance criterion 1 true for strangers,
not just for the author.

---

## Self-Review

**Spec coverage:**

| `DESIGN.md` section | Task |
|---|---|
| §1 Purpose, non-goals | 11 (SKILL.md), 13 (README) |
| §2 Constraints | Global Constraints; enforced by tests in 1 to 8 |
| §3 Pipeline | 11 |
| §4 Detection layer | 2, plus visibility in 6 |
| §5.1 CLI | 7 |
| §5.2 JSON schema | 7, assembled from 2, 3, 4, 5, 6 |
| §5.3 Design-doc discovery | 4 |
| §5.4 Test detection | 3 |
| §5.5 Clustering | 5 (with the `merge-commit` note recorded in 14) |
| §6 Semantic re-clustering | 11, stage 2 |
| §7.1, §7.2, §7.3 | 9 |
| §8 Redaction postures | 10 |
| §9.1, §9.2, §9.3 | 10 |
| §10 Output | 11 stage 7, 13 sample |
| §11 File layout | 14 refinement (adds `install.sh`, `install.ps1`) |
| §12 Dependencies | 6 degradation, 13 README table |
| §13 Deferred hooks | Not implemented by design; §13 stays as written |
| §14 Acceptance criteria | 14 |
| Distribution (added after the spec was approved) | 12 installers, 13 README, 14 live verification |

No gaps. Distribution was not in `DESIGN.md`; Task 14 adds `install.sh` and
`install.ps1` to §11 and a Distribution subsection to §12 recording that the
advertised install commands are verified against the live repo after push.

**Placeholder scan:** No "TBD", "TODO", "add error handling", "similar to Task N", or "write tests for the above". Every code step carries runnable code. Tasks 9, 10, and 12 specify Markdown content by naming each section and its source, with the load-bearing text written out; their structural requirements are enforced by executable tests in Task 8.

**Type consistency:**

- `run_git(args, repo)` defined in Task 2, imported in Tasks 3 and 7. Consistent.
- `commit_signals` emits `area_count`, matching `DESIGN.md` §5.2 after the self-review fix. Task 5's tests and Task 9's worked example both use `area_count`. No stale `layers_crossed`.
- `fetch_pr` returns `changed_files` and `merged_at` (snake_case), converted from `gh`'s `changedFiles` and `mergedAt`. Task 7 stores the result unchanged under `cluster["pr"]`, matching §5.2.
- `propose_clusters(commits, default_branch, branch_commits, convention)` has the same four-parameter signature in Task 5's tests and Task 7's call site.
- `parse_since(value, today=None)` is called with two arguments in tests and one in `main`. The default makes both valid.
- `new_files` is computed from each commit's `added` list, populated by a second `--diff-filter=A` pass in `collect_commits`. The first draft of this plan hardcoded it to `0`, which would have shipped a field the complexity ranking reads but nothing writes. Task 3 now covers it with `test_marks_created_files_as_added` and `test_counts_test_files_and_new_files`, and Task 14 records the `added` field in §5.2.
- `_window_args(since, until, author)` is shared by `collect_commits` and `_added_by_sha` so the two passes can never drift out of alignment on the window or author filter.
