---
name: fortuna-vps-tailscale
description: "Fortuna VPS (162.216.16.9) reached over Tailscale SSH as `ssh root@fortuna`; CachyOS box joined tailnet 2026-11-05"
metadata:
  node_type: memory
  type: reference
  originSessionId: c39aebcb-2891-496f-b1f6-2bff00592fbb
  modified: 2026-11-05T09:35:49.340Z
---

Fortuna is the user's VPS, public IP 162.216.16.9, tailnet IP 100.85.196.72 (tailnet tailab5130.ts.net, account ujjwalt616@).

- CachyOS laptop joined the tailnet 2026-11-05 as `asgrd-1`; Windows side is `asgrd`. User is Tailscale operator (no sudo needed).
- `~/.ssh/config` mirrors the Windows config: `fortuna` (User deploy, Tailscale SSH, no key) and `fortuna-direct` (public IP, `~/.ssh/fortuna_deploy`).
- `ssh root@fortuna` and `ssh fortuna` (as deploy) both verified working.
- `tailscale status` warns systemd-resolved/NetworkManager are mis-wired for MagicDNS, but `fortuna` resolves fine. Ignore unless name resolution breaks.

Related: [[windows-migration-2026-09]]
