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


if __name__ == "__main__":
    unittest.main()
