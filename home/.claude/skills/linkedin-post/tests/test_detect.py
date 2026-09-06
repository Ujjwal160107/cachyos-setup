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
