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
