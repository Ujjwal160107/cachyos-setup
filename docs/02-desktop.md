# The desktop: Hyprland + illogical-impulse

## What is upstream and what is yours

The desktop is [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland),
known as **illogical-impulse** or **ii**. Almost everything under
`~/.config/hypr`, `~/.config/quickshell`, `~/.config/matugen` and
`~/.config/illogical-impulse` came from that project.

This repo stores the **whole tree**, not a diff. That is a deliberate trade: it
costs about 8 MB and duplicates upstream, but it means `install.sh` restores a
working desktop without depending on the ii installer behaving the same way next
year. `patches/ii-dots/` separately records what you changed, so you can tell
your edits from theirs.

**Pinned version:**

```
97c5bc651f68092351b24aaa935af708b1e04514
2026-08-27 — "gentoo rework (#3625)"
```

Installed on this machine 2026-09-06.

## Installing ii

```bash
git clone https://github.com/end-4/dots-hyprland.git ~/.local/share/dots-hyprland
cd ~/.local/share/dots-hyprland
git checkout 97c5bc651f68092351b24aaa935af708b1e04514
./setup
```

`./setup` is interactive and writes directly into `~/.config`. Run it **before**
`install.sh`, never after.

### UWSM

The ii installer offers UWSM (Universal Wayland Session Manager) session
handling. **This machine does not use it.** It was tried and caused session
startup problems; Hyprland is launched directly by greetd instead. Say no when
asked. If you say yes and the session fails to come up, that is the first thing
to undo.

## The two local patches

Exactly two QML files differ from upstream. Both exist for the same reason: to
get **linux-wallpaperengine** (animated wallpapers) to render underneath the ii
shell instead of being hidden by it.

`patches/ii-dots/` holds them as unified diffs against the pinned commit.

### `Background.qml`

ii draws its static wallpaper on the `Bottom` Wayland layer. linux-wallpaperengine
also draws on `Bottom`, and loses. The patch moves the ii background down to the
`Background` layer while the screen is unlocked, so the animated wallpaper shows
through. It still lifts to `Overlay` when locked, so the lock screen keeps a
static image.

### `IllogicalImpulseFamily.qml`

A comment recording why the `Background` panel loader is left alone — so the next
person reading it (you, in a year) does not "fix" the layer back to `Bottom` and
quietly break the animated wallpaper.

### Reapplying after an ii update

**This is the thing that bites.** Updating ii overwrites both files and the
animated wallpaper silently stops showing. There is no error; the desktop just
goes back to a static background.

```bash
cd ~/.config
git -C ~/.local/share/dots-hyprland pull      # or however you update ii
patch -p1 < ~/dev/cachyos-setup/patches/ii-dots/Background.qml.patch
patch -p1 < ~/dev/cachyos-setup/patches/ii-dots/IllogicalImpulseFamily.qml.patch
```

If `patch` rejects a hunk, upstream changed that region. Open the `.rej` file,
find where `WlrLayershell.layer` is now set in `Background.qml`, and change
`WlrLayer.Bottom` to `WlrLayer.Background` in the unlocked branch by hand. Then
regenerate the patches so the repo matches reality:

```bash
cd ~/dev/cachyos-setup && ./sync.sh
```

## Config you actually edit

ii keeps user-facing settings apart from its internals. These are the files worth
knowing:

| Path | What |
|---|---|
| `~/.config/hypr/custom/` | Your Hyprland overrides. ii does not touch this. Put personal rules here. |
| `~/.config/hypr/hyprland/keybinds.lua` | Keybindings |
| `~/.config/hypr/config/monitors.lua` | Monitor layout — see [05-hardware.md](05-hardware.md) |
| `~/.config/hypr/config/environment.lua` | Session environment variables |
| `~/.config/illogical-impulse/config.json` | Shell behaviour: bar, dock, panels |
| `~/.config/matugen/config.toml` | Material You colour generation targets |

`~/.config/hypr/custom/` is the right place for anything personal. Everything
else under `hypr/` is upstream and will be overwritten by the next ii update.

## Theming

Colours are generated from the wallpaper by **matugen** (Material You) and pushed
into GTK, Qt (via Kvantum), KDE, Hyprland and the shell.
`~/.config/matugen/templates/` holds one template per target.

Regenerate after changing the wallpaper:

```bash
matugen image ~/Pictures/Wallpapers/random_wallpaper.png
```

The generated KDE colour schemes land in `~/.local/share/color-schemes/`
(`MaterialYouDark`, `MaterialYouLight`, and `_darker_titlebar` variants) and are
tracked in this repo.

- **Qt:** Kvantum with the `MaterialAdw` and `Colloid` themes, wired up through
  `qt5ct` and `qt6ct`
- **GTK:** `adw-gtk-theme-git` plus matugen-generated colours in `gtk-3.0`/`gtk-4.0`
- **Cursor:** Bibata-Modern-Ice
- **Icons:** the ii icon theme
- **UI font:** Google Sans Flex, from `illogical-impulse-fonts-themes`

## Shell and bar

`quickshell` runs the ii shell: bar, dock, notifications, overview, lock screen.

`waybar` is also installed and configured but **not in use** — the ii bar
replaces it. The waybar config is kept as a fallback for when a quickshell update
breaks the bar and you need something on screen while you sort it out.
