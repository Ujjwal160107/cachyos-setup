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
