# cachyos-setup

Everything needed to rebuild this laptop — a CachyOS (Arch) machine running
Hyprland with the [end-4 illogical-impulse](https://github.com/end-4/dots-hyprland)
desktop — from a blank disk.

Private repo. It holds configuration only: **no keys, no tokens, no browser
profiles.** What has to be re-authenticated by hand is listed in
[docs/04-secrets-and-logins.md](docs/04-secrets-and-logins.md).

## Rebuilding, short version

```bash
git clone git@github.com:<you>/cachyos-setup.git ~/dev/cachyos-setup
cd ~/dev/cachyos-setup
./packages/restore.sh      # install the programs
./install.sh               # symlink the config into $HOME
```

Then work through [docs/01-fresh-install.md](docs/01-fresh-install.md), which
covers the parts a script cannot do: partitioning, the ii desktop installer,
NVIDIA, and logging back into things.

**Read the long version the first time.** The short version assumes CachyOS is
already installed and that you have an AUR helper. On genuinely bare metal the
order matters, and `01-fresh-install.md` is that order.

## Docs

| | |
|---|---|
| [01-fresh-install.md](docs/01-fresh-install.md) | Blank disk to working desktop, in order |
| [02-desktop.md](docs/02-desktop.md) | Hyprland, ii dots, the local patches |
| [03-apps.md](docs/03-apps.md) | Per-app setup, editors, wallpapers |
| [04-secrets-and-logins.md](docs/04-secrets-and-logins.md) | What is deliberately missing and how to restore it |
| [05-hardware.md](docs/05-hardware.md) | This specific machine: GPU, disks, dual boot |
| [06-maintenance.md](docs/06-maintenance.md) | Keeping the repo in step with the machine |

## Layout

```
manifest.txt              every tracked path, tagged by group
install.sh                symlink repo -> $HOME (idempotent, backs up first)
sync.sh                   the reverse: pull live config back into the repo
sanitize.py               strips credentials from repo copies; sync.sh runs it
home/                     mirrors $HOME exactly, so a path here is its path there
packages/                 pacman / AUR / flatpak lists + restore.sh
patches/ii-dots/          local changes to upstream ii, as re-appliable patches
wallpapers/               static images + Wallpaper Engine workshop manifest
system/etc/               system config worth keeping (greetd, udev)
docs/                     the guides above
```

## The two scripts

**`install.sh`** links `home/<path>` to `$HOME/<path>` for every line in
`manifest.txt`. Anything already pointing here is left alone, so rerunning is
safe. Anything else in the way is moved to `~/config-backup-<timestamp>/` first —
nothing is ever destroyed. `--dry-run` shows the plan; `--list` shows the groups
(`desktop`, `shell`, `terminal`, `theme`, `audio`, `apps`, `editors`, `claude`),
and naming groups installs only those.

**`sync.sh`** goes the other way, for when you change a config on the machine and
want the repo to match. It skips anything already symlinked (those files *are*
the repo), refreshes the package lists, and runs `sanitize.py` before you commit.

Once `install.sh` has run, most edits need no sync at all — you are editing the
repo through a symlink. `sync.sh` is for the machine you have not linked yet, and
for the package lists.
