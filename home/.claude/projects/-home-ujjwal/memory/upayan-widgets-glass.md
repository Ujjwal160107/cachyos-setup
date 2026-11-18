---
name: upayan-widgets-glass
description: 2026-11-19 port of upayanmazumder/dotfiles 6a236bd..1ce4fb7 (desktop widgets, Spotify lyrics, Nothing Liquid glass) into ii; Wallpaper Engine moved under ii's layer so widgets show
metadata:
  type: project
---

On 2026-11-19 the user asked to apply the last three commits of github.com/upayanmazumder/dotfiles
(6a236bd, 9334b63, 1ce4fb7): desktop widgets (media with lyrics from lrclib/betterlyrics, calendar,
world clock, resources, visualizer off), liquid-glass shader for widget cards, `hypr/custom/liquidglass.lua`.
Their QML lives as `patches/quickshell-ii-local.patch` against ii cb1c428 (same QML as 21733c3); the
3-commit delta was cherry-picked onto the live tree in a scratch git repo. One conflict (Background.qml)
resolved to their WidgetsLoader. Added their AudioVisualizerWidget + its Config.qml key from an earlier
commit because WidgetsLoader needs it. Skipped their kitty.conf, kdeglobals, darklyrc and rules.lua.
Their widget positions were merged into config.json and overlap the user's weather/clock.

Wallpaper Engine change: widgets render inside ii's `quickshell:background` window, which the old patch
had put under the renderer, so they were invisible (the ii clock always was). Now
`wallpaper-engine.sh` defaults `LAYER=background` and Background.qml is back on `WlrLayer.Bottom`, with a
`wallpaperEngineActive` check (`hyprctl layers -j` on start and on openlayer/closelayer of
`linux-wallpaperengine`) that hides the static image while the renderer runs and not when locked.
Supersedes the layer notes in [[wallpaper-engine-setup]].

**Why:** the user wanted the widgets visible over the animated wallpaper.

**How to apply:** all Quickshell edits are now one file,
`~/dev/cachyos-setup/patches/ii-dots/quickshell-ii-local.patch` (round-trip verified against ii 21733c3);
the old Background/IllogicalImpulseFamily patches were removed (staged, not committed). Backup before the
port: `~/ii-backup-before-upayan-2026-11-19.tar.zst`. hyprglass is built and loaded (2026-11-19): shlok-shinde/hyprglass at 8d1c06d, the fork's last
Hyprland-0.56 commit (93dbe19 needs 0.57), `make` in a scratch clone, copied to
`~/.local/lib/nothing-liquid/hyprglass.so`. Glass is on for every window (`default_preset = "tahoe_window"`)
and the quickshell layers. The 0.57-only options (press_glow, press_spill, highlight_direction, dark_edge,
near_reflection) were removed from `liquidglass.lua` and from `services/LiquidGlass.qml`'s apply(); put
them back when moving to 0.57. Rebuild the .so after every Hyprland update (`hyprctl -j hyprglass status`
shows versionCheck); a mismatched build pauses rather than crashes. Tested first in a nested
`Hyprland -c test.lua` (find its instance by excluding $HYPRLAND_INSTANCE_SIGNATURE, `ls -t` picks the wrong one). Restarting the
launcher: kill both `wallpaper-engine.sh` and the renderer by PID (pgrep -f also matches your own shell),
then start it with `hyprctl dispatch 'hl.dsp.exec_cmd("...")'`. Lock-screen image not yet tested.
Related: [[ii-dots-install]].

Chrome and Discord got their own rule at the end of `hypr/custom/rules.lua` (2026-11-19): opacity
`0.85 override 0.78 override` and `no_blur = true`, after the class=".*" no_blur=false wildcard, because
Hyprland's cached blur hides hyprglass on static windows. Verified with `hyprctl getprop address:<a> opacity|no_blur`.

White line under the bar (2026-11-19) was hyprglass's rim (bevel) on the `quickshell:bar` layer: the bar
touches the screen top, so only its bottom rim shows. Fixed in liquidglass.lua with
`hg.preset("tahoe_clear_norim", { inherits = "tahoe_clear", bevel_strength = 0 })` for bar, verticalBar and dock (dock rim read as a blurred white outline).
`hg.layer(ns, { exclude = true })` via `hyprctl eval` did NOT take effect live; turning the plugin off with
`hg.config({ enabled = false, layers = { enabled = false } })` is the reliable A/B test.

