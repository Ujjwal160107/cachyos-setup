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
