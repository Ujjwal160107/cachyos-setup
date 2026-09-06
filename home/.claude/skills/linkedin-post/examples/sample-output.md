# Sample output: a full run against `example-repo`

This is a complete run of `/linkedin-post` against a fictional repository
called `example-repo`, using the default 14-day window and an authenticated
`gh` CLI. It shows every stage of the output: the shortlist, the blocked
item, the finished draft, the carousel outline, the redaction log, and the
coverage note.

## 1. Shortlist

| Rank | Cluster | Post-worthiness | Complexity | Evidence | Thesis |
|---|---|---|---|---|---|
| 1 | Idempotency key stops duplicate webhook processing | 47/60 | Low (1 area, no new abstraction, half-day span) | 1 fix-after-feat, a short design note, 0 reverts | A timeout retry replayed a webhook without checking whether the first attempt had already run. |
| 2 | Request coalescing ends a cache stampede | 42/60 | Medium (2 areas, one new coalescing module, 3-day span) | 1 fix-after-feat, PR body describing the outage | A cold cache under concurrent load turned one slow query into a hundred identical ones. |
| 3 | A shared mutable fixture made the integration suite flaky | 32/60 | Low (1 area, no new abstraction, 1-day span) | Small PR, no design doc | Tests failed in a different order depending on which one ran first, because they shared one mutable object. |
| 4 | Config loader split into two files | 13/60 | Low (1 area, no new abstraction, same day) | No PR, no design doc, tension capped at 2 | The config loader was split into a parser and a validator, with no behavior change. |

Recommendation: the idempotency-key cluster is the top pick over the
cache-stampede cluster because a fingerprint check applies to any consumer
that retries a call with a side effect, while request coalescing only helps
once a caching layer already exists to coalesce against.

## 2. Blocked

| Cluster | Reason |
|---|---|
| Tiered pricing for the paid plan | Gate: the story is the pricing change itself, a product concept that stack-only cannot abstract without emptying the post. |

## 3. Draft

**Hooks** (pick one to post; all three pass the length and content checks)

1. Specific number: A timeout retry replayed 23 webhooks in one hour, and 4 of them got processed twice.
2. Failure confession: I spent a day chasing a bug in our own code before I found out the real bug was trusting a retry to be safe.
3. Unexpected comparison: Our webhook handler had no turnstile. One retry let the same event through twice.

**Body** (using hook 1)

Our webhook consumer had a five-second timeout. When a downstream call took longer than that, we retried the whole message instead of the slow call alone.

That seemed safe. It was not. The retry re-ran a handler that already had a side effect from the first attempt, and neither attempt knew about the other.

In one hour, 23 webhooks got replayed. Four of them ran twice before we noticed, because nothing on our side remembered which ones had already been handled.

The fix was not a longer timeout. It was an idempotency key: every incoming webhook gets a fingerprint, and a second delivery with the same fingerprint is dropped before it reaches the handler.

Retrying a network call is standard advice. Retrying a call that already had a side effect, with no way to tell the second attempt it already happened, is a different problem. That distinction cost us four duplicate runs before we saw it.

**Close**

If your retry logic assumes the first attempt failed cleanly, what happens when it did not?

**First comment**

(No link included; the source repository is private under this run's stack-only posture.)

## 4. Carousel outline

Visual potential scored 3, so a carousel is included. Nine slides.

1. Hook, verbatim: "A timeout retry replayed 23 webhooks in one hour, and 4 of them got processed twice." Layout: title slide, hook set large and left-aligned on a plain background, no logo.
2. The setup: a webhook consumer with a five-second timeout; on timeout, the whole message was retried instead of the slow call alone. Layout: two-box diagram, inbound webhook on the left, consumer box on the right, a clock marking the timeout.
3. The assumption: a retry means the first attempt failed cleanly and never ran. Layout: one sentence, centered, in quotes, alone on the slide.
4. The numbers: 23 webhooks replayed in one hour, 4 processed twice, 0 alerts fired. Layout: three large stacked numbers with a one-line label under each.
5. Neither attempt knew about the other, so nothing local caught the duplicate before it landed. Layout: two arrows pointing at the same box from different directions, neither aware of the other.
6. The fix was not a longer timeout; it was a fingerprint on every incoming webhook. Layout: before-and-after diagram, timeout value crossed out on the left, fingerprint icon added on the right.
7. A second delivery with the same fingerprint gets dropped before it reaches the handler. Layout: simple flowchart, incoming webhook, a decision diamond for "seen before," two paths out.
8. Retrying a call that failed and retrying a call that already had a side effect are different problems. Layout: split slide, left side labeled clean retry, right side labeled side-effect retry, a check mark on one side and a warning mark on the other.
9. Closing question, verbatim: "If your retry logic assumes the first attempt failed cleanly, what happens when it did not?" Layout: closing slide, question centered, plenty of white space, no logo.

## 5. Redaction log

| Original | Replacement |
|---|---|
| `Anchorpoint` (company name found in commit history) | (dropped from the draft; company names are never given a pseudonym) |
| `services/webhook-intake/consumer.go` (internal service path) | `services/webhook-consumer` |
| `j.rivera@anchorpoint.example` (author email found in source) | `dev@example.com` |
| `Sendwave` (third-party vendor named in the PR body) | `a third-party webhook provider` |

Posture used: `stack-only`.

## 6. Coverage note

Window: 2026-07-19 to 2026-08-02 (14 days, the default). Author:
`dev@example.com`, selected automatically as the most active of 3 candidates
who committed in the window. Clustering: 3 clusters resolved by PR suffix, 1
by branch, 1 by scope-and-week, against a repo that used conventional
commits a little over half the time. `gh` was available and authenticated,
so PR bodies and review comments were pulled wherever a PR existed. Repo
visibility read as private, so stack-only redaction applied by default. The
config-loader cluster had no PR, no design doc, and nothing but bare
subjects in its commit bodies, which is why its tension score is capped low
rather than scored on impression.
