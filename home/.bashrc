#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

alias ls='ls --color=auto'
alias grep='grep --color=auto'
if [[ "$TERM" != "linux" ]]; then
    [[ ":$PATH:" == *":$HOME/.local/bin:"* ]] || export PATH="$HOME/.local/bin:$PATH"
    eval "$(oh-my-posh init bash --config ~/.config/oh-my-posh/marcduiker.omp.json)"
else
    PS1='[\u@\h \W]\$ '
fi
