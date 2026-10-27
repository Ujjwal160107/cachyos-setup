---
name: bt-audio-crackling-fix
description: Bluetooth audio crackling/popping every few minutes, fixed 2026-09-21 — Intel AX201 USB autosuspend, not a config/codec issue
metadata:
  type: project
---

Bluetooth output (earbuds) cracked/popped periodically. Root cause confirmed via logs:
`spa.bluez5: Failure in Bluetooth audio transport …` in WirePlumber roughly every 5 min,
paired with kernel "corrupted SCO packet" bursts — the BT audio transport itself was
dying and re-establishing, unrelated to any app touching the mic (checked: no
autoswitch/profile-restore events around the failures).

WiFi is on 5GHz (channel 36) so this isn't 2.4GHz co-channel interference. Cause: the
Intel AX201's Bluetooth USB interface (`idVendor=8087 idProduct=0026`) had
`power/control=auto` with a 2s autosuspend delay — a known trigger for BT audio glitches
on this combo chip. Verified by disabling it and watching 3 clean minutes vs. 3 failures
in the prior 6.

Fix: `/etc/udev/rules.d/50-bt-no-autosuspend.rules` forces `power/control=on` for that
specific USB device on every add event. Persistent, survives reboot and re-plug. Mirrored
in [[cachyos-setup-repo]] at `system/etc/udev/rules.d/` (manual `sudo cp` + `udevadm
trigger`, same pattern as the existing greetd/logind.conf.d files there) — not yet
committed, same pending-commit state as [[easyeffects-removed]].

If crackling returns: check `power/control` for that USB device first (`cat
/sys/bus/usb/devices/*/power/control` for the AX201's Bluetooth interface) before
suspecting codec/config again.
