---
name: cachyos-setup-repo
description: Private dotfiles/rebuild repo at ~/dev/cachyos-setup mirroring $HOME; how install.sh and sync.sh work and when each is needed
metadata: 
  node_type: memory
  type: project
  originSessionId: 1ca248b8-e40d-450f-8d68-12ff828c1380
  modified: 2026-09-06T19:27:53.661Z
---

Since 2026-09-07 this machine's whole setup is captured in the private repo
`Ujjwal160107/cachyos-setup`, cloned at `~/dev/cachyos-setup`. 1243 files: ii/Hyprland
desktop, shells, theming, audio, editors, package lists (215 pacman / 35 AUR / 1 flatpak),
wallpapers, and `~/.claude` config including these memory files.

`manifest.txt` is the single source of truth — 78 `group:path` lines relative to `$HOME`.
Both scripts read it: `install.sh` symlinks repo→`$HOME` (idempotent, moves anything it
displaces to `~/config-backup-<ts>/`), `sync.sh` copies live config back the other way and
refreshes package lists. Adding a tracked path means adding a manifest line, nothing else.

**Why:** The Windows→CachyOS migration was painful and undocumented; the point is that the
next rebuild is scripted rather than remembered. See [[windows-migration-2026-09]].

**How to apply:** `install.sh` has **not** been run on this machine — the configs in
`$HOME` are still real files, so changes need `./sync.sh` before committing. If a future
session runs `install.sh`, that flips: tracked files become symlinks into the repo and edits
show up directly in `git status` with no sync step. Check with `ls -l ~/.config/hypr`.

`sanitize.py` runs inside `sync.sh` and redacts secrets from repo copies (currently
`env.GITHUB_PERSONAL_ACCESS_TOKEN` in `.claude/settings.json`); it exits non-zero if any
credential-shaped string survives under `home/`. Add a handler there before tracking any
file that holds a token. The two ii QML patches from [[wallpaper-engine-setup]] are stored
as re-appliable diffs in `patches/ii-dots/` against pinned ii commit `97c5bc6`.
