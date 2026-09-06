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
