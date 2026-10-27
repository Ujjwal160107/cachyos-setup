---
name: wifi-failover
description: Auto-switch from college wifi T-VIT to the vivo Y39 5G hotspot when T-VIT stops passing traffic
metadata:
  type: project
---

Set up 2026-09-08: `~/.local/bin/wifi-failover` plus a `wifi-failover.timer`
systemd *user* timer (60s). It leaves NM connection `T-VIT` for `vivo Y39 5G`
on the first failed captive-portal probe on wlan0.

**Why:** the college cuts T-VIT around 13:29 but the AP stays associated and
still answers DNS, so link state and pings to the gateway both look healthy —
only an exact-response probe (gstatic `generate_204`) detects it.

**How to apply:** it is deliberately one-way. Testing whether T-VIT is back
means associating to it, which would drop a working hotspot every cycle, so
switching back is manual: `nmcli connection up id T-VIT`.
See [[windows-migration-2026-09]] for the rest of this machine's setup.
