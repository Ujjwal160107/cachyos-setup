#!/usr/bin/env bash
# Brings up linux-wallpaperengine the moment Hyprland starts, using whatever was last picked
# in the Linux Wallpaper Engine GUI, and keeps a static frame of it for ii's lock screen.
#
# Why not let the GUI do it: it is an Electron app started via XDG autostart, and on this
# machine it brought the wallpaper up minutes after login. The GUI stays the place to pick
# wallpapers; this script reads its active-wallpapers.json and re-syncs when that changes.
# While the GUI is open it launches and supervises the renderer itself, so this script only
# takes over launching when the GUI is not running.
set -uo pipefail

GUI_DIR="$HOME/.config/Linux Wallpaper Engine"
ACTIVE="$GUI_DIR/active-wallpapers.json"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wallpaper-engine"
LOCK_IMAGE="$STATE_DIR/lockscreen.png"
PICK_FILE="$STATE_DIR/current"
SWITCHWALL="$HOME/.config/quickshell/ii/scripts/colors/switchwall.sh"
LAYER="${WPE_LAYER:-bottom}"
mkdir -p "$STATE_DIR"

# The kernel truncates comm to 15 chars ("linux-wallpaper"), so match the command line.
RENDERER='linux-wallpaperengine .*--screen-root'

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$STATE_DIR/sync.log"; }

pick() { jq -r '.activeWallpapers | to_entries[0].value.backgroundId // empty' "$ACTIVE" 2>/dev/null; }

# Screen, background and scaling: shared by the live renderer and the screenshot instance.
base_args() {
    jq -r '(.activeWallpapers | to_entries[0].value // empty)
           | ["--screen-root", .screen, "--bg", .backgroundId, "--scaling", (.scaling // "fill")][]' \
       "$ACTIVE" 2>/dev/null
}

# The rest of the GUI's per-wallpaper settings. --silent and --volume are mutually exclusive.
live_args() {
    jq -r '(.activeWallpapers | to_entries[0].value // empty)
           | ["--fps", ((.fps // 30) | tostring)]
           + (if .silent then ["--silent"] else ["--volume", ((.volume // 0) | tostring)] end)
           + (if .noAutomute then ["--noautomute"] else [] end)
           + (if .noAudioProcessing then ["--no-audio-processing"] else [] end)
           + (if .disableMouse then ["--disable-mouse"] else [] end)
           + (if .disableParallax then ["--disable-parallax"] else [] end)
           + (if .disableParticles then ["--disable-particles"] else [] end)
           + (if .noFullscreenPause then ["--no-fullscreen-pause"] else [] end)
           | .[]' "$ACTIVE" 2>/dev/null
}

renderer_running() { pgrep -f "$RENDERER" >/dev/null 2>&1; }
gui_running() { pgrep -f 'linux-wallpaper-engine-ux/app.asar' >/dev/null 2>&1; }

launch() {
    local -a base live
    mapfile -t base < <(base_args)
    mapfile -t live < <(live_args)
    if [[ ${#base[@]} -eq 0 ]]; then
        log "no wallpaper selected in $ACTIVE"
        return 1
    fi
    nohup linux-wallpaperengine --layer "$LAYER" "${base[@]}" "${live[@]}" >"$STATE_DIR/renderer.log" 2>&1 &
    disown
    log "launched ${base[*]} ${live[*]}"
}

# Renders one frame of the current pick into LOCK_IMAGE with a second instance on the
# background layer, which sits underneath the live renderer so nothing flashes on screen.
# The renderer has no "exit after screenshot", so it is killed once the file lands.
make_lock_image() {
    local -a base
    mapfile -t base < <(base_args)
    [[ ${#base[@]} -eq 0 ]] && return 1
    local tmp="$STATE_DIR/lockscreen.tmp.png"
    rm -f "$tmp"
    linux-wallpaperengine --layer background --fps 30 --silent --disable-mouse \
        --screenshot "$tmp" --screenshot-delay 30 "${base[@]}" >/dev/null 2>&1 &
    local pid=$!
    for _ in $(seq 1 60); do
        sleep 0.5
        [[ -s "$tmp" ]] && break
    done
    sleep 1 # let the PNG finish writing
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    if [[ ! -s "$tmp" ]]; then
        rm -f "$tmp"
        log "lock image failed for $(pick)"
        return 1
    fi
    mv -f "$tmp" "$LOCK_IMAGE"
    # ii's lock screen shows Config.options.background.wallpaperPath, so hand it the frame.
    # This also re-derives ii's colour scheme from the wallpaper, as any ii wallpaper does.
    [[ -x "$SWITCHWALL" ]] && "$SWITCHWALL" --image "$LOCK_IMAGE" >/dev/null 2>&1
    log "lock image updated for $(pick)"
}

current="$(cat "$PICK_FILE" 2>/dev/null || true)"

# On login: wallpaper first, static frame second.
if ! renderer_running && ! gui_running; then
    launch
fi
if [[ "$(pick)" != "$current" || ! -s "$LOCK_IMAGE" ]]; then
    current="$(pick)"
    echo "$current" >"$PICK_FILE"
    make_lock_image
fi

while true; do
    # The GUI rewrites the file rather than editing it, so watch the directory for it.
    inotifywait -qq -t 5 -e close_write,moved_to,create --include 'active-wallpapers.json' "$GUI_DIR" 2>/dev/null

    if [[ -n "$(pick)" && "$(pick)" != "$current" ]]; then
        current="$(pick)"
        echo "$current" >"$PICK_FILE"
        log "pick changed to $current"
        # The GUI applies its own pick; only relaunch when nobody else will.
        if ! gui_running; then
            pkill -f "$RENDERER" 2>/dev/null
            sleep 0.3
            launch
        fi
        make_lock_image
    elif ! renderer_running && ! gui_running; then
        # The renderer exits instead of recovering when the compositor drops its layer
        # surface on a monitor power-cycle (upstream #438), which a laptop lid does often.
        log "renderer gone, relaunching"
        launch
    fi
done
