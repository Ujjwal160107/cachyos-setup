source /usr/share/cachyos-zsh-config/cachyos-config.zsh

# added by linux migration 20260905-2356: npm global prefix
export PATH="$HOME/.local/bin:$PATH"

# Prompt: oh-my-posh replaces powerlevel10k, which cachyos-config.zsh loads
# above (and we can't edit that file). It has no teardown function when sourced
# that way, so drop its hooks or it retakes PROMPT and starts gitstatusd.
if [[ "$TERM" != "linux" ]]; then
  precmd_functions=(${precmd_functions:#_p9k_*})
  preexec_functions=(${preexec_functions:#_p9k_*})
  chpwd_functions=(${chpwd_functions:#_p9k_*})
  eval "$(oh-my-posh init zsh --config ~/.config/oh-my-posh/marcduiker.omp.json)"
fi
