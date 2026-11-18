---
name: ii-game-mode-kills-blur
description: "ii's Game mode quick toggle silently disables blur/rounding/shadows/animations via a file sourced after custom config"
metadata:
  node_type: memory
  type: project
  originSessionId: 276fbfdd-76fe-4fdc-971e-b190524dedd1
  modified: 2026-11-01T16:30:39.670Z
---

ii's **Game mode** quick toggle (a size-1 tile in the right sidebar grid, between
`cloudflareWarp` and `powerProfile`) writes `~/.config/hypr/hyprland/shellOverrides/main.lua`
with `decoration:blur:enabled=0`, `decoration:rounding=0`, `decoration:shadow:enabled=0`,
`animations:enabled=0`, `general:gaps_in/out=0`, `border_size=1`, `allow_tearing=1`.
`hyprland.lua` requires that file **last**, after `custom/*.lua`, so it beats anything in
`custom/rules.lua`. It persists across reboots until the toggle is flipped back.

Symptom when it gets mis-tapped: window translucency looks like it "went opaque" —
`active_opacity`/`inactive_opacity` are untouched, but with blur off there is no frosting,
so glass reads as flat. Diagnosed 2026-11-01.

Clear it with ii's own script so the toggle's state stays in sync:
`~/.config/quickshell/ii/scripts/hyprland/hyprconfigurator.py --file <that file> --reset <each key>`

Also note `~/.config/hypr/config/` (decorations.lua, windowrules.lua) is **dead** CachyOS
leftover from before ii was installed — `hyprland.lua` never requires it, so editing it does
nothing. The live decoration values are in `hyprland/general.lua`.

Related: [[ii-dots-install]], [[no-mac-style-desktop]]
