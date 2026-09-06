# Secrets and logins

Nothing in this repo can log you in. This is the list of what was deliberately
left out and how to restore each piece by hand.

Everything here is blocked by `.gitignore` as well as being absent, so a stray
`git add -A` cannot pull it in later.

## Read this first: rotate the GitHub token

While building this repo, a **live GitHub personal access token** was found in
plaintext in `~/.claude/settings.json` under `env.GITHUB_PERSONAL_ACCESS_TOKEN`.

It was never committed — the pre-commit scan caught it and `sanitize.py` now
replaces it with a placeholder on every sync. But it sat unencrypted in a config
file, and the `github` MCP server was returning HTTP 401 with it, which suggests
it is expired or revoked already.

**Revoke it and issue a new one:** <https://github.com/settings/tokens>

Then put the new one back on this machine only, never in the repo:

```bash
# ~/.claude/settings.json, env block
"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."
```

`sanitize.py` will strip it from the repo copy the next time `sync.sh` runs. If
you would rather not keep a token in a config file at all, put it in your
password manager and export it from a shell fragment that is itself gitignored.

## SSH keys

**Not in the repo. Never put them in.**

Three keys exist on this machine:

| Key | Use |
|---|---|
| `id_ed25519` | Primary |
| `id_ed25519_antra` | The `Antra1705` GitHub account |
| `fortuna_deploy` | A deploy key |

On a new machine, either restore them from your password manager or offline
backup, or generate fresh ones and re-register the public halves:

```bash
ssh-keygen -t ed25519 -C "yash@cruitical.com"
chmod 700 ~/.ssh && chmod 600 ~/.ssh/id_ed25519
gh ssh-key add ~/.ssh/id_ed25519.pub
```

If you use several GitHub identities, `~/.ssh/config` needs a `Host` block per
key. That file is also not tracked.

## GitHub CLI

```bash
gh auth login -h github.com -s repo -w
```

Writes `~/.config/gh/hosts.yml`, which is gitignored.

Worth knowing: logging into github.com in a **browser** does not authenticate
`gh`. They are separate. Confirm the CLI is actually working with:

```bash
gh api user --jq .login
```

## Git credentials

`~/.gitconfig` **is** tracked, and sets `credential.helper = store`. That helper
writes plaintext credentials to `~/.git-credentials`, which is **not** tracked.

Plaintext storage is a real weakness. If you want to fix it during the rebuild,
switch to the libsecret helper, which uses your keyring:

```bash
sudo pacman -S git-credential-libsecret
git config --global credential.helper /usr/lib/git-credential-libsecret
```

## Cloud and package registries

| What | Restore with |
|---|---|
| Google Cloud | `gcloud auth login` and `gcloud auth application-default login` |
| Heroku | `heroku login` |
| npm | `npm login` — writes `~/.npmrc` |
| Docker registries | `docker login` |
| Tailscale | `sudo tailscale up`, then approve in a browser |

## Browser profiles

Chrome, Zen and Thorium profiles are excluded — they are hundreds of megabytes
of cache wrapped around cookies and saved passwords, and committing them would
put your live sessions in a git repo.

Sign in to each browser and let its own sync restore bookmarks, extensions and
passwords. Only the `*-flags.conf` files are tracked, and those carry no
identity.

## Apps needing a fresh sign-in

Slack, Discord, Spotify, Steam, Postman, VS Code / Cursor / Antigravity sync,
and Claude Code (`claude login`).

## GPG

`~/.gnupg/` is excluded. If you sign commits, restore your secret key from
backup:

```bash
gpg --import private-key-backup.asc
git config --global user.signingkey <KEY_ID>
```

## Keyrings

`~/.local/share/keyrings/` is excluded. The GNOME keyring is created fresh on
first login and repopulates as you sign in to things.

## The rule

If something authenticates you, it does not belong in this repo — even a private
one. Private repos get shared, forked, cloned onto other machines, and handed to
tools. Config is safe to keep; credentials are not.
