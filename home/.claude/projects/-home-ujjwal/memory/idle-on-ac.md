---
name: idle-on-ac
description: "On the charger hypridle never locks, blanks, or suspends; lid rule removed 2026-10-27 because the lid would not wake"
metadata: 
  node_type: memory
  type: project
  originSessionId: bc46ef41-5a0d-4fe6-8c0d-dd7b1a443813
  modified: 2026-10-27T07:31:34.987Z
---

Chosen 2026-09-08. `~/.local/bin/unless-ac CMD` runs CMD only on battery; all
three hypridle listeners (lock 5m, DPMS off 10m, suspend 15m) are routed through
it. A logind drop-in once ignored lid close on AC; the user deleted it on
2026-10-27 because after closing the lid the PC would not wake and needed a
reboot. Lid close suspends again, on mains too. Do not re-add it.

**Why:** the user asked for all of it, lock included, after being told the
tradeoffs — a plugged-in laptop left in a college lab never locks, and a closed
lid in a bag stays running and hot.

**How to apply:** don't "fix" the missing lock as a security oversight; it was a
deliberate call. Battery behaviour is untouched. Keep the `$unless_ac` line in
`hypridle.conf` free of a trailing `#` comment — hyprlang carries it into the
value and mid-line it comments out the rest of the action. All of it is tracked
in `~/dev/cachyos-setup` (manifest `shell:.local/bin/unless-ac`, `system/etc/`,
`patches/ii-dots/hypridle.conf.patch`) — see [[ii-dots-install]] and
[[cachyos-setup-repo]].
