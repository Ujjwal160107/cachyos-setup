---
name: chrome-logout-keyring
description: "Chrome logging out every profile on each Linux boot — keyring not unlocked by greetd + duplicate \"Chrome Safe Storage\" keys; PAM fix 2026-11-07"
metadata:
  node_type: memory
  type: project
  originSessionId: c39aebcb-2891-496f-b1f6-2bff00592fbb
  modified: 2026-11-07T16:55:23.039Z
---

Symptom: every Chrome profile says "verify it's you" after each Linux boot.

Cause (verified 2026-11-07 by test-decrypting each profile's Cookies DB):
- `/etc/pam.d/greetd` had no `pam_gnome_keyring`, so keyrings stayed locked at login. Chrome then got whichever key answered, or fell back to v10 ("peanuts").
- Two "Chrome Safe Storage" items existed: Default_keyring/2 (2026-09-05, original) and login/6 (2026-10-27, created during the Ryoku trial, which also switched the keyring `default` alias to `login`). See [[ryoku-desktop]].
- Cookies were split three ways: Profiles 3,4 = Default_keyring key; 5,6,7,9 = login key; Default, Profile 2 = v10.

Fix applied: added `-auth optional pam_gnome_keyring.so` and `-session optional pam_gnome_keyring.so auto_start` to `/etc/pam.d/greetd`. Backups of the keyrings and the original PAM file are in `~/keyring-backup-2026-11-07/`.
User deleted duplicate Default_keyring/2 on 2026-11-07; only login/6 remains. Verified after reboot 2026-11-08: gkr-pam unlocks login keyring at greetd login, no prompt, all new cookies are v11 with the login key. (A "couldn't unlock" gkr-pam line for the greeter user, uid 962, is harmless.)

**How to apply:** if logouts recur, re-run a cookie-key tally, and check that login keyring's password matches the login password (otherwise PAM can't unlock it). The check script was in session scratchpad and is gone now. Its logic: PBKDF2-SHA1(secret, "saltysalt", 1 iter, 16 bytes), AES-128-CBC with an IV of 16 spaces, then check the padding.
