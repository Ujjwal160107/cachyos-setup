# Fresh install: blank disk to working desktop

Follow this in order. Steps 1–3 have to happen before the scripts in this repo
can do anything useful.

## 1. Install CachyOS

Grab the ISO from [cachyos.org](https://cachyos.org/download/) and run the
graphical installer.

Choices that match this machine:

- **Desktop:** pick a minimal option. The real desktop is Hyprland via ii dots,
  installed in step 4, and a full KDE or GNOME install just adds packages you
  then have to work around. Some KDE pieces *are* wanted (Dolphin, Kvantum, the
  Qt platform theming) but `restore.sh` pulls those in by name.
- **Kernel:** `linux-cachyos` (the default). `linux-cachyos-lts` is installed
  alongside it here as a fallback — worth doing, it costs a few hundred MB and
  saves you when an NVIDIA update breaks the main kernel.
- **Bootloader:** GRUB with a separate EFI partition. See
  [05-hardware.md](05-hardware.md) for the exact partition layout, which
  matters if you are dual-booting Windows again.
- **Filesystem:** ext4 on root.

Reboot into the new system before continuing.

## 2. Base tools

```bash
sudo pacman -Syu
sudo pacman -S --needed base-devel git
```

CachyOS ships `paru` and `yay` already. If they are somehow missing:

```bash
git clone https://aur.archlinux.org/paru-bin.git /tmp/paru-bin
cd /tmp/paru-bin && makepkg -si
```

## 3. Clone this repo

```bash
git clone https://github.com/<you>/cachyos-setup.git ~/dev/cachyos-setup
cd ~/dev/cachyos-setup
```

HTTPS on purpose — you will not have SSH keys yet. Swap the remote to SSH once
you have set keys up, per [04-secrets-and-logins.md](04-secrets-and-logins.md).

## 4. Packages

```bash
./packages/restore.sh --dry-run   # look first
./packages/restore.sh
```

This installs 190 native packages, 35 AUR packages, and one flatpak. The AUR
half is the slow part — the `illogical-impulse-*` packages build from source and
`illogical-impulse-quickshell-git` alone can take a while. Leave it running.

`restore.sh` only asks for what is missing, so rerunning after a failure picks up
where it stopped rather than starting over.

### If an AUR build fails

Almost always a transient upstream break. Retry the single package:

```bash
paru -S --needed <package>
```

If it still fails, skip it and note it — everything except the
`illogical-impulse-*` group is optional for getting to a working desktop.

## 5. The ii desktop

The AUR packages install the ii *dependencies*. The dots themselves come from
upstream. Full detail in [02-desktop.md](02-desktop.md); the short form:

```bash
git clone https://github.com/end-4/dots-hyprland.git ~/.local/share/dots-hyprland
cd ~/.local/share/dots-hyprland
git checkout 97c5bc651f68092351b24aaa935af708b1e04514   # the pinned version
./setup
```

**Pinned deliberately.** ii moves fast and its installer overwrites config in
place. Install the known-good commit first, confirm the desktop comes up, and
only then decide whether to move to a newer one.

## 6. Link the config

```bash
cd ~/dev/cachyos-setup
./install.sh --dry-run
./install.sh
```

Run this **after** the ii installer, not before. `./setup` writes into
`~/.config/hypr`, `~/.config/quickshell` and friends; running it afterwards would
clobber the symlinks you just made.

Anything `install.sh` displaced is in `~/config-backup-<timestamp>/`.

## 7. Reapply the local ii patches

Two QML files differ from upstream. `install.sh` already put the patched copies
in place, so this step is only needed after a *future* ii update overwrites them.
See [02-desktop.md](02-desktop.md#the-two-local-patches).

## 8. Display manager

greetd with the noctalia greeter:

```bash
sudo cp system/etc/greetd/config.toml /etc/greetd/config.toml
sudo systemctl enable greetd.service
```

## 9. Services

```bash
sudo systemctl enable --now bluetooth ufw tailscaled docker
systemctl --user enable --now ee-jack-watch.service
```

`ee-jack-watch` is a local unit that switches the EasyEffects preset when
headphones are plugged in — see [03-apps.md](03-apps.md#audio).

The full enabled list on this machine: `ananicy-cpp`, `avahi-daemon`,
`bluetooth`, `docker`, `greetd`, `intel_lpmd`, `NetworkManager`,
`nvidia-powerd`, `switcheroo-control`, `systemd-resolved`, `systemd-timesyncd`,
`tailscaled`, `ufw`, plus the `cachyos-rate-mirrors` and `fstrim` timers.

## 10. NVIDIA

See [05-hardware.md](05-hardware.md#nvidia). Hybrid Intel + RTX 3050 laptop
graphics, which needs some care under Wayland.

## 11. Log back in to everything

[04-secrets-and-logins.md](04-secrets-and-logins.md) is the checklist. Nothing in
this repo can do it for you — that is the point.

## 12. Wallpapers

[03-apps.md](03-apps.md#wallpapers). The static images are in the repo; the
Wallpaper Engine scenes are 3 GB of Steam Workshop content and get re-subscribed
from a manifest of item IDs.

---

## Rough timings

| Step | Time |
|---|---|
| CachyOS install | 20–30 min |
| `restore.sh` native | 10 min |
| `restore.sh` AUR | 45–90 min (source builds) |
| ii `./setup` | 10 min |
| `install.sh` | seconds |
| Logging back in | 30 min of clicking |
