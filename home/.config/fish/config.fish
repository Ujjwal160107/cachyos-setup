# Commands to run in interactive sessions can go here
if status is-interactive
    # No greeting
    set fish_greeting

    # Prompt: oh-my-posh (marcduiker). Transient prompt is set in the theme.
    if test "$TERM" != "linux"
        oh-my-posh init fish --config ~/.config/oh-my-posh/marcduiker.omp.json | source
    end
    
    # Colors
    if test -f ~/.local/state/quickshell/user/generated/terminal/sequences.txt
        cat ~/.local/state/quickshell/user/generated/terminal/sequences.txt
        # ii writes this file with the final OSC terminator cut off (it ends on
        # a bare ESC). Without this the terminal stays inside that OSC string
        # and silently swallows whatever the shell prints next.
        printf "\033\\\\"
    end

    # Aliases
    # kitty doesn't clear properly so we need to do this weird printing
    alias clear "printf '\033[2J\033[3J\033[1;1H'"
    alias celar "printf '\033[2J\033[3J\033[1;1H'"
    alias claer "printf '\033[2J\033[3J\033[1;1H'"
    alias pamcan pacman
    alias q 'qs -c ii'
    if test "$TERM" != "linux"
        alias ls 'eza --icons=auto'
    end
    if test "$TERM" = "xterm-kitty"
        alias ssh 'kitten ssh'
    end

    # Greeting: only in a fresh terminal. The marker is exported, so nested
    # shells (subshells, tmux panes, shells Claude Code spawns) inherit it and
    # stay quiet. A new kitty window/tab starts from kitty's env, so it prints.
    if not set -q __fastfetch_shown
        set -gx __fastfetch_shown 1
        fastfetch
    end
end
