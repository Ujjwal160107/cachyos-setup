# Scoring rubric

Load this at the scoring stage. Score every cluster; do not skip low
scorers, they belong in the shortlist as evidence you looked.

## Post-worthiness (primary ranking)

Six criteria, each 0 to 5, weighted. Maximum 60.

| Criterion | Weight | 0 | 5 | Evidence |
|---|---|---|---|---|
| Tension | ×3 | Linear; worked first try | A wrong turn, a revert, or a root cause that was not where you looked | `reverts`, `fix_after_feat`, "turns out / instead / actually / it was not" in PR bodies or commit bodies, rejected options in design docs, review threads demanding change |
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

## The gate

**Confidentiality is a gate, not a criterion.** If the story *is* the product
concept, the item is dropped from the shortlist with the reason printed, rather
than scored low and buried where it looks like a near miss.

A blocked item is listed under a separate Blocked heading with its reason.
Never silently omit it.

## Anti-signals

Subtract from the tension score, or drop outright when nothing else is present:
dependency bumps, lockfile churn, formatting or lint-only changes,
doc-only commits, pure renames, generated-file updates, merge commits, and
changes whose entire story is "I configured a thing."

## Complexity (secondary ranking)

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

## Worked example

Score this cluster by hand. It is the calibration anchor for every score that
follows.

```
Cluster: "never let the third-party fallback fail the pipeline run"
  2 commits, 1 area, span 1 day, 0 reverts, 1 fix_after_feat,
  numbers_found: ["402"], docs: 1 design doc listing a rejected alternative

  Tension            4  x3 = 12   fix-after-feat plus a rejected alternative in the doc
  Transferable       5  x3 = 15   "isolate third-party failure from your own pipeline"
                                  survives stripping every product noun
  Concrete numbers   2  x2 =  4   one status code, no before/after figures
  One-idea           5  x2 = 10   single thesis
  Visual potential   3  x1 =  3   before/after error-handling diff
  Freshness          5  x1 =  5   this week
                          ----
                            49 / 60   Gate: PASS under stack-only
```

## Scoring discipline

- Score from the evidence column, not from impression.
- A cluster with no design doc, no PR body, and no commit body beyond bare
  subjects caps Tension at 2, because then there is genuinely no record of a
  wrong turn anywhere. A rationale written into commit bodies is a record:
  read them before applying the cap.
- Never invent a number that is not in `numbers_found` or a diffstat.
