---
name: internal-mic-gain-fix
description: Internal laptop mic was clipping (53% of samples at full scale, silent noise floor -1.6dBFS) from Internal Mic Boost + Capture both maxed at +30dB each
metadata:
  type: project
---

ALC257 internal mic ("HDA Intel PCH", alsa_input.pci-0000_00_1f.3.analog-stereo) had
Internal Mic Boost and Capture both at their max (+30dB each, 60dB total) — verified by
recording 4s of silence and measuring: -1.6dBFS RMS floor, 53% of samples clipped at
full scale. That's why voice sounded like noise: the self-noise/clipping was louder than
speech.

**Gotcha that cost a repeat of the same fix:** `amixer -c PCH sset 'Internal Mic Boost' 0`
+ `Capture 70%` looks like it works immediately, but reverts on next reboot/reconnect/
WirePlumber restart. Cause: PipeWire's alsa-card-profile mixer path
(`/usr/share/alsa-card-profile/mixer/paths/analog-input-internal-mic.conf`) declares
`Internal Mic Boost` and `Capture` as one **merged** volume control — WirePlumber owns
and re-asserts its own stored composite value (e.g. 100%) on every route activation,
silently overwriting any direct amixer edit underneath it.

**Correct, durable fix:** set the composite volume itself —
`pactl set-source-volume alsa_input.pci-0000_00_1f.3.analog-stereo 18%` — which the merge
curve maps to Internal Mic Boost off + Capture ~68% (~15dB total, matches what raw-amixer
tuning found was clean). This persists in
`~/.local/state/wireplumber/default-routes` as `channelVolumes` (stored as cubic
amplitude: 0.18³≈0.00583, confirmed matching) and gets correctly reapplied every time,
unlike a raw amixer edit. Also ran `alsactl store` as a belt-and-suspenders fallback for
the pre-WirePlumber cold-boot raw register state.

If it goes noisy again: check `amixer -c PCH sget 'Capture'` / `'Internal Mic Boost'`
first — if both are back near max, redo the `pactl set-source-volume …%` step (scan
5/10/15/18/20% if the mapping ever shifts) rather than touching amixer directly.

Separately: [[easyeffects-removed]] covers why input runs raw/unprocessed now.
Bluetooth earbuds mic being pinned per-site in Zen (can't even `pactl move-source-output`
it — request fails with "Invalid argument", the stream is locked to that device) is a
distinct, already-diagnosed issue — fix in the site's own mic permission, not here.
