---
name: linkedin-post
description: Use when the user wants to post on LinkedIn about work they have done in a code repository, asks what recent work is worth posting about, wants a draft written about a shipped feature or fix, or asks which of their tasks would make a good post. Works in any git repo.
license: MIT
---

# LinkedIn post from repo work

Turn recent authored work in the current git repo into a ranked shortlist of
post ideas and one finished draft.

## Workflow

Run these in order. Do not skip stage 3 even when one item looks obviously best.

### 1. Harvest

```bash
python <this-skill-dir>/scripts/harvest.py --since 14d --repo .
```

`<this-skill-dir>` is wherever this file is installed, for example
`~/.claude/skills/linkedin-post`. That path is the skill; `--repo .` is always
the repo you are standing in, never the skill's own directory. Widen with
`--since 30d` if fewer than three clusters come back. If `meta.warnings`
mentions an author with no commits, re-run with `--author <email>` before
going further.

### 2. Re-cluster

The script clusters mechanically and is often wrong at the story level. Read
each cluster's PR body and linked docs, then split any cluster whose description
needs the word "and". Every final cluster carries exactly one thesis, written as
one sentence. Splitting is common; merging is rare.

### 3. Score

Read `rubric.md` and score every cluster. Produce two tables: post-worthiness
(primary) and complexity (secondary). List gate-blocked items separately with
reasons. Never omit an item silently.

### 4. Select

Show both tables. Recommend the top post-worthiness item and say in one sentence
why it beats the runner-up. Ask the user to confirm or pick another.

### 5. Draft

Read `drafting.md`. Set the redaction posture from `meta.visibility`. Write three
hooks, the body, and a closing question. Every factual claim must trace to a
commit, PR body, or doc in the harvest. Invent nothing.

### 6. Humanize

Invoke the `humanizer` skill on the draft, passing the absolute prohibitions and
preserved formatting from `drafting.md`. If it is not installed, run that
checklist manually and say so.

### 7. Output

1. Shortlist tables, blocked items included
2. The draft: three hooks, body, closing question, first-comment link block
3. Carousel outline, only when visual potential scored 3 or higher
4. Redaction log with the posture used
5. Coverage note: window, author, cluster strategy, unavailable signals

## Rules

- Effort is not post-worthiness. The largest change is rarely the best post.
- Never state a number that is not in the harvest.
- Under `stack-only`, no company name, customer name, or internal identifier
  reaches the draft.
- The draft is a starting point. Say so, and offer to revise.
