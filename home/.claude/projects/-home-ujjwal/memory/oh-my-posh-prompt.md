---
name: oh-my-posh-prompt
description: Prompt is oh-my-posh (marcduiker theme) in fish/zsh/bash, replacing starship and p10k; font ComicShannsMono Nerd Font Mono
metadata:
  type: project
---

Set up 2026-10-02. One theme at `~/.config/oh-my-posh/marcduiker.omp.json` (exact hex colours, OS icon, exec time, node/python/go, transient prompt) is shared by fish, zsh and bash. Font is ComicShannsMono Nerd Font Mono in kitty, alacritty and the VS Code terminal only (not the editor).

**Why:** the user asked for the Hanselman-blog oh-my-posh look and chose to replace starship rather than keep it as a fallback. `starship.toml` stays in the repo, unused.

**How to apply:**
- zsh: `/usr/share/cachyos-zsh-config/cachyos-config.zsh` sources p10k and can't be edited. `~/.zshrc` strips the `_p9k_*` hooks before running `omp init zsh`. Don't call `prompt_powerlevel10k_teardown`; it doesn't exist here.
- The fish greeting depends on the OSC fix in config.fish, see [[ii-dots-install]].
- Bash has no transient prompt (omp needs ble.sh for that).
- `.config/oh-my-posh` is in cachyos-setup's manifest.txt but not yet synced or committed.
