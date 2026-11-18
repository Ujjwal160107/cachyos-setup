---
name: windows-drive-cleanup
description: "2026-11-16 Windows C: cleanup from Linux — page file fixed at 4-8 GB via offline registry edit (hive backup in ~/win-registry-backup); what was deleted vs left for Windows uninstall"
metadata:
  node_type: memory
  type: project
  originSessionId: 6b7b43c3-2e29-4d89-9cc2-9eea6fd9c28d
  modified: 2026-11-16T09:08:36.915Z
---

On 2026-11-16 the user cleaned the Windows drive (`/mnt/win`, 287 of 375 GB used). The page file
was changed from system-managed to `C:\pagefile.sys 4096 8192` by editing the offline SYSTEM
hive with `hivexregedit --merge` (ControlSet001, `PagingFiles` REG_MULTI_SZ). The original hive is
at `~/win-registry-backup/SYSTEM-2026-11-16`; copying it back to
`/mnt/win/Windows/System32/config/SYSTEM` undoes the change.

**Why:** the auto-managed pagefile was 27.7 GB. My `rm -rf` calls are blocked by the user's
permission settings, so deletions were handed to the user as `!` commands (C:\Drivers, NVIDIA
Downloader, Temp, AppData\Roaming\Code, .tlauncher, pagefile.sys).

**Reverted the same day:** with the cap, Marvel's Spider-Man 2 closed within a minute on every
launch. The Windows System log showed Resource-Exhaustion-Detector 2004 (low virtual memory) at each
launch, and GameBar and PsPcSdkUI crashed alongside it. `PagingFiles` is back to `?:\pagefile.sys`
(system-managed). Don't cap the page file again: 16 GB RAM is not enough for that game without it.
Pre-revert hive: `~/win-registry-backup/SYSTEM-2026-11-16-before-revert`.

**How to apply:** Office, WSL, Windows Kits/SDKs, Visual Studio and MongoDB were left for the user
to uninstall inside Windows, because deleting them from Linux leaves services and the Office
Click-to-Run repair behind. Spider-Man 2 (108 GB) is the biggest remaining item. Related:
[[windows-games-on-linux]], [[nightreign-mod-merge]].
