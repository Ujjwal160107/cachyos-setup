---
name: windows-migration-2026-09
description: Windows-to-CachyOS dev migration done 2026-09-06; where things landed and the non-obvious facts (HTTPS remotes, SSH keys belong to Antra1705, Windows partition read-only at /mnt/win)
metadata:
  type: project
---

Migration from the Windows 11 dual-boot to CachyOS was completed on 2026-09-06 following LINUX-MIGRATION-PROMPT.md.
Repos live in ~/dev (cruitical + 4 worktrees, kb, Casino-, clueminati-2026, elevenlabs-coffee-chat, linkedin-post-skill, Land, MeghMitra).
The Windows partition (nvme0n1p3, Windows-SSD) is mounted read-only at /mnt/win via fstab; never remount it rw.

**Why:** Both SSH keys in ~/.ssh authenticate as GitHub user Antra1705, not Ujjwal160107, so private repos were cloned over HTTPS using the stored git credential (same as the Windows remotes). The Windows landing-page repo was gutted (objects only) and was not migrated.
**How to apply:** Use HTTPS remotes for Cruitical/* and Ujjwal160107/* repos. Pre-migration copies of overwritten files are under ~/migration-backup/20260905-2356. ~/laptop-backup-2026-09-02 holds plaintext secrets and should be deleted once verified.
