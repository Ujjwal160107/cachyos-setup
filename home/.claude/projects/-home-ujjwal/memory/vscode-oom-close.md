---
name: vscode-oom-close
description: VS Code vanishing on ASGRD was OOM-kill plus systemd OOMPolicy=stop, not a VS Code bug
metadata:
  type: project
---

On 2026-09-08 the "VS Code randomly closes" symptom was root-caused: a vitest run in
the integrated terminal grew to 6.2 GB, zram swap hit 100% full (free swap 48 kB), the
kernel OOM-killed it, and systemd's default `OOMPolicy=stop` then tore down the whole
`app-code-*.scope` — so the editor died with no crash dialog.

Two fixes applied:
- `~/.config/systemd/user/app-.scope.d/oom.conf` sets `OOMPolicy=continue` for all
  `app-*.scope` units. Not tracked in any repo — add it to [[cachyos-setup-repo]]
  before a rebuild or it is lost.
- `apps/web/vitest.config.ts` in ~/dev/cruitical gained `maxWorkers: 6` (threads pool
  shares one process, so one worker per core on 20 cores = heap cost).

**Why:** 16 GB RAM with zram sized at 100% of RAM leaves no headroom once Zen, Chrome,
Discord, Slack, next dev, Docker and several claude processes are up; VS Code scopes
alone peaked at 7.4–9.4 GB.

**How to apply:** if the editor vanishes again, check `journalctl -k | grep oom-kill`
before suspecting VS Code. If a whole GUI session disappears instead, that is a
different failure — Hyprland segfaults in the logs were shutdown artifacts, not causes.
