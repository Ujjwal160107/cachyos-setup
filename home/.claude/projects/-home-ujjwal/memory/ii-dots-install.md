---
name: ii-dots-install
description: end-4 illogical-impulse (Quickshell) dots installed 2026-09-06 on CachyOS Hyprland; backup location, UWSM caveat, archived waybar config
metadata:
  type: project
---

On 2026-09-06 end-4's illogical-impulse (ii, Quickshell-based) dots were installed from
`~/.cache/dots-hyprland` via `./setup install -f --skip-plasmaintg`. Previous configs
(hypr, fish, kitty, dolphinrc, kdeglobals) are in `~/ii-original-dots-backup`. The old
Lua Hyprland config still sits unused in `~/.config/hypr/config/`; noctalia config remains
in `~/.config/noctalia/` but is no longer autostarted.

**Why:** User asked for "illogical impulse dot files and waybar end4 dots". Current ii has
no waybar; end-4's only waybar config is the 2023 eww-era tray stub on the `archive`
branch, copied to `~/.config/waybar` but not autostarted (it would overlap ii's bar).

**How to apply:** Hyprland here runs under UWSM (greetd + noctalia-greeter, CachyOS
`start-hyprland`), which ii's installer warns against; `ILLOGICAL_IMPULSE_VIRTUAL_ENV` was
added to `~/.config/uwsm/env` as mitigation. To update ii: `cd ~/.cache/dots-hyprland &&
git pull && ./setup install`. Related: [[cachyos-hyprland-env]].
