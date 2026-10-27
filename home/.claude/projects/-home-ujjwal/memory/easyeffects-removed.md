---
name: easyeffects-removed
description: EasyEffects uninstalled 2026-09-14 — user runs native PipeWire/WirePlumber audio only, no effects layer
metadata:
  type: project
---

EasyEffects (mic gate/rnnoise/equalizer, speaker EQ) was degrading both playback and mic
quality. Removed entirely on 2026-09-14: package (`pacman -Rns`), `~/.config/easyeffects`,
`~/.local/share/easyeffects`, `~/.cache/easyeffects`, the `ee-jack-watch` service/script,
`ee-preset-cycle` script, the Hyprland autostart line, and the action-center/bar toggle
entries in `~/.config/illogical-impulse/config.json`.

The earlier [[bt-headset-mic-easyeffects]]-style WirePlumber autoswitch patch (in
`~/.local/share/wireplumber/scripts/`) is also deleted — it existed only to route around
EasyEffects sitting between apps and the Bluetooth mic. With EasyEffects gone, stock
WirePlumber's `autoswitch-bluetooth-profile.lua` switches to HFP correctly on its own.

**Why:** user's own call after comparing audio quality with/without EasyEffects.

**How to apply:** `~/dev/cachyos-setup` (the rebuild repo, see [[cachyos-setup-repo]]) has
matching edits already made to manifest.txt, install.sh, docs, package lists, and the
tracked copies of execs.lua/config.json — **not yet committed**, sitting alongside
unrelated pre-existing uncommitted work (idle-on-AC). Commit the EasyEffects-only subset
separately when asked, don't squash it in with the other pending changes.

Left alone deliberately (dormant, not worth the diff): ii-dots' own EasyEffects QML
widgets/service files under `~/.config/quickshell/ii/` and translations (upstream
dots-hyprland source, config.json no longer references the toggle so they just don't
render); a disabled waybar config's `on-click: easyeffects` (waybar isn't running).
