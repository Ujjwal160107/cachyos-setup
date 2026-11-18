---
name: subagent-model-sonnet
description: "Spawn general-purpose subagents with model \"sonnet\", not the inherited model"
metadata:
  node_type: memory
  type: feedback
  originSessionId: dc58b342-f84d-4648-8134-68b1361edd27
  modified: 2026-11-11T19:12:14.536Z
---

When launching general-purpose agents (Agent tool), pass `model: "sonnet"`.

**Why:** User asked for this explicitly on 2026-11-12 while I had 4 transcription agents running on the inherited Opus model; I restarted them on Sonnet.

**How to apply:** Default every general-purpose subagent to Sonnet unless the user says otherwise for that task. Related: [[study-guide-pdfs]].
