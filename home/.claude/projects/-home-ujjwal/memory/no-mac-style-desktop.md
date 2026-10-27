---
name: no-mac-style-desktop
description: "User does not want macOS-style cursor, dock, or similar cosmetic ports on this CachyOS/Hyprland setup"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5e30a4b1-6b02-4fdf-a184-f9b7874eebff
  modified: 2026-09-09T05:37:56.677Z
---

Don't apply macOS-style cosmetic changes (cursor theme, dock, shake-to-find cursor, etc.)
to this machine's ii/Hyprland desktop, even if asked for something similar in the moment —
confirm scope first.

**Why:** On 2026-09-07 a separate Claude session installed `apple_cursor`/`apple_hyprcursor`,
set `hyprctl setcursor macOS-hypr 24` at startup, enabled the `dynamic-cursors` hyprpm plugin
(macOS shake-to-find), and flipped ii's dock module on (`illogical-impulse/config.json`
`dock.enable`/`pinnedOnStartup` false→true, both off by default in ii). The user called this
"ruined" and had it fully reverted the same night: cursor back to `Bibata-Modern-Classic 24`,
plugin disabled, dock config restored to `false`/`false`, the AUR packages removed, and
`custom/execs.lua` restored to just the wallpaper-engine startup call (see
[[wallpaper-engine-setup]]).

**How to apply:** If the user asks for a Mac-like look again, treat it as a real request to
implement, not evidence the last attempt is welcome — but be aware this exact combination
was tried once and rejected within about an hour. Related: [[ii-dots-install]].

**Update 2026-09-08:** the user asked again, deliberately, after being reminded of the above.
What they kept: WhiteSur icons, an ii dock (see [[dock-magnify-headroom]]), and the
dynamic-cursors shake-to-locate *effect*. What they rejected a second time: the macOS cursor
*skin* — "rather than the mac cursor skin can i just have the mac cursor effect" — so
`apple_cursor`/`apple_hyprcursor` were installed and then removed again, and the cursor is
back to ii's default `Bibata-Modern-Classic`. The pattern across both attempts: they want
macOS *behaviour*, not macOS *appearance* in the pointer.

Shake-to-locate now lives in `~/.config/hypr/custom/general.lua` (not ii's files, so updates
can't wipe it): `mode = "none"` (no cursor tilt/rotate — that default is what made the cursor
"change shape and style"), `shake.limit = 5` (the default 0 means grow forever), and
`cursor:no_hardware_cursors = true`, without which a magnified cursor overflows the GPU's
fixed cursor plane and reverts to a default image mid-shake.

**Update 2026-10-13 (third rejection):** user asked for macOS minimize (`SUPER+M`, restore on
`CTRL+SUPER+M`), approved a design, then asked for a real genie animation into the dock icon.
It was built (Hyprland special-workspace park + Quickshell shader overlay + dock patches) and
verified frame by frame. A few turns later, asked for it on "all apps", the user said "remove the
entire config revert back". Fully reverted: `custom/keybinds.lua` and `custom/rules.lua` restored,
`minimize.sh`, `GenieOverlay.qml`, shaders and the setup-repo patches deleted, dock QML back to its
pre-genie state, `SUPER+M` is ii's media controls again.

**How to apply:** don't rebuild minimize/genie unprompted. If it comes up again, say it was
built and removed on 2026-10-13, and ask what was wrong before building anything. Likely
unknowns: whether the cost (a patched ii dock that an update wipes, a screenshot-based overlay)
was the issue, or the result itself. Hyprland has no native minimize and no genie plugin exists.
