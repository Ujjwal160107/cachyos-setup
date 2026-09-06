# Working defaults

These apply in every project. A project's own `CLAUDE.md` or `.claude/rules/` wins over
anything here.

## Design principles — the default, not an absolute

Apply these by default. When you deliberately don't, say which one you're trading away
and why — don't just quietly skip it.

- **DRY** — Before writing something that resembles code that already exists, find the
  existing one and extend it. The same derivation at two call sites is a bug: give it one
  seam. Never fork a near-duplicate of a workflow, component, endpoint, or helper.
- **SOLID** — Depend on the abstraction the codebase already has, not a concrete
  implementation. Adding a variant should be a new entry in a registry, not a new branch
  in a dispatcher.
- **SRP** — One reason to change per module, and the sharpest of these in practice.
  Name the single responsibility in one sentence; if the sentence needs an "and", the
  module is two modules. A function that decides, formats and persists has three reasons
  to change and will be edited by three unrelated tasks.
- **SOC** — Keep the layers apart: no SQL in a component, no HTTP status or transport
  concern in a core module, no business rule in a route handler or a serializer. The test
  is whether you could swap the layer (REST for a queue, Postgres for anything) without
  touching the logic underneath it.
- **KISS** — Prefer the boring shape. A clever rule that handles a case nobody has hit
  costs more to read forever than it saves once.
- **YAGNI** — Don't build for a caller that doesn't exist. No field written but read
  nowhere, no guard for a state the caller structurally cannot produce, no generated
  config for a combination the producer cannot emit.

When two of these pull against each other it is almost always DRY vs. KISS, and at
N=2 the answer is usually KISS: two similar things are not yet a pattern. Abstract on
the third.

## Following the surrounding code

If the code around your change deliberately does something these principles argue
against, follow the surrounding code and mention the tension. Don't "fix" it as a side
effect of an unrelated task.
