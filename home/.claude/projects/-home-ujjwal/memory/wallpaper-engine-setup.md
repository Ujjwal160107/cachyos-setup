---
name: wallpaper-engine-setup
description: How linux-wallpaperengine is started at login and shown statically on ii's lock screen; includes two ii QML patches that an ii update will wipe
metadata:
  type: project
---

Since 2026-09-06 the animated wallpaper is started by
`~/.config/hypr/custom/scripts/wallpaper-engine.sh` from ii's `custom/execs.lua`, not by the
Linux Wallpaper Engine GUI (Electron, `linux-wallpaper-engine-ux`). The GUI's autostart was
turned off (`launchOnLogin: false` in `~/.config/Linux Wallpaper Engine/settings.json`, its
`~/.config/autostart` entry removed); it remains the tool for picking wallpapers, and the
script re-syncs from its `active-wallpapers.json`. State and logs live in
`~/.local/state/wallpaper-engine/` (lockscreen.png, current, sync.log, renderer.log).

**Why:** The GUI's XDG-autostart brought the wallpaper up ~2.5 minutes after login. The user
wants it instantly, and a static frame of it on the lock screen.

**How to apply:** Two patches live inside ii's config dir and are lost on `./setup install`
(it rsyncs `~/.config/quickshell` with --delete); reapply them after an ii update:
1. `modules/ii/background/Background.qml`: unlocked layer `WlrLayer.Background` instead of
   `WlrLayer.Bottom`, so ii's static wallpaper sits under the renderer's bottom layer.
2. `panelFamilies/IllogicalImpulseFamily.qml`: `PanelLoader { component: Background {} }`
   re-enabled (an earlier session had commented it out).
ii's `background.wallpaperPath` is set to the lock frame by the script via switchwall.sh,
which also re-derives the Material colours. `lock.blur.enable` was set false so the frame
shows unblurred. The older `wallpaper-engine-sync.sh` (Proton Wallpaper Engine config
watcher) is unused and can be removed. Related: [[ii-dots-install]].
