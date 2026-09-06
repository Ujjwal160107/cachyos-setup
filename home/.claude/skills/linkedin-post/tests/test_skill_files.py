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


if __name__ == "__main__":
    unittest.main()
