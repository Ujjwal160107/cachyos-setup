# Maintenance

A setup repo is only worth having if it matches the machine. This is how to keep
it that way.

## The two states

After `install.sh` has run, tracked config files in `$HOME` are **symlinks into
this repo**. Editing `~/.config/hypr/custom/rules.conf` edits the repo file
directly, and `git status` shows it. No sync step needed — just commit.

Before `install.sh` has run — on this machine, right now — the files in `$HOME`
are real files and the repo holds copies. That is what `sync.sh` is for.

Check which state you are in:

```bash
ls -l ~/.config/hypr
```

A symlink into `~/dev/cachyos-setup` means you are linked.

## Routine sync

```bash
cd ~/dev/cachyos-setup
./sync.sh
git diff --stat
git add -A && git commit -m "sync: <what changed>"
git push
```

`sync.sh` copies unlinked paths back, refreshes the package lists, and runs
`sanitize.py`. Read the diff before committing — that is the step that catches a
config file that started holding a credential.

Worth doing after: installing or removing packages, changing keybindings or
monitor layout, updating ii, or changing wallpapers.

## Adding something new

Tracking a new config file takes two steps.

1. Add a line to `manifest.txt` under the right group:

```
desktop:.config/newthing
```

2. Sync and commit:

```bash
./sync.sh && git add -A && git commit -m "track newthing config"
```

`install.sh` picks it up automatically on the next machine — the manifest is the
single source of truth for both scripts.

**Check for secrets first.** If the app stores a token in the file you are about
to track, either exclude that file or add a handler to `sanitize.py`.

## Adding a secret handler

`sanitize.py` uses one explicit handler per file rather than a blanket regex,
because a broad search-and-replace over config silently mangles settings.

To add one, write a function taking a `pathlib.Path`, editing it in place, and
returning the list of redacted key names. Then register it:

```python
HANDLERS = {
    "home/.claude/settings.json": scrub_claude_settings,
    "home/.config/newthing/config.json": scrub_newthing,
}
```

The backstop at the end scans everything under `home/` for credential shapes and
exits non-zero if any survive, so a missed handler fails loudly instead of
leaking.

## Updating ii

The riskiest routine change, because ii overwrites config in place.

```bash
git -C ~/.local/share/dots-hyprland pull
cd ~/.local/share/dots-hyprland && ./setup
```

Then, every time:

1. Reapply the two QML patches — see
   [02-desktop.md](02-desktop.md#reapplying-after-an-ii-update). The animated
   wallpaper breaks silently without them.
2. `./sync.sh` to pull the new upstream tree into the repo.
3. Update the pinned commit in `02-desktop.md` **and** in
   [01-fresh-install.md](01-fresh-install.md) — both name it.
4. Regenerate the patches if upstream moved the code they touch.
5. Commit with the new commit hash in the message.

If the desktop breaks, `git revert` the sync commit, run `install.sh` again, and
you are back — which is the entire reason the whole tree is tracked rather than a
diff.

## Keeping the docs honest

Stale docs are worse than none, because you trust them at the moment you can
least afford to. When you change the machine, change the doc in the same commit.

The claims most likely to rot:

| Claim | Where | Check with |
|---|---|---|
| ii pinned commit | `02-desktop.md`, `01-fresh-install.md` | `git -C ~/.local/share/dots-hyprland log -1` |
| Package counts | `01-fresh-install.md` | `wc -l packages/*.txt` |
| Extension counts | `03-apps.md` | `wc -l editors/*.txt` |
| Disk layout | `05-hardware.md` | `lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT` |
| Enabled services | `01-fresh-install.md` | `systemctl list-unit-files --state=enabled` |
| Driver version | `05-hardware.md` | `nvidia-smi` |

## Testing the rebuild without rebuilding

The one thing this repo cannot prove is that a fresh install actually works. The
cheap approximation:

```bash
./install.sh --dry-run          # every path resolves, nothing unexpected
./packages/restore.sh --dry-run # every package still exists in the repos
bash -n install.sh sync.sh packages/restore.sh
python3 sanitize.py             # exits non-zero if any secret leaked in
```

Worth running before a push. A real test means a VM, and is worth doing once
before you ever need it for real.

## Periodic check

Every few months, or before any risky change:

```bash
cd ~/dev/cachyos-setup
./sync.sh
git status              # drifted? commit it
git diff --stat
```

If `sync.sh` prints `MISSING on this machine` for a path, you removed that config
without removing it from `manifest.txt`. Drop the line.
