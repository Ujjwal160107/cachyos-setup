---
name: ii-dots-install
description: "end-4 illogical-impulse (Quickshell) dots installed 2026-09-06 on CachyOS Hyprland; backup location, UWSM caveat, archived waybar config"
metadata: 
  node_type: memory
  type: project
  originSessionId: cc1e8b2e-233b-4ce0-8cc0-2a624d73e526
  modified: 2026-09-08T05:47:18.124Z
---

On 2026-09-06 end-4's illogical-impulse (ii, Quickshell-based) dots were installed from
`~/.local/share/dots-hyprland` (was `~/.cache/dots-hyprland`) via `./setup install -f --skip-plasmaintg`. Previous configs
(hypr, fish, kitty, dolphinrc, kdeglobals) are in `~/ii-original-dots-backup`. The old
Lua Hyprland config still sits unused in `~/.config/hypr/config/`; noctalia config remains
in `~/.config/noctalia/` but is no longer autostarted.

**Why:** User asked for "illogical impulse dot files and waybar end4 dots". Current ii has
no waybar; end-4's only waybar config is the 2023 eww-era tray stub on the `archive`
branch, copied to `~/.config/waybar` but not autostarted (it would overlap ii's bar).

**How to apply:** Hyprland here runs under UWSM (greetd + noctalia-greeter, CachyOS
`start-hyprland`), which ii's installer warns against; `ILLOGICAL_IMPULSE_VIRTUAL_ENV` was
added to `~/.config/uwsm/env` as mitigation. To update ii: `cd ~/.local/share/dots-hyprland &&
git pull && ./setup install`, then reapply the three patches in `~/dev/cachyos-setup/patches/ii-dots/`
(two QML for wallpaper engine, `hypridle.conf` for no lock/blank/suspend on AC via
`~/.local/bin/unless-ac`, added 2026-09-07, widened to all three timeouts 2026-09-08 —
see [[idle-on-ac]]). Also live-edited but NOT yet in that patches dir (2026-09-08, see
[[dock-magnify-headroom]]): `modules/ii/dock/Dock.qml` and `DockAppButton.qml`.
Quickshell does not hot-reload QML — restart it with `Ctrl+Super+R` (or
`qs -c ii`) after editing, and never `pkill -f "qs -c ii"` from a shell whose own command
line contains that string, or pkill kills the caller too. This Hyprland build takes Lua in `hyprctl dispatch`: use
`hyprctl dispatch 'hl.dsp.exec_cmd("cmd")'`, not `hyprctl dispatch exec cmd`. Related: [[cachyos-hyprland-env]].

**Updated 2026-11-18** from 97c5bc6 to 21733c3 without `./setup install`: upstream only changed
`hypr/hyprland/{general,keybinds,rules}.lua`, `overview/Overview.qml` and `services/SystemInfo.qml`,
none of them locally patched, so those five were copied into `~/.config` (old copies in
`~/ii-update-backup-2026-11-18`). That keeps the QML patches and the removed `setcursor` line from
[[hyprcursor-startup-race]] intact. Upstream also bumped the Quickshell pin to 4f508be (0.3.2,
includes the Qt 6.12 fix); NOT rebuilt, because 0.3.2 broke the bar's Hug corners here (see
[[ryoku-desktop]]). The installed custom build (7511545 + cherry-picked 5d5d498) still runs.
Before the next update, diff `git diff HEAD @{u} --stat` first; only use `./setup install` when
upstream touches many files, then reapply every patch above.

