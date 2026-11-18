---
name: hyprcursor-startup-race
description: "Hyprland SEGV at login from setcursor racing dynamic-cursors' theme load; fixed 2026-10-31 by env theme and no startup setcursor; ii update can undo it"
metadata:
  node_type: memory
  type: project
  originSessionId: ade9e613-934c-4a91-b10c-15d88c913780
  modified: 2026-10-30T19:09:41.532Z
---

On 2026-10-31 Hyprland segfaulted at login. libhyprcursor's parser keeps a global `currentMeta`
pointer, so two theme parses at once crash. dynamic-cursors loads the theme on a background thread
once at startup (~150 ms), and `hyprctl setcursor` in `hyprland/execs.lua` parsed on the main
thread (~340 ms). A cold boot closes that gap. It only became reachable once `bibata-hyprcursor`
gave Bibata a real hyprcursor theme on 2026-10-28.

Fix: `~/.config/uwsm/env` now sets both cursor themes to `Bibata-Modern-Classic` (it still held
the rejected `macOS-hypr`/`macOS` from [[no-mac-style-desktop]]), and the startup `setcursor` line
is gone from `execs.lua`. Forced with a slowed plugin thread in nested Hyprland: old setup
crashed 6/6, fixed setup 0/6.

**Why:** `hyprland/execs.lua` is an ii file, so `./setup install` restores the line and the
crash with it. The `cachyos-setup` repo copies of both files were not updated, and no real login
had been tested when this was written.

**How to apply:** after any ii update, delete the startup `setcursor` line again
(see [[ii-dots-install]]). Don't run `hyprctl setcursor` in the first second after login.
Safe mode ignores `hyprctl reload`; use its Load config button, or run Lua through
`hyprctl dispatch "(function() ... end)()"`, where the "expected a dispatcher" error is harmless.
