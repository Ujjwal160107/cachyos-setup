---
name: windows-games-on-linux
description: "Running Windows-partition games/apps in place on CachyOS (2026-10-24) — Steam+Proton on the NTFS library, Lutris for portable games; what was changed and what is pending"
metadata:
  node_type: memory
  type: project
  originSessionId: 6b7b43c3-2e29-4d89-9cc2-9eea6fd9c28d
  modified: 2026-10-24T09:27:02.524Z
---

On 2026-10-24 the user asked to run Windows-installed games and apps from Linux without
booting Windows. Chosen approach: **Steam + Proton** for the Windows Steam library and
**Lutris** for portable/third-party games, run in place from `/mnt/win`. A VM was rejected:
only the RTX 3050 is visible (no iGPU exposed), IOMMU is off, and RAM is 16 GB.

Done: fstab switched to rw `ntfs-3g` with `windows_names` (backup `/etc/fstab.bak-2026-10-24`);
`/mnt/win/Program Files (x86)/steam/steamapps/compatdata` symlinked to the Linux library's
compatdata; Windows library added as entry "1" in `~/.local/share/Steam/steamapps/libraryfolders.vdf`
(backup `.bak-2026-10-24`). Installed ntfs-3g, umu-launcher, wine, winetricks.
`docs/05-hardware.md` in cachyos-setup updated, not committed.

**Why:** The user explicitly approved writing to the Windows partition, overriding the
earlier read-only rule from [[windows-migration-2026-09]].

Full `pacman -Syu` run the same day (kernel 7.3.0-4, NVIDIA 615.78.08), then lutris 0.5.22 +
vulkan-tools installed. Funnel Runners, How to Fish and Content Warning were registered in Lutris
via its own Python API (`write_game_config` + `games_db.add_game`), wine runner, version
`ge-proton`, shared prefix `~/Games/windows`.

**How to apply:** Windows Fast Startup must stay off (user told to run `powercfg /h off`). Portable games live in
`/mnt/win/Users/ujjwa/Downloads` (Funnel Runners, How to Fish, Content Warning). Several are
online-fix (OFME) cracks: launching them is fine, but don't troubleshoot the crack layer.
Wallpaper Engine (431960) has an appmanifest in both Steam libraries.

User's real workflow: games come as extracted folders (online-fix), some run through a mod
manager (me3 for Nightreign), rarely Steam; Steam games via LuaTools. They want Windows-style
"double-click the .exe and it runs". Built for that: `~/.local/bin/run-exe` (cd to exe dir, umu-run
with GE-Proton, shared prefix `~/Games/windows`, log `~/.local/state/run-exe.log`) and
`~/.local/share/applications/run-exe.desktop` ("Run with Proton"), set as default for
.exe MIME types. GE-Proton11-11 in `~/.local/share/Steam/compatibilitytools.d`. Neither file is
in the cachyos-setup manifest yet. Don't help set up LuaTools or debug crack layers.

Gotcha: campus Wi-Fi (T-VIT) shares one public IP, so GitHub's unauthenticated API limit
(60/h) is often exhausted. umu and Lutris fetch Proton/DXVK through it and fail with 403.
Check `curl -s https://api.github.com/rate_limit` before retrying; a hotspot also works.

