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
