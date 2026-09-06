# linkedin-post — design

Status: approved design, implemented. Sections marked "as implemented" record
where the build diverged from this document and why.
Date: 2026-07-27, revised 2026-08-02
Repo: https://github.com/Ujjwal160107/linkedin-post-skill
Installs to: `~/.claude/skills/linkedin-post`

## 1. Purpose

A Claude Code skill that reads the work you actually did in whatever repo you
are standing in, tells you which of it is worth a LinkedIn post, and drafts the
best one.

It answers three questions in one run:

1. What did I ship recently that is worth posting about?
2. Which single item is the strongest post, and why that one?
3. What does that post actually say?

### Non-goals

- It does not publish to LinkedIn. Output is a draft you copy, edit, and post.
- It does not schedule, queue, or run unattended. Interactive only in v1.
- It does not learn your personal writing voice in v1. See §13.
- It does not invent achievements. Every claim traces to a commit, PR, or doc.

## 2. Constraints

The skill is public and must work in a repo it has never seen.

- **Zero configuration.** No config file, no per-repo setup, no env vars.
- **Zero required network access** beyond the `gh` CLI when it happens to exist.
- **Python 3.9+ standard library only** for the harvest script. No pip install.
- **Cross-platform.** Windows, macOS, Linux. No shell-specific syntax, no
  POSIX-only paths, no reliance on a particular shell.
- **Graceful degradation.** Missing `gh`, a non-GitHub remote, freeform commit
  messages, no docs directory, a shallow clone: each removes a signal, none
  causes a failure. Every degraded run says which signals were unavailable.
- **No assumptions about repo shape.** Language, layout, monorepo or single
  package, commit convention, branch naming: all detected, never assumed.

## 3. Pipeline

```
scripts/harvest.py  →  cluster  →  score  →  select  →  draft  →  humanize  →  output
     (script)          (agent)     (agent)   (user)    (agent)  (sub-skill)
```

Stage boundaries follow one rule: anything deterministic and repetitive goes in
the script, anything requiring judgment goes to the agent. The script never
scores and never writes prose. The agent never re-derives data the script
already collected.

## 4. Detection layer

Run first, inside `harvest.py`, before any collection. This is the portability
contract, so each item names its fallback chain.

| What | Detection | Fallback |
|---|---|---|
| Repo root | `git rev-parse --show-toplevel` | Hard error; the skill requires a git repo |
| Default branch | `git symbolic-ref refs/remotes/origin/HEAD` | Probe `main`, `master`, `develop`, `trunk` in order; else no branch-diff clustering |
| Remote host | Parse `git remote get-url origin` | `none` — git-only mode |
| Repo visibility | `gh repo view --json visibility` | `unknown` → treated as private |
| Author identity | `git config user.email` | List all emails with commits in window; warn if the configured one has zero |
| Commit convention | Sample up to 50 subjects against `^(\w+)(\([^)]+\))?!?: ` | `freeform` — subject parsed as a plain sentence |
| PR linkage | (a) `(#N)` subject suffix, then (c) `gh pr list --search <sha>` for branch clusters — see §4.2 | No PR enrichment |
| Areas | Workspace manifest packages, then top-level directories containing code; languages inferred from file extensions | Single area named `.` |
| Design docs | Path globs (see §5.3) | Empty list |
| Test files | Path and name patterns (see §5.4) | Rigor signal unavailable |

### 4.1 Workspace manifests checked

`pnpm-workspace.yaml`, `lerna.json`, `turbo.json`, `nx.json`, `go.work`,
`settings.gradle`, and `Cargo.toml` with a `[workspace]` table. Any hit means
monorepo. Areas then come from a two-level directory scan for packages that
contain code, not from parsing the manifest's declared paths.

Two originally specified manifests are **not implemented**: `pom.xml` with
`<modules>` and `composer.json` with `repositories`. A Maven or Composer
monorepo is therefore not recognised as one; it falls through to the
top-level-directory tier, which still yields one area per top-level module
directory that contains code.

### 4.2 PR linkage, as implemented

This row was specified with four strategies. Two shipped, two did not, and the
reasons are recorded here rather than left as a gap between the spec and the
code.

| Strategy | Status | Why |
|---|---|---|
| (a) `(#N)` subject suffix | Implemented | Free. `cluster.propose_clusters` already parses `(#N)` into the cluster id, so `harvest.build` reads the number straight off the id with no subprocess at all |
| (b) `Merge pull request #N` | Not implemented | Unreachable. `collect._window_args` passes `--no-merges` to every `git log` call, so no merge commit ever reaches the clusterer. Removing `--no-merges` to recover this strategy would import every merge commit as a first-class item, and §7.2 lists merge commits as an anti-signal |
| (c) `gh pr list --search <sha>` | Implemented | The authoritative resolution, applied to `branch-*` clusters only. The resolved PR attaches to the whole cluster, and only in a branch cluster do all commits plausibly belong to one PR; a coarse day or scope-week cluster keeps `pr: null` rather than borrowing one commit's PR as evidence for work the other commits did not do. One search per cluster, never one per commit, bounded by `MAX_PR_LOOKUPS` |
| (d) Branch name | Not implemented | Deliberately dropped. It resolves the same linkage (c) already resolves, but heuristically, and it would cost a second network call per cluster on top of (c). `branch` still exists as a *clustering* strategy in §5.5; it is only PR-number inference from a branch name that was not built |

The distinction that matters: (b) is blocked by a design decision made
elsewhere in this document, while (d) is a cost decision that could be revisited
if (c) ever proves unreliable.

## 5. harvest.py

### 5.1 CLI

```
python scripts/harvest.py [--since 14d] [--author EMAIL] [--repo PATH] [--json PATH]
```

`--since` accepts `Nd`, `Nw`, `Nm`, or an ISO date. Default `14d`. Output goes
to stdout as JSON unless `--json` is given.

### 5.2 Output schema

```json
{
  "meta": {
    "generated_at": "2026-07-27T10:00:00Z",
    "repo_root": "/path/to/repo",
    "repo_name": "example-repo",
    "host": "github",
    "visibility": "private",
    "default_branch": "main",
    "window": { "since": "2026-07-13", "until": "2026-07-27", "days": 14 },
    "author": {
      "selected": "dev@example.com",
      "candidates": [{ "email": "dev@example.com", "commits": 43 }]
    },
    "commit_convention": "conventional",
    "capabilities": { "gh": true, "gh_auth": true, "pr_enrichment": true },
    "warnings": []
  },
  "areas": [
    { "name": "services/api", "kind": "workspace-package", "languages": ["python"] }
  ],
  "clusters": [
    {
      "id": "pr-123",
      "strategy": "pr-suffix",
      "title": "<PR or derived cluster title>",
      "pr": {
        "number": 123,
        "title": "...",
        "body": "...",
        "comments": [{ "author": "...", "body": "..." }],
        "additions": 866,
        "deletions": 41,
        "changed_files": 23,
        "url": "https://github.com/owner/repo/pull/123",
        "merged_at": "2026-07-23T00:00:00Z"
      },
      "commits": [
        {
          "sha": "abc1234def5678901234567890abcdef12345678",
          "date": "2026-07-23",
          "email": "dev@example.com",
          "subject": "...",
          "body": "...",
          "files": ["services/api/handlers.py"],
          "added": ["services/api/handlers.py"],
          "insertions": 120,
          "deletions": 4
        }
      ],
      "docs": [{ "path": "docs/adr/0009-example.md", "kind": "adr", "excerpt": "..." }],
      "signals": {
        "reverts": 0,
        "fix_after_feat": 3,
        "test_files_touched": 12,
        "areas": ["services/api"],
        "area_count": 1,
        "new_files": 8,
        "span_days": 1,
        "numbers_found": ["402", "3x", "866"]
      }
    }
  ]
}
```

`pr` is `null` when unavailable. `docs` is `[]` when none are found. Neither
absence is an error.

**Notes on the commit object.** Three fields need saying explicitly, because
getting any of them wrong breaks something downstream that no test of the field
in isolation would catch.

- `sha` is the **full 40-character hash**, from git's `%H`, never the
  abbreviated form the example above once showed. The `branch` clustering
  strategy in §5.5 matches these against the output of
  `git rev-list <default>..<branch>`, which is also full length. Abbreviating
  either side makes every branch cluster silently fail to match and produce no
  error.
- `added` is the subset of `files` that the commit **created**, collected by a
  second `git log --diff-filter=A` pass over the same window. It is what
  `signals.new_files` counts, and §7.3 reads `new_files` as the evidence for new
  abstractions introduced. Without it that criterion has nothing to score.
- `email` is the commit's author email, lowercased. It is present so a document
  can be re-filtered by author after the fact without re-running git, and so a
  run that selected the wrong author is diagnosable from the JSON alone.

### 5.3 Design-doc discovery

Two independent passes, results merged and deduplicated:

1. **Touched:** any `.md`, `.mdx`, `.rst`, `.txt`, or `.adoc` file modified by a
   commit in the cluster.
2. **Name-matched:** files under the top-level directories `docs/`, `doc/`,
   `rfcs/`, `adr/`, `decisions/`, `design/`, and `.github/` — each searched
   recursively, skipping vendored directories — whose filename shares a slug
   token with the cluster's title, its id (which embeds the branch name or
   commit scope), or its PR title.

The search roots are **top-level only**, a narrower net than the recursive
globs (`**/adr/**`, `**/*plan*.md`, ...) this pass was originally specified
with. A doc nested elsewhere, such as `services/api/docs/design.md`, is found
only when a commit in the cluster touched it (pass 1), never by name. This is
a known limitation, recorded here rather than left as a gap between spec and
code.

Results are capped at `MAX_DOCS = 12` per cluster, touched docs preferred over
name matches when the cap binds, and the excerpt is capped at 4000 characters
per doc to bound token cost.

### 5.4 Test-file detection

Path contains a segment `test`, `tests`, `spec`, `specs`, `__tests__`, or
`testing`; or the filename matches `test_*`, `*_test.*`, `*.test.*`,
`*_spec.*`, `*.spec.*`, `*Test.java`, `*Tests.cs`.

### 5.5 Proposed clustering

The script clusters mechanically. Strategies in priority order:

1. `pr-suffix` — subject ends with `(#N)`; one cluster per N.
2. `merge-commit` — **not implemented.** See the note below.
3. `branch` — commits reachable from a non-default branch but not from the
   default branch.
4. `scope-week` — conventional-commit scope plus ISO week.
5. `day` — freeform repos with no other signal; one cluster per author-day.

The chosen strategy is recorded per cluster so the agent knows how much to trust
it. `strategy` therefore takes one of four values in practice: `pr-suffix`,
`branch`, `scope-week`, `day`.

**Why `merge-commit` was dropped.** Every `git log` call in `collect.py` passes
`--no-merges`, so a merge commit never reaches the clusterer and a strategy
keyed on one could never fire. That flag is not incidental: §7.2 lists merge
commits among the anti-signals, and admitting them would put "Merge pull request
#123 from feature/x" into the shortlist as a first-class item with its own
diffstat, double-counting the work of the commits it brings in.

Nothing is lost by the omission. The linkage `merge-commit` would have
established is recovered twice over — by `pr-suffix` when the merge was
squashed (which is what leaves the `(#N)` suffix on the subject in the first
place), and by `branch` when it was not, since the commits a merge brings in are
exactly the commits `git rev-list <default>..<branch>` returns. §4.2 records the
same decision from the PR-linkage side.

## 6. Semantic re-clustering (agent)

The script's clustering is mechanical and often wrong at the story level. A
single PR frequently contains two or three separable stories, and a long-running
branch nearly always does.

The agent reads PR bodies and linked design docs, then merges or splits clusters
so that **each final cluster carries exactly one thesis**, stated in one
sentence. A cluster that needs "and" to describe it gets split. Splitting is the
common operation, merging is rare.

## 7. Scoring

### 7.1 Post-worthiness (primary ranking)

Six criteria, each scored 0–5, weighted. Maximum 60.

| Criterion | Weight | 0 | 5 | Evidence |
|---|---|---|---|---|
| Tension | ×3 | Linear; worked first try | A wrong turn, a revert, or a root cause that was not where you looked | `reverts`, `fix_after_feat`, "turns out / instead / actually / it was not" in PR bodies, rejected options in design docs, review threads demanding change |
| Transferable lesson | ×3 | Meaningless outside this codebase | Changes how any engineer works Monday | Does the thesis survive stripping every product-specific noun? |
| Concrete numbers | ×2 | None | Hard before-and-after figures | `numbers_found`, diffstat, benchmark or cost figures in PR body |
| One-idea compression | ×2 | Several theses tangled together | One thesis, tellable in 200 words | Cluster coherence after §6 |
| Visual potential | ×1 | Nothing to show | Clean before/after code, or an architecture change | Diff shape, new modules, state machines, config diffs |
| Freshness | ×1 | Older than 90 days | This week | Commit dates |

**Weighting rationale.** Tension and transferability carry the most weight
because LinkedIn now ranks primarily on dwell time, and comments count roughly
double likes. Readers do not dwell on, and do not comment on, work they cannot
apply. Effort does not predict reach; applicability does. Scope deliberately
carries no weight at all in this ranking.

**Confidentiality is a gate, not a criterion.** If the story *is* the product
concept, the item is dropped from the shortlist with the reason printed, rather
than scored low and buried where it looks like a near miss.

### 7.2 Anti-signals

Subtract from the tension score, or drop outright when nothing else is present:
dependency bumps, lockfile churn, formatting or lint-only changes,
doc-only commits, pure renames, generated-file updates, merge commits, and
changes whose entire story is "I configured a thing."

### 7.3 Complexity (secondary ranking)

Presented as a separate table, clearly labeled as answering a different
question. Ranked on:

- Areas crossed (`area_count`, as defined in §4)
- New abstractions introduced (new modules, interfaces, protocols, workflows)
- State, concurrency, migration, or distributed-systems involvement
- Blast radius in call sites changed
- Calendar duration from first to last commit

**Raw line count is excluded on purpose.** A large generated file or a long plan
document would dominate the ranking, while a six-line concurrency fix would sink
to the bottom. Line count measures typing.

## 8. Redaction posture

Defaults from detected repo visibility, always overridable, always stated in the
output.

| Posture | Default when | Names freely | Abstracts | Drops |
|---|---|---|---|---|
| `open` | Repo is public | Everything, plus a link to the actual PR | Nothing | Nothing |
| `stack-only` | Repo is private, or visibility unknown | Languages, frameworks, infrastructure, databases, model vendors | Third-party vendors, product concepts | Company name, customer names, internal table and column names, unshipped features, cost and revenue figures |
| `maximum` | Never by default; opt in | Language and general domain only | Everything else | All of the above plus framework and infrastructure names |

Every run ends with a redaction log listing each substitution, so specifics can
be restored deliberately if clearance exists.

Under `stack-only`, if the only interesting element of an item is something that
must be dropped, the gate blocks the item instead of shipping a hollow draft.

## 9. Drafting

### 9.1 Post anatomy

1. **Hook.** One line, under 200 characters, standalone before the "see more"
   fold. Three variants offered, drawn from four frameworks: contrarian claim,
   specific number, failure confession, unexpected comparison.
2. **Body.** Under 200 words. Paragraphs of one to three sentences with blank
   lines between them.
3. **Close.** A question the author genuinely wants answered.
4. **First comment block.** Any links, kept out of the post body.

### 9.2 Reconciling with humanizer

LinkedIn house style and the humanizer skill are in direct conflict. Left
unresolved, the skill either produces obvious AI output or argues with itself.
The resolution is explicit and lives in `drafting.md`.

**Absolute — humanizer wins.** No em dashes, no emoji bullets, no rule of three,
no negative parallelism ("it's not just X, it's Y"), no "Here's the thing", no
bold inline-header lists, no curly quotes, no generic uplift close, none of the
AI vocabulary set (delve, leverage, landscape, testament, underscore, robust,
seamless, unlock).

**Preserved — formatting, not voice.** Short paragraphs separated by blank lines
(a real mobile readability constraint), first person throughout, the hook as a
standalone opening line, and a closing question. The closing question is not a
"generic positive conclusion"; it is disqualified unless it asks something
specific that the author would actually read answers to.

### 9.3 Carousel

Emitted only when visual potential scores 3 or higher. Eight to fifteen slides,
one idea per slide, described as content plus a layout note. No image
generation; the outline is for the author or a designer to build.

## 10. Output

1. **Shortlist table** — every surviving cluster with both scores, a one-line
   thesis, and gate status. Blocked items listed separately with reasons.
2. **Full draft of the top pick** — three hooks, body, close, first-comment block.
3. **Carousel outline** — when applicable.
4. **Redaction log** — posture used and every substitution made.
5. **Coverage note** — window, author, cluster strategy, and any signals that
   were unavailable.

## 11. File layout

```
linkedin-post-skill/
  SKILL.md              # workflow, target under 500 words
  README.md             # install, usage, sample output, humanizer credit
  LICENSE               # MIT
  DESIGN.md             # this file
  PLAN.md               # the implementation plan this repo was built from
  rubric.md             # §7 in full, loaded at the scoring stage
  drafting.md           # §8 and §9 in full, loaded at the drafting stage
  install.sh            # one-command install, POSIX shells
  install.ps1           # one-command install, PowerShell
  scripts/
    __init__.py
    harvest.py          # §5.1 CLI, §5.2 assembly, orchestration
    detect.py           # §4 detection layer, plus the shared run_git seam
    collect.py          # §5.2 commits and signals, §5.3 docs, §5.4 test files
    cluster.py          # §5.5 mechanical clustering
    github.py           # optional gh enrichment, §12 degradation
  tests/
  examples/sample-output.md
  examples/validation-notes.md  # §14 acceptance runs, results recorded honestly
```

`harvest.py` was specified as a single file. It shipped as five modules behind
the same CLI, split along the seams §4 and §5 already draw: detection,
collection, clustering, and optional enrichment are independently testable and
degrade independently, which a single file made awkward to verify. The CLI
contract in §5.1 and the schema in §5.2 are unchanged, and `harvest.py` is still
the only entry point.

Repo root is the skill directory, matching the humanizer convention, so install
is a single clone.

## 12. Dependencies

| Dependency | Required | Without it |
|---|---|---|
| git | Yes | Hard error |
| Python 3.9+ | Yes | Hard error |
| `gh` CLI, authenticated | No | No PR bodies, comments, or visibility detection. Falls back to commits and docs; posture defaults to `stack-only` |
| `humanizer` skill | No | Falls back to an inlined checklist of the AI tells that matter most for LinkedIn, and prints the one-line install command |

`humanizer` is MIT licensed, by Siqi Chen, at https://github.com/blader/humanizer.
Credited in README with its license notice. Not vendored.

### 12.1 Distribution

Distribution was not part of the approved design. It was added afterwards, and
is recorded here so the file layout in §11 and the install instructions in
README have a specification to answer to.

Two installers ship: `install.sh` for POSIX shells and `install.ps1` for
PowerShell. Each supports a global install to `~/.claude/skills/linkedin-post`
and a `--local` install to `.claude/skills/linkedin-post` in the current
workspace. Both depend only on `git`, which §12 already requires.

**The install commands in README are verified against the live repository after
push, not before.** The `curl -fsSL .../install.sh | sh` and
`irm .../install.ps1 | iex` forms fetch over the network from a URL that does
not resolve until the repo is public, so nothing before the first push can
exercise the path a stranger actually takes. A README advertising an install
command nobody has run is a broken promise, and the pre-push test suite cannot
detect one: it can only prove the scripts work when invoked from a local
checkout. Closing that gap is a required post-push step, and its result belongs
in `examples/validation-notes.md` alongside the §14 criteria.

Until that step runs, acceptance criterion 1 is satisfied for the author and
unproven for everyone else.

## 13. Deferred, with hooks left in place

- **Voice calibration.** A `voice-profile.md` holding past posts, read at the
  drafting stage and passed to humanizer's voice-calibration mode. SKILL.md will
  carry a marked, commented hook so adding it later touches one file.
- **Automation.** Flags (`--non-interactive`, `--json`) and a scheduled runner.
  The script and stage boundaries are already shaped for it; the agent stages
  are not.

## 14. Acceptance criteria

1. On a repo with conventional commits, a GitHub remote, and authed `gh`, a run
   produces a shortlist, one full draft, and a redaction log.
2. On a repo with freeform commits, no remote, and no `gh`, the same run
   completes, produces a draft, and names every unavailable signal.
3. Re-clustering splits a multi-thesis PR into separate items.
4. Under `stack-only`, no company name, customer name, or internal identifier
   appears in the draft, and the redaction log accounts for each one.
5. The generated draft contains no em dash, no emoji bullet, no rule-of-three
   list, and no AI-vocabulary word.
6. **The judgment test:** run against a repo with at least 30 days of history
   and confirm the top-ranked item is one the author would actually post. If the
   ranking prefers the largest change over the most interesting one, the weights
   are wrong and get retuned. This is the criterion that decides whether the
   rubric works.
7. No file in the repo references any specific private codebase, its layout, or
   its conventions. Verified by running the finished skill against a second,
   structurally different repository.
