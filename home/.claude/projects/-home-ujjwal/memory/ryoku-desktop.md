---
name: ryoku-desktop
description: "Ryoku trial 2026-10-27, reverted to ii 2026-10-28; how Ryoku was tweaked, and how to go back to it (tarball + branch)"
metadata:
  node_type: memory
  type: project
  originSessionId: 1282d7d9-74c3-46f3-a3da-f3af4bce9249
  modified: 2026-10-27T20:26:13.643Z
---

**REVERTED 2026-10-28:** the user asked to go back to ii. Ran Ryoku's
`~/.local/state/ryoku/shell-install/backup-20261027-133508/restore.sh` (identical to
`~/ii-pre-ryoku-backup-20261027.tar.zst` for the dirs it restores): hypr, quickshell,
kitty, fish, fastfetch, matugen, qt6ct, systemd/user, portal, mimeapps restored; SDDM
disabled, greetd (noctalia greeter) enabled; Ryoku's sddm.conf.d files removed. Not
touched: gtk-3.0/gtk-4.0/kdeglobals (WhiteSur icons, approved), `~/.config/chrome-flags.conf`
(Chrome 0.9 scale), `~/.config/ryoku`, `~/.local/bin/ryoku-*`, Ryoku packages and the
`[ryoku]` pacman repo. The full Ryoku state is in `~/ryoku-pre-revert-backup-20261028.tar.zst`
(37 MB, has user.lua and shell.json) and on git branch `ryoku` (c0fbc0b, plus uncommitted
later edits that exist only in that tarball). Full removal 2026-10-28 (user said keep ii exactly as before, nothing from Ryoku): Ryoku's
installer had uninstalled all 14 `illogical-impulse-*` packages (incl. ii's quickshell-git
and Bibata), so ii ran on Ryoku's quickshell. Removed every ryoku/ryogami/ryomanager package,
Ryoku's quickshell, hypr-dynamic-cursors/hyprglass/hyprgrass/imgborders/gpk/skwd-paper-bin,
the `[ryoku]` repo (pacman.conf backup `/etc/pacman.conf.pre-ryoku-removal`) and the dangling
unit links; rebuilt the ii packages from `~/.local/share/dots-hyprland/sdata/dist-arch` via
makepkg. Plymouth back to `cachyos-bootanimation`. Chrome flags, gtk-3.0/4.0, kdeglobals,
btop restored from the `ii` branch. Ryoku-only files moved (not deleted) to
`~/ryoku-leftovers-20261028/`. ii's pinned quickshell (7511545) no longer builds against Qt 6.12: built it with upstream
5d5d498 cherry-picked (conflicts resolved, `bindableUsingLua` dropped), Clang, and
`PKGBUILD.clang` (adds -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON) in the sdata quickshell dir.
Packaged quickshell 0.3.2 fails to draw the bar's Hug corners at startup; ii's build does.
Red magnified cursor fixed in `hypr/custom/general.lua` (dynamic-cursors `hyprcursor.enabled=false`;
uwsm env still names the removed macOS-hypr theme). Generic packages Ryoku pulled in (sddm, weston, vimix-cursors,
fonts, xpadneo-dkms…) were left installed.

First reboot after the revert
re-laid Ryoku over ii: `ryoku-bootstrap.service` (global user unit) runs `ryoku materialize`
when `~/.config/quickshell/shell/shell.qml` is missing, which restore.sh causes. Fixed
2026-10-28 with `sudo systemctl --global disable ryoku-bootstrap ryoku-bt-agent` and a second
restore.sh run; to go back to Ryoku, `--global enable` them again. `ryoku-greeter-guard`
and `ryoku-boot-guard` (system units) are still enabled but inert without SDDM. The notes
below describe Ryoku, not the live desktop; [[ii-dots-install]], [[wallpaper-engine-setup]], [[dock-magnify-headroom]] apply again.

Ryoku (Hyprland + `qs -c shell`) was the desktop 2026-10-27 to 2026-10-28. `~/.config/quickshell/`
is a copy of `/usr/share/ryoku/config/quickshell/` that Ryoku overwrites;
`ryoku owner <path>` says the tree "cannot be forked" and the `user_edits` overlay
is not for it. Don't patch QML there the way the ii patches worked.

**Why:** an in-place or overlay QML edit is lost on `ryoku update`, and Ryoku
treats a fork as breaking the shell.

**How to apply:** put changes in files Ryoku never touches: `~/.config/hypr/user.lua`
(look, window/layer rules, binds, plugin load), `~/.config/kitty/user.conf`,
`~/.config/fish/user.fish`. Shell options live in `~/.config/ryoku/shell.json`.
Wallpaper Engine scenes apply through the `ryogami` JSON-RPC socket, not
`ryogami wallpaper set`. Idle policy is `ryoku-power idle set` (see [[idle-on-ac]]).

The bar is the **Orpheus** style (`shell.json` `.barStyle = "orpheus"`,
`.orpheus.workspaceStyle = "icons"`), switched 2026-10-27 because the default islands
bar (`qsbar`) cannot show app icons in its workspace strip. Revert with
`.barStyle = "qsbar"`. Orpheus looks icons up by window class, so an app whose class
is not an icon name shows a generic glyph; fix it with a symlink in
`~/.local/share/icons/hicolor/scalable/apps/<class>.svg` (done for
`com.microsoft.VSCode`). Orpheus scrolls workspaces natively; a Hyprland scroll bind
for the old islands strip was removed because it double-stepped.

**Super tap = overview + search (ii behaviour):** user.lua binds `SUPER + SUPER_L/R`
on release to `~/.local/bin/ryoku-super-tap`, which opens `ryoku:overview` (draggable
workspace grid) then `ryoku:launcher` (search) and closes both on the next tap. Both
are independent toggles in the shell, so the script reads open layers from `hyprctl
layers`. Super+Space = launcher alone, Super+Tab = overview alone. Super+Alt+Left/Right
move the window to the previous/next workspace, but Super+Alt+Left never reaches Hyprland
from the user's keyboard (log showed only Right; cause unknown, likely keyboard). The
window-to-workspace binds in user.lua are ii's set ported one for one (read from
ii's keybinds.lua): Super+Alt+PageUp/Down, Ctrl+Super+Shift+Left/Right, Super+Shift or
Super+Alt + scroll, and Super+Alt+<number> as a silent move (ii's follow=false).

**Single icon per workspace:** `~/.local/bin/ryoku-single-icon-patch` patches the
shipped Orpheus `Workspaces.qml` (shell tree, so `ryoku update` and `ryoku
materialize` undo it): re-run it, then `systemctl --user restart ryoku-shell`. Picks
the smallest `focusOrder` (the daemon exposes no creation time). I tried a systemd
drop-in to re-run it at every shell start; the auto-mode classifier blocked it as
persistence, so do not add one without the user asking. WARNING: `ryoku materialize
--help` ignores the flag and actually runs the re-lay (harmless here, but avoid).

**Hub resets the look (fixed 2026-10-27):** opening Ryoku Hub runs
`ryoku-hub desktop get` then `desktop preview <saved draft>` (Hub.qml `hyprGet` ->
`onHyprDraftChanged`), live-applying every Hub appearance value over user.lua's blur,
gaps, rounding and opacity, with no restore on close and no configreloaded event.
Fix: the look is saved in the Hub too (`ryoku-hub desktop get | jq patch |
ryoku-hub desktop save`). Keep the two in sync when editing the look; `hyprctl
reload` recovers a reset. The border follows the palette whenever the Hub opens.
Gotcha: the Hub's save writes an alpha `shadowColor` as invalid `rgb(00000020)` and
Hyprland shows a config-error banner; keep the Hub's `shadowColor` at `#000000` and
let user.lua carry the alpha. Check `hyprctl configerrors` after any `desktop save`.

**Colours:** the shell palette is monochrome since 2026-10-27, set by
`~/.config/ryoku/matugen.json` `.schemeType = "scheme-monochrome"` (was
`scheme-tonal-spot`; regenerates `~/.cache/ryoku/colors.json` within seconds). The
`theme.matugen.scheme_type` key in shell.json does not drive it. Notification popups
keep an orange countdown outline: `flameGlow #ff9e64` is hard-coded in the shell
tree and has no setting. The Hyprland active border in user.lua is neutral white.

**Notifications:** popup width is hard-coded 400 px times the per-monitor shell UI
scale (`shell.json` `displays.ui_scale.eDP-1`, Hub > Displays, 50-200%); set to 0.75
on 2026-10-27 to get ii-like small popups. It scales other shell chrome too. The
card layout (header, title, body, orange countdown outline) cannot be slimmed
further: no setting, and the only other designs are the RyoStore's Tegami and
Yatagarasu. The oh-my-posh prompt ("oh my pi" in the user's words; theme
`~/.config/oh-my-posh/marcduiker.omp.json`) is live in fish via `user.fish`.

**Repo:** `~/dev/cachyos-setup` has branch `ryoku` (current Ryoku dotfiles, pushed
2026-10-27) and branch `ii` (= `main`, tag `ii-final`; the whole ii setup). The user
said ii must stay: never delete `~/.config/illogical-impulse`,
`~/.local/share/dots-hyprland` or the ii backups, and keep ii on its own branch.

Supersedes the ii notes in [[ii-dots-install]], [[wallpaper-engine-setup]] and
[[dock-magnify-headroom]].
