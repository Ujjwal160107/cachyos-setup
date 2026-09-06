---
name: hands-free-mode
description: Use when the user wants an unattended or autonomous run - "hands free", "don't ask me anything", "run on your own for hours", "keep going until it's finished", "no permission prompts", "don't stop to confirm" - or hands over a multi-step job they intend to walk away from.
---

# Hands-Free Mode

## Overview

The user has left. Nobody will answer a question, approve a plan, or say "continue."
Every stop is a stall that wastes the entire unattended window.

**Core principle: a hands-free run ends in exactly two ways — the work is done and verified, or you hit a hard stop. Nothing else ends the run.**

## Session Contract

State this once at the start, then work. Do not restate it.

1. **Ledger first.** Decompose the request into a TodoWrite ledger before touching anything. Every item gets a verification command — the shell command that proves it works. An item with no verification command is not a real item; split it until each one has one.
2. **Decide, log, proceed.** Ambiguity is resolved by you, not by asking. Write the choice into an `ASSUMPTIONS` running list and keep moving.
3. **Work the loop** (below) until the ledger is empty.
4. **Verify, then report** in the closing format (below).

## The Loop

```
while ledger has unfinished items:
    pick the next unblocked item
    implement it
    run its verification command
    if green  -> mark done
    if red    -> fix and re-run (attempt 2, then 3)
    if red x3 -> mark PARKED with the error text, move to the next item
re-run the full verification suite over everything
if anything red -> the item goes back in the ledger, loop again
```

Nothing here is optional and nothing here waits on the user. A parked item does not end the run — the *other* items still need doing. Come back to parked items after the ledger drains; a fix elsewhere often unblocks them.

## Never Stop to Ask

Under an unattended run these are all violations, not judgment calls:

| The urge | What to do instead |
|---|---|
| "Which approach do you prefer?" | Pick the one that is easier to reverse. Log it in ASSUMPTIONS. |
| "Should I continue?" | Continue. That is the entire point of the mode. |
| "Let me confirm before I proceed." | Proceed. Confirmation is unavailable. |
| "This is ambiguous, I need input." | Choose the reading that satisfies the most of the request. Log it. |
| "I've done the main part — good stopping point." | The ledger is the stopping point. Not your sense of momentum. |
| "I'll present options and let them choose." | Options are a question wearing a hat. Choose one. |
| "The next part is risky, I should check in." | Risky ≠ hard stop. Only the Hard Stops list ends a run. |
| "Tests fail for an unrelated reason, so I'm blocked." | Three attempts, then PARK it and take the next item. |
| "I've been at this a while, I should report back." | Report at the end. Elapsed time is not a completion signal. |

**Violating the letter of this contract is violating the spirit of it.** An unattended run that ends with a question delivered nothing — the user reads it hours later, having lost the whole window.

## Hard Stops

Stop the run *only* for these. They are irreversible or reach outside the machine:

- Sending or publishing anything outward — email, Slack, a PR comment, a deploy, a post
- Spending money or provisioning paid resources
- Destroying work the task did not create: force-push, `git reset --hard`, dropping a database, deleting uncommitted changes
- Rotating, revoking, or committing credentials
- Anything the user's `permissions.deny` list blocks (see below)

If the user's original request explicitly asked for one of these, it is authorized — do it. The list is for actions you'd be *adding on your own*.

Hitting a hard stop parks that item. It does not end the run. Finish everything else, then report the stop.

## Deny Rules Still Fire

`bypassPermissions` does **not** disable `permissions.deny`. A denied command returns a permission error mid-run, verified by direct test.

When a command is denied: do not retry it verbatim, and do not try to sneak past the pattern. Find another route to the same outcome (`git revert` instead of `reset --hard`, targeted deletes instead of `rm -rf`) or PARK the item and note which rule blocked it. Removing the user's own safety rule to get past it is never the answer.

## Closing Report

End the run with exactly this, and nothing else:

```
DONE:      <items completed, each with the verification command that passed>
PARKED:    <items not completed, each with the actual error text and what you tried>
ASSUMPTIONS: <every judgment call you made instead of asking>
NEXT:      <what a human should decide or do first>
```

Paste real command output for the verification claims. **Never write "done", "fixed", or "passing" without the output that proves it** — an unattended run is precisely where an unverified claim survives longest before anyone catches it.

## Red Flags — you are about to break the run

- You are drafting a sentence that ends in "?"
- You are about to use AskUserQuestion
- You typed "Let me know" or "Would you like"
- You are summarizing progress while the ledger still has items
- You are calling something complete without having run its verification command
- You are treating one failing item as a reason to stop the other nine

All of these mean: **make the call, log it, take the next item.**

## Launching a Hands-Free Run

Permission prompts are harness-level, not skill-level. This skill governs behavior; the settings govern prompting. For a truly silent run you want both:

```bash
claude --dangerously-skip-permissions
```

Or persist it in `~/.claude/settings.json`:

```json
{ "permissions": { "defaultMode": "bypassPermissions" } }
```

To keep the run alive across turns for hours, pair this skill with `/loop` — it re-enters on an interval and the ledger survives, so an interrupted run picks up where it stopped.
