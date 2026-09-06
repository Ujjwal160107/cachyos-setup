# Drafting rules

Load this at the drafting stage, once a cluster has been selected and
scored. Consumes the selected cluster and `meta.visibility`; produces no
code, only the draft that stages 5 and 6 of `SKILL.md` show the user.

`DESIGN.md` stays the spec of record. This file is what actually loads
into the agent's context when it writes the post, so the passages below
are copied from `DESIGN.md` §8 and §9 on purpose rather than referenced.
A reference the agent cannot follow at drafting time is worse than a
copy that costs a few hundred tokens.

## 1. Redaction posture

| Posture | Default when | Names freely | Abstracts | Drops |
|---|---|---|---|---|
| `open` | Repo is public | Everything, plus a link to the actual PR | Nothing | Nothing |
| `stack-only` | Repo is private, or visibility unknown | Languages, frameworks, infrastructure, databases, model vendors | Third-party vendors, product concepts | Company name, customer names, internal table and column names, unshipped features, cost and revenue figures |
| `maximum` | Never by default; opt in | Language and general domain only | Everything else | All of the above plus framework and infrastructure names |

Every run ends with a redaction log listing each substitution, so
specifics can be restored deliberately if clearance exists.

**Default selection, keyed to `meta.visibility`:**

- `meta.visibility: public` selects `open`.
- `meta.visibility: private` or `meta.visibility: unknown` selects
  `stack-only`.
- `maximum` is never chosen automatically. Use it only when the user
  explicitly requests it for this run.

**The hollow-draft rule.** Under `stack-only`, if the only interesting
element of an item is something that must be dropped, the gate blocks
the item instead of shipping a hollow draft.

## 2. Redaction log format

Every draft ships with a redaction log: a two-column table, one row per
substitution made while applying the posture above, plus a final line
naming the posture used.

| Original | Replacement |
|---|---|
| `<company name found in source>` | (dropped entirely; company names are never given a pseudonym) |
| `<internal service path found in source>` | `services/api` |
| `<author email found in source>` | `dev@example.com` |

Posture used: `stack-only`.

(The rows above are a template. Populate `Original` with what the
detection layer actually found for this run, and `Replacement` with what
the draft shows instead. Never leave the template placeholders in a real
draft.)

## 3. Post anatomy

1. **Hook.** One line, under 200 characters, standalone before the "see
   more" fold. Three variants offered, drawn from four frameworks:
   contrarian claim, specific number, failure confession, unexpected
   comparison.
2. **Body.** Under 200 words. Paragraphs of one to three sentences with
   blank lines between them.
3. **Close.** A question the author genuinely wants answered.
4. **First comment block.** Any links, kept out of the post body.

## 4. The four hook frameworks

One worked example per framework, each written to the rules the rest of
this file states, so the calibration anchor and the rule sit side by
side.

- **Contrarian claim.** "Retries made our reliability worse."
- **Specific number.** "One third-party API returned 402 and took down a
  pipeline that had nothing to do with it."
- **Failure confession.** "I spent two days debugging our code. The bug
  was that we trusted someone else's."
- **Unexpected comparison.** "Our error handling had no fuse box. One bad
  circuit took the house."

Each example is one line, under 200 characters, and stands on its own
before the "see more" fold, per section 3 above.

## 5. Absolute prohibitions (humanizer wins)

Run this checklist against your own draft before showing it to the user.
Every box should be checked before the draft ships.

`DESIGN.md` §9.2 bans, copied here verbatim:

- [ ] No em dashes.
- [ ] No emoji bullets.
- [ ] No rule of three.
- [ ] No negative parallelism ("it's not just X, it's Y").
- [ ] No "Here's the thing."
- [ ] No bold inline-header lists.
- [ ] No curly quotes.
- [ ] No generic uplift close.
- [ ] None of the AI vocabulary set: delve, leverage, landscape,
      testament, underscore, robust, seamless, unlock.

That is the spec's own eight-word vocabulary ban, exactly as `DESIGN.md`
§9.2 states it. Beyond that spec, the validator that enforces this file
also bans four more words, because they are real AI tells that cost
nothing to also avoid. These four are an extension added here, not part
of `DESIGN.md` §9.2:

- [ ] vibrant
- [ ] tapestry
- [ ] pivotal
- [ ] showcase

Combined, the checklist above and its extension cover twelve banned
words: delve, leverage, landscape, testament, underscore, robust,
seamless, unlock, vibrant, tapestry, pivotal, showcase.

## 6. Preserved formatting (formatting, not voice)

`DESIGN.md` §9.2 preserves, copied here verbatim:

Short paragraphs separated by blank lines (a real mobile readability
constraint), first person throughout, the hook as a standalone opening
line, and a closing question. The closing question is not a "generic
positive conclusion"; it is disqualified unless it asks something
specific that the author would actually read answers to.

**The closing-question test.** Would you read the answers? If not, the
question is decoration. Rewrite it.

## 7. humanizer handoff

If the humanizer skill is installed, invoke it on the draft and pass the two lists above as constraints. If not, run the checklist in section 5 manually and tell the user: `git clone https://github.com/blader/humanizer.git ~/.claude/skills/humanizer` improves results.

## 8. Carousel spec

Emitted only when visual potential scores 3 or higher. Eight to fifteen
slides, one idea per slide, described as content plus a layout note. No
image generation; the outline is for the author or a designer to build.

**Slide template:**

1. Slide 1 is the hook, verbatim from section 3 above.
2. Slides 2 through N are one idea each, with a layout note describing
   what should be on the slide.
3. The final slide is the closing question.

## 9. Length discipline

These are hard limits, not targets.

- Hook: under 200 characters.
- Body: under 200 words.
- Paragraphs: one to three sentences.
