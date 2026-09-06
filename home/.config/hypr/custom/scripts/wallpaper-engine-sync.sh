#!/usr/bin/env bash
# Applies the wallpaper you pick in the real Wallpaper Engine app (running under Proton)
# using linux-wallpaperengine, which renders it natively on Wayland.
#
# Why this exists: WE writes your pick to its config.json, but nothing upstream watches that
# file. linux-wallpaperengine only parses the "playlist" sub-key, only at startup, and only at
# steamuser.wallpaperconfig -- while this install writes to steamuser.general.wallpaperconfig.
# So we watch the file ourselves and relaunch on change (runtime switching is unsupported
# upstream, hence kill-and-relaunch rather than signalling the running process).
#
# Also supervises the renderer: it exits rather than recovers when the compositor drops its
# layer surface on monitor power-cycle (upstream issue #438), which a laptop lid does often.

set -uo pipefail

WE_DIR="$HOME/.local/share/Steam/steamapps/common/wallpaper_engine"
CONFIG="${WPE_CONFIG:-$WE_DIR/config.json}"
ASSETS="$WE_DIR/assets"
WORKSHOP="$HOME/.local/share/Steam/steamapps/workshop/content/431960"

SCREEN="${WPE_SCREEN:-eDP-1}"
FPS="${WPE_FPS:-30}"
EXTRA_ARGS="${WPE_EXTRA_ARGS:---noautomute}" # --noautomute dodges the PulseAudio startup deadlock (#649)

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wallpaper-engine-sync"
STATE_FILE="$STATE_DIR/current"
LOG="$STATE_DIR/renderer.log"
mkdir -p "$STATE_DIR"

log() { printf '%s %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }

# Prints candidate wallpaper tokens (workshop ids and filesystem paths), best guess first.
# WE's selectedwallpapers shape varies by version, so walk the whole subtree instead of
# assuming a key layout, and let the caller validate what actually exists on disk.
candidates() {
    python3 - "$CONFIG" <<'PY' 2>/dev/null
import json, re, sys

try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)

steamuser = data.get("steamuser", {})
roots = [steamuser.get("wallpaperconfig"),
         steamuser.get("general", {}).get("wallpaperconfig")]

def windows_to_unix(value):
    # Mirrors upstream's own path fixup: Proton hands back \\?\Z:\home\... style paths.
    cleaned = value.removeprefix("\\\\?\\").replace("\\", "/")
    if len(cleaned) > 1 and cleaned[1] == ":":
        cleaned = cleaned[2:]
    return cleaned

paths, ids = [], []

def walk(node):
    if isinstance(node, dict):
        for value in node.values():
            walk(value)
    elif isinstance(node, list):
        for value in node:
            walk(value)
    elif isinstance(node, str):
        if "/" in node or "\\" in node:
            paths.append(windows_to_unix(node))
        # A bare id straight from the workshop.
        if re.fullmatch(r"\d{6,}", node):
            ids.append(node)
    elif isinstance(node, int) and len(str(node)) >= 6:
        ids.append(str(node))

for root in roots:
    if root:
        walk(root.get("selectedwallpapers"))

# Ids embedded in a workshop path are the strongest signal, so emit those first.
for path in paths:
    match = re.search(r"431960/+(\d+)", path)
    if match:
        print(match.group(1))
for path in paths:
    print(path)
for wid in ids:
    print(wid)
PY
}

# Echoes something linux-wallpaperengine can actually render, or nothing.
resolve_target() {
    local candidate
    while read -r candidate; do
        [[ -z "$candidate" ]] && continue
        if [[ -d "$WORKSHOP/$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
        # A local (non-workshop) project, e.g. one of your own under projects/myprojects.
        if [[ -f "$candidate/project.json" ]]; then
            echo "$candidate"
            return 0
        fi
        if [[ -f "$candidate" && "$(basename "$candidate")" == "project.json" ]]; then
            echo "$(dirname "$candidate")"
            return 0
        fi
    done < <(candidates)
    return 1
}

# Match on the command line, not the process name: the kernel truncates comm to 15 chars
# ("linux-wallpaper"), so pgrep/pkill -x can never match this binary.
RENDERER_PATTERN="linux-wallpaperengine --assets-dir"

renderer_pid=""

renderer_running() {
    [[ -n "$renderer_pid" ]] && kill -0 "$renderer_pid" 2>/dev/null && return 0
    pgrep -f "$RENDERER_PATTERN" >/dev/null 2>&1
}

apply() {
    local target="$1"
    [[ -n "$renderer_pid" ]] && kill "$renderer_pid" 2>/dev/null
    # Upstream supports only one instance, so sweep strays a previous run may have left behind.
    pkill -f "$RENDERER_PATTERN" 2>/dev/null
    # Give the compositor a moment to release the old layer surface before claiming a new one.
    sleep 0.3
    # shellcheck disable=SC2086
    nohup linux-wallpaperengine \
        --assets-dir "$ASSETS" \
        --screen-root "$SCREEN" \
        --fps "$FPS" \
        --layer background \
        $EXTRA_ARGS \
        "$target" >"$LOG" 2>&1 &
    renderer_pid=$!
    disown
    echo "$target" >"$STATE_FILE"
    log "applied $target (pid $renderer_pid)"
}

case "${1:-}" in
    # Reports what the current config resolves to, without touching the running wallpaper.
    --check)
        if target="$(resolve_target)"; then
            echo "$target"
            exit 0
        fi
        echo "no wallpaper selection found in $CONFIG" >&2
        exit 1
        ;;
    # Lists installed wallpapers with their titles, so you can pick an id by hand.
    --list)
        for dir in "$WORKSHOP"/*/; do
            id="$(basename "$dir")"
            title="$(jq -r '.title // "?"' "$dir/project.json" 2>/dev/null)"
            printf '%-12s %s\n' "$id" "$title"
        done
        exit 0
        ;;
    # Applies a wallpaper directly, bypassing Wallpaper Engine's config entirely.
    # The running watcher keeps it alive and will still switch when you pick one in the app.
    --set)
        [[ -z "${2:-}" ]] && { echo "usage: $0 --set <workshop-id|project-dir>" >&2; exit 1; }
        if [[ ! -d "$WORKSHOP/$2" && ! -f "$2/project.json" ]]; then
            echo "not an installed wallpaper: $2" >&2
            exit 1
        fi
        apply "$2"
        exit 0
        ;;
esac

current="$(cat "$STATE_FILE" 2>/dev/null || true)"

# Restore the last pick on login, so the wallpaper survives a reboot even before WE runs.
if target="$(resolve_target)"; then
    current="$target"
elif [[ -n "$current" ]]; then
    target="$current"
else
    target=""
fi
[[ -n "$target" ]] && apply "$target"

while true; do
    if command -v inotifywait >/dev/null 2>&1; then
        # move_self/create too: WE rewrites config.json rather than editing it in place.
        inotifywait -qq -t 30 -e close_write,modify,move_self "$CONFIG" 2>/dev/null
        inotifywait -qq -t 1 -e close_write,create,moved_to "$WE_DIR" 2>/dev/null
    else
        sleep 5
    fi

    if target="$(resolve_target)" && [[ "$target" != "$current" ]]; then
        current="$target"
        apply "$target"
    elif [[ -n "$current" ]] && ! renderer_running; then
        log "renderer died, restarting"
        apply "$current"
    fi
done
