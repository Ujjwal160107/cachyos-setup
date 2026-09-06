# This machine

Everything here is specific to one laptop. On different hardware, treat it as
the thing to change rather than the thing to copy — `monitors.lua` and the NVIDIA
notes in particular.

## Specs

| | |
|---|---|
| CPU | 13th Gen Intel Core i7-13650HX |
| GPU | NVIDIA RTX 3050 6GB Laptop (GA107BM) — the only GPU the OS sees, see [NVIDIA](#nvidia) |
| RAM | 15 GiB |
| Display | eDP-1, 1920x1080 @ 60 Hz, internal |
| Disk | 476.9 GB NVMe (`nvme0n1`) |
| Swap | zram, 15.4 GB — no swap partition |

## Disk layout

Dual-boot with Windows. **The Windows partitions matter**: repartitioning
carelessly during a reinstall is how you lose the Windows side.

| Partition | Size | FS | Mount | What |
|---|---|---|---|---|
| `nvme0n1p1` | 260M | vfat | — | Windows EFI |
| `nvme0n1p2` | 16M | — | — | Microsoft reserved |
| `nvme0n1p3` | 374.7G | ntfs | `/mnt/win` | Windows C: |
| `nvme0n1p4` | 2G | ntfs | — | Windows recovery |
| `nvme0n1p5` | 99.5G | ext4 | `/` | Linux root |
| `nvme0n1p6` | 515M | vfat | `/boot/efi` | Linux EFI |

There is no separate `/home` — it lives on root. Back up `~` before any
reinstall, because reformatting root takes your home with it.

`/mnt/win` is mounted **read-only** on purpose. Windows fast-startup leaves the
NTFS filesystem in a dirty state, and writing to it from Linux can corrupt it.
Leave it read-only unless you have fully shut Windows down (not hibernated) and
know what you are doing.

## Bootloader

GRUB, with the Linux ESP at `/boot/efi`.

Kernels installed: `linux-cachyos` (primary) and `linux-cachyos-lts` (fallback).
Keeping the LTS kernel is worth the disk space — when an NVIDIA driver update
breaks the main kernel, the LTS entry in the GRUB menu is how you get back in.

`os-prober` must be enabled for GRUB to find Windows. It already is on this
machine (`GRUB_DISABLE_OS_PROBER='false'` in `/etc/default/grub`), but a fresh
install defaults it off. If the Windows entry is missing after a rebuild:

```bash
sudo sed -i "s/^#\?GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/" /etc/default/grub
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

Current kernel command line, for reference:

```
rw nowatchdog nvme_load=YES splash loglevel=3
```

## NVIDIA

**The NVIDIA GPU is the only GPU the OS can see.** Despite the i7-13650HX having
integrated graphics, `lspci` reports one display controller and `/dev/dri` has
one card, both the RTX 3050. The iGPU is switched off — either disabled in BIOS
or the laptop MUX is pinned to discrete.

That is worth knowing for two reasons. Hyprland is compositing on NVIDIA, not on
an iGPU, so NVIDIA Wayland problems hit the whole session rather than one app.
And there is no power saving from offloading to an iGPU, because there is nothing
to offload to.

If you want the iGPU back, that is a BIOS change (look for a hybrid/MSHYBRID or
"Switchable Graphics" option), not a Linux one.

### Driver

Driver 610.57.04, via the **open** kernel modules built for the CachyOS kernels:

| Package | For |
|---|---|
| `linux-cachyos-nvidia-open` | Primary kernel |
| `linux-cachyos-lts-nvidia-open` | LTS fallback kernel |
| `nvidia-utils`, `nvidia-settings`, `nvidia-prime` | Userspace |
| `lib32-nvidia-utils`, `lib32-opencl-nvidia` | 32-bit, for Steam |
| `libva-nvidia-driver` | VA-API hardware video decode |

Install the module package matching **each** kernel you keep. Install
`linux-cachyos-lts-nvidia-open` alongside the LTS kernel or the fallback boot
entry comes up with no working display — which defeats the point of having it.

`nvidia_drm` modesetting is enabled by the packages themselves. There is **no**
`/etc/modprobe.d/nvidia.conf` on this machine and none is needed; the only file
in `modprobe.d` is `audio-nopowersave.conf`. Do not add one from a generic Arch
guide without checking whether it is doing anything.

Enabled services: `nvidia-powerd` (dynamic boost) and `switcheroo-control`.

### Verifying after a rebuild

```bash
nvidia-smi                    # driver version and GPU
lsmod | grep nvidia           # expect nvidia, nvidia_drm, nvidia_modeset, nvidia_uvm
switcherooctl list            # what the system thinks it can switch between
```

`prime-run <app>` exists but does nothing useful here — with a single GPU there
is nothing to offload from.

### If the session comes up black

Check `~/.cache/hyprland.log` first — `auto-Hypr.sh` writes it.

The most common cause is a kernel update landing without its matching
`*-nvidia-open` package, leaving no NVIDIA module for the running kernel. Boot
the LTS entry from GRUB and reinstall:

```bash
sudo pacman -S linux-cachyos linux-cachyos-nvidia-open
```

Note that ii's `~/.config/hypr/config/environment.lua` ships NVIDIA environment
variables (`GBM_BACKEND`, `__GLX_VENDOR_LIBRARY_NAME`, `LIBVA_DRIVER_NAME`)
**commented out**, and the session works fine that way. Modern Hyprland does not
need them. Uncomment only if you hit a specific bug they address — turning them
on speculatively causes its own problems.

## Monitors

Single internal display. Configured in `~/.config/hypr/config/monitors.lua`.

```
eDP-1  1920x1080@60  at 0x0
```

Adding an external monitor means editing that file. `hyprctl monitors` prints
what the compositor currently sees, which is the fastest way to get the exact
name and mode string for a new display.

## Audio

PipeWire 1.6.8 with the PulseAudio compatibility layer. The default sink on this
machine was a Bluetooth headset — you will need to re-pair it, since Bluetooth
pairing keys are in `/var/lib/bluetooth` and are not tracked.

## Firmware

Check for updates after a rebuild:

```bash
sudo fwupdmgr refresh && sudo fwupdmgr get-updates
```
