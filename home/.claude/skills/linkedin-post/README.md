# linkedin-post

## What it does

This skill reads the commits, pull requests, and design docs in the git
repo you are standing in, and finds the work that would make a good
LinkedIn post. It ranks that work by tension, transferability, and the
other criteria that predict engagement, not by how large the change was.
It then drafts one post: three hook options, a body, a closing question,
and a carousel outline when the work has something to show.

## Install

The one-liners are the advertised path. Pick the scope you want.

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

If you would rather see what you are about to run before you run it,
piping a URL into a shell is not required. Clone it directly instead:

```bash
git clone https://github.com/Ujjwal160107/linkedin-post-skill.git ~/.claude/skills/linkedin-post
```

Global installs land in `~/.claude/skills/` and are available in every
repo. `--local` installs land in `./.claude/skills/` inside the current
directory, so they travel with that one project and a team can commit
them. Re-running either command updates an existing install instead of
failing.

## Use

Run `/linkedin-post` inside any git repo. It looks at the last 14 days of
your authored commits by default. If fewer than three clusters come back,
widen the window by asking for `--since 30d` (or any `Nd`, `Nw`, `Nm`, or
an ISO date).

## What it reads

The skill reads commit metadata directly from your local git history,
plus PR titles, bodies, and review comments through the `gh` CLI when it
is installed and authenticated, plus any design docs referenced from the
harvested commits. Nothing leaves your machine except the calls `gh`
itself makes to GitHub on your behalf; every other step is a local git
command or a local file read. The skill never posts anything. It drafts,
and you copy, edit, and post it yourself.

## Requirements

| Dependency | Required | Without it |
|---|---|---|
| git | Yes | Hard error |
| Python 3.9+ | Yes | Hard error |
| `gh` CLI, authenticated | No | No PR bodies, comments, or visibility detection. Falls back to commits and docs; posture defaults to `stack-only` |
| `humanizer` skill | No | Falls back to an inlined checklist of the AI tells that matter most for LinkedIn, and prints the one-line install command |

## How it ranks

Six criteria, each scored 0 to 5, weighted, maximum 60:

| Criterion | Weight |
|---|---|
| Tension | x3 |
| Transferable lesson | x3 |
| Concrete numbers | x2 |
| One-idea compression | x2 |
| Visual potential | x1 |
| Freshness | x1 |

Complexity is scored separately, on a different set of signals, and it
deliberately excludes raw line count: a large generated file would
dominate that ranking while a small concurrency fix would sink to the
bottom, and line count measures typing, not difficulty.

## Redaction

Every draft is written under one of three postures: `open` names
everything freely and links to the actual PR; `stack-only` names
languages, frameworks, and infrastructure but drops company names,
customer names, and internal identifiers; `maximum` keeps only the
language and general domain. The default is derived from `meta.visibility`
in the harvest output: `public` selects `open`, and `private` or
`unknown` selects `stack-only`. `maximum` is never chosen automatically;
it is opt-in only, for a run where you ask for it explicitly.

## Sample output

See [examples/sample-output.md](examples/sample-output.md) for a full run
against a fictional repository, from shortlist to carousel outline.

## Credits

The drafting stage hands off to the `humanizer` skill when it is
installed, to strip common AI writing tells from the draft before you see
it. `humanizer` is an optional companion, written by Siqi Chen, MIT
licensed: https://github.com/blader/humanizer.

## License

MIT. See [LICENSE](LICENSE).
