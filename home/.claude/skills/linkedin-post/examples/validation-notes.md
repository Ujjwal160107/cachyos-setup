# Acceptance validation notes

`DESIGN.md` §14 lists seven acceptance criteria. This file records what
happened when each was run for real, on 2026-08-03, against real
repositories rather than fixtures.

It records failures and partial results as such. A criterion that could not be
tested is marked that way rather than claimed.

## Repositories used

Private repositories are described by shape only, never by name, layout, or
product concept, per criterion 7. One public repository is named because it
belongs to the author and naming it makes the evidence checkable.

| Ref | What it is | Commits in window | Convention | Remote | Visibility |
|---|---|---|---|---|---|
| A | `github.com/Ujjwal160107/Casino-`, a TypeScript Discord bot | 148 | conventional | GitHub | public |
| B | scratch repo built for this run | 3 | freeform | none | n/a |
| C | a private TypeScript and Node web app | 10 | freeform | GitHub | private |
| D | this repository | 32 | conventional | **none** | n/a |

**This repository does not satisfy criterion 1.** It has conventional commits,
but no git remote at all, so the "GitHub remote and authed `gh`" half of the
criterion cannot be exercised against it. Repo A was used instead. `gh` itself
is installed (2.92.0) and authenticated on this machine, so the absence is the
remote, not the tooling.

`gh` is deliberately hidden from the process for criterion 2 by running with a
`PATH` that excludes its directory.

## Criterion 1: conventional commits, GitHub remote, authed `gh`

**Status: PASS**, against repo A.

```
python scripts/harvest.py --since 30d --repo <A> --json crit1.json
```

| Fact | Value |
|---|---|
| host / visibility | `github` / `public` |
| convention detected | `conventional` |
| capabilities | `gh: true, gh_auth: true, pr_enrichment: true` |
| default branch | `main` |
| clusters | 43 |
| strategies used | `scope-week` x42, `branch` x1 |
| areas | 1 (`.`, root, `["typescript", "javascript"]`) |
| private identifier in output | none, and none expected: the repo is public |

One warning, and it is correct:

> PR lookup by commit is capped at 20 clusters per run; 23 older cluster(s) were
> left unenriched and report pr: null even if a PR exists. Narrow --since to
> bring them inside the cap.

43 clusters against a `MAX_PR_LOOKUPS` of 20 is exactly the case the cap exists
for, and the run announced it rather than truncating silently.

**PR enrichment verified end to end, separately.** The first run resolved zero
PRs, which looked wrong. It is not: the five PRs merged inside the window were
authored by a different account, so the `--author` filter removed their commits
before clustering. Re-running with that account as `--author` resolved PR #5
through linkage strategy (c) with body, `additions` 551, `deletions` 139,
`changed_files` 16, `url`, and `merged_at` all populated. Strategy (c) was also
called directly against a known commit and returned the right number.

## Criterion 2: freeform commits, no remote, no `gh`

**Status: PASS**, with one nuance recorded below.

Repo B, three freeform commits, no remote, run with `gh` removed from `PATH`.

| Fact | Value |
|---|---|
| host / visibility | `none` / `unknown` |
| convention detected | `freeform` |
| capabilities | `gh: false, gh_auth: false, pr_enrichment: false` |
| default branch | `main`, found by the probe fallback |
| clusters | 1 |
| strategy used | `day` |
| private identifier in output | none |

The run completed and produced a usable document. Warning emitted:

> gh CLI unavailable: no PR bodies, review comments, or visibility detection.
> Redaction posture defaults to stack-only.

**Nuance.** Two things were absent, `gh` and the remote, and only the `gh` cause
was named. The warning chain in `harvest.build` is `if not gh_ok ... elif ...
elif host == "none"`, so the first matching cause wins. Every unavailable
*signal* is still named accurately, because the `gh` warning covers PR bodies,
review comments and visibility, which is the same set the missing remote would
cost. But a reader who installs `gh` to fix this will then discover the second
cause. Criterion 2 asks that every unavailable signal be named; that holds. It
does not quite hold for causes.

## Criterion 3: re-clustering splits a multi-thesis item

**Status: PARTIAL. The exact form in the criterion could not be tested.**

The criterion says "splits a multi-thesis PR". No multi-thesis PR was available
in any accessible repository: repo A's five PRs carry one commit each, and repos
B, C and D have no PRs at all. So the PR-specific form is untested, and this
criterion is not claimed as a pass.

The splitting operation itself was exercised on real multi-thesis clusters:

**A 13-commit cluster** (`scope-anticheat-...`) carries at least three theses and
splits into three single-sentence items: an atomic claim primitive plus seven
duplicate-claim races closed with it; a compare-and-swap that silently matched
nothing; and a test harness moved in-process because the container runtime could
not host a replica set on this platform.

**A five-commit cluster** splits into five, because it contained five separate
PRs. That is a defect, not a feature, and it is recorded under Findings below.

## Criterion 4: `stack-only` drops private identifiers

**Status: PASS**, against repo C.

Repo C reports `visibility: private`, which selects `stack-only` automatically,
as `drafting.md` §1 requires. A full draft was written under that posture and
shipped with a redaction log accounting for six substitutions: the platform
vendor name (in four commit subjects), a vendor-named environment variable, a
vendor build-config filename, the repository name, the author email, and the
product concept.

Verified mechanically rather than by eye. The repository's own opt-in guard,
`TestNoPrivateRepoReferences`, was switched on by writing a `.private-terms`
file holding the tokens that would identify any private fixture repository or
any individual contributor. With the guard active the whole suite passes, which
means no Markdown file in this repository, including this one, contains any of
them. The guard file is gitignored and is not part of the commit.

## Criterion 5: the draft obeys the prohibitions

**Status: PASS**, checked mechanically on both drafts produced during this
validation.

Checked for: em dashes, en dashes, curly quotes, emoji, all twelve banned
vocabulary words, negative parallelism, "Here's the thing", body under 200
words, hooks under 200 characters, and paragraphs of at most three sentences.

| Draft | Posture | Body words | Result |
|---|---|---|---|
| repo A story | `open` | 175 | pass |
| repo C story | `stack-only` | 171 | pass |

**The check caught a real violation before it shipped.** The first version of
the `open` draft had a four-sentence paragraph, against a hard limit of three in
`drafting.md` §9. It was found by running the check, not by reading the draft,
and was split into two paragraphs. Recorded here because a validation note that
only reports passes is not worth much.

## Criterion 6: the judgment test

**Status: PASS.** The ranking does not prefer the largest change.

Run against repo A, which has roughly eight months of history and 148 authored
commits in a 30-day window, producing 43 clusters. Every cluster was scored by
hand against `rubric.md`.

**This repository does not qualify for this criterion.** Its history runs
2026-07-27 to 2026-08-03, which is 7 days, not the 30 the criterion requires.

The largest change by every raw measure is a website rebuild: 9,290 lines of
churn, 30 commits, 55 new files, spanning 6 days. It ranks near the bottom.

| Cluster | Churn | Post-worthiness | Why |
|---|---|---|---|
| compare-and-swap that matched nothing (split out of the anti-cheat cluster) | 2,612 across the parent | **50 / 60** | Tension 5, transferable 5, one idea 5 |
| anti-cheat cluster, unsplit | 2,612 | 46 / 60 | Same story, but carrying three theses, so one-idea drops to 3 |
| deploy reliability cascade | 110 | 42 / 60 | Tension capped at 2 by a rubric rule, see below |
| item rebalancing | not top 8 | 29 / 60 | Highest mechanical tension signal in the run, weakest actual story |
| **website rebuild (largest)** | **9,290** | **21 / 60** | Transferable 1, one idea 1, no design doc, style and copy anti-signals |

The largest change scores 21 and the winner scores 50. Scope is doing no work in
the ranking, which is what §7.1 intends.

**Top-ranked item:** "The compare-and-swap I added to stop double-claims never
matched a row, because a field that was never written is not the same as a field
explicitly set to null, even though the client reads both back as null."

**Would the author actually post it?** Yes. It is a specific, non-obvious,
transferable failure with a clean before-and-after and no product context
needed to understand it. It is also the item a reader could act on Monday, which
is what the ×3 weight on transferability is for.

`rubric.md` was **not** retuned. The condition the criterion names for retuning,
a ranking that prefers the largest change, did not occur. A separate rubric
defect was found and is recorded under Findings rather than fixed, because it is
outside what this criterion authorises changing.

## Criterion 7: portability to a structurally different repo

**Status: PASS**, against repo C, which was **found on this machine, not
constructed**.

Compared with this repository, repo C differs on all three axes the criterion
names:

| Axis | This repo | Repo C |
|---|---|---|
| Language | Python | TypeScript and Node |
| Layout | flat `scripts/`, `tests/`, `examples/` | nested application and server trees with a separate build output |
| Convention | conventional commits | freeform, capitalised subjects |

Results: `freeform` detected correctly, `day` strategy selected, 1 cluster of 10
commits, 6 design docs discovered, `visibility: private` read through `gh`, no
warnings (nothing was unavailable), no crash. Languages detected as
`["typescript", "python"]`, which is correct: the repository really does contain
two Python files in a reference directory.

**No output referenced this repository's structure.** The document names only
repo C's own paths. No skill file was consulted for repo shape, and nothing in
the harvest mentions `harvest.py`, `rubric.md`, or any other path belonging to
the skill.

Full suite after all runs:

```
Ran 160 tests in 34.142s
OK
```

Zero skipped, because the private-reference guard was active.

## Findings

Things the runs revealed. None are fixed here; `scripts/` was out of scope for
this task, and each is recorded for triage.

**1. Clusters can collapse several PRs into one and then mislabel them.**
The most serious finding. Five commits, each belonging to a different merged PR,
landed in one `scope-week` cluster because they shared a scope and an ISO week
and none carried a `(#N)` suffix. `harvest.build` then probed the cluster's
newest commit for a PR number and attached **PR #5's body to all five**. Four of
the five commits are now backed by a PR body describing work they did not do.
Verified by resolving each commit separately: they map to PRs 5, 4, 3, 2 and 1.
This matters beyond tidiness, because `SKILL.md` requires every factual claim in
a draft to trace to a commit, PR body, or doc, and §7.1 reads PR bodies as
primary Tension evidence. Here that evidence is wrong for four items out of five.

**2. `detect_areas` never implements the middle tier of §4's fallback chain.**
§4 specifies "Workspace manifests, then top-level directories, then file
extensions". The implementation checks workspace manifests and otherwise returns
a single root area named `.`. Every repository used here is a non-monorepo, so
`area_count` was 1 in every run, in a repo with a dozen meaningful top-level
directories. §7.3 lists "areas crossed" first among its complexity signals, so
that signal is constant, and therefore dead, for any repository without a
workspace manifest.

**3. `numbers_found` is polluted by commit trailers.** The anti-cheat cluster
reports `numbers_found: ["4.8", "1M"]`. Neither is a metric. Both come from
`Co-Authored-By: Claude Opus 4.8 (1M context)` trailers in the commit bodies.
`numbers_found` feeds the ×2 "Concrete numbers" criterion, so trailer text is
being scored as evidence. This repository's own commits use the same trailer
convention, so it would do the same here.

**4. The rubric's Tension cap suppresses the best story in a solo-developer
repo.** `rubric.md` states that "a cluster with no design doc and no PR body
caps Tension at 2, because there is no record of a wrong turn." The deploy
cluster has neither, yet its four commit bodies record an explicit cascade: a
deploy was serialised with a file lock, which exposed that the handler answered
success before the work ran; making it wait then corrupted the HTTP response,
because for that invocation stdout *was* the TCP socket; waiting then stalled CI,
so the webhook went back to acknowledging immediately with a bounded wait. A
separate commit records an executable bit lost to a Windows checkout. That is a
textbook root-cause-not-where-you-looked story, in 110 lines of churn. The cap
scores its Tension 2 instead of 5, costing 9 weighted points and the top spot.
The Tension evidence column lists PR bodies and design docs but never commit
bodies, even though §5.2 collects `body` for every commit. Suggested change:
allow commit bodies as Tension evidence, and cap Tension only when no
prose rationale exists anywhere.

**5. Minor: only one degradation cause is reported when several apply.** See the
nuance under criterion 2.

**Investigated and not a bug.** Console output showed replacement characters in
commit subjects containing em dashes. The JSON is clean: 11 commits carry a real
U+2014 and the document contains no U+FFFD anywhere. The corruption was the
Windows console's code page, not the tool. The encoding work in `run_git` and
`write_stdout` is doing its job.

## Not covered by this file

Criterion 1 is satisfied here for a user standing in a repository. The install
commands advertised in `README.md` fetch over the network from URLs that do not
resolve until this repository is public, so they cannot be exercised before the
first push. `DESIGN.md` §12.1 records that obligation. Until it is discharged,
the install path is proven for a local checkout and unproven for a stranger.

## Live install verification (after the first push)

Run on 2026-08-03, immediately after `main` was published to
`https://github.com/Ujjwal160107/linkedin-post-skill`. Both runs happened in a
scratch directory outside any checkout, so they exercise exactly what a
stranger's machine would do.

**POSIX sh, workspace scope.** The advertised `install.sh` was fetched from the
raw `main` URL and run with `--local`. First run cloned and landed
`SKILL.md` at `.claude/skills/linkedin-post/SKILL.md` (PUBLIC INSTALL OK).
A second run took the update path (`updating existing install`) instead of
failing (RE-RUN UPDATE OK).

**PowerShell, workspace scope.** The advertised scriptblock form
(`& ([scriptblock]::Create((irm .../install.ps1))) --local`) fetched from the
raw `main` URL cloned and landed `SKILL.md` in the same layout
(PUBLIC INSTALL OK).

**Not exercised: the two global one-liners.** They are the same code path with
a different target directory, but running them would write into the real
`~/.claude/skills/` on the validation machine, which this validation forbids
itself from touching. The scope-selection logic they differ by is covered by
`TestInstallers` and the pre-push probe runs.

The obligation recorded in `DESIGN.md` §12.1 is discharged: the install path
is now proven for a stranger, not only for a local checkout.
