#!/usr/bin/env bash
# Reinstall the packages recorded in this directory.
#
# Run this on a fresh CachyOS install BEFORE ../install.sh, so the programs
# exist by the time their config gets linked into place.
#
#   ./restore.sh --dry-run    print what would be installed
#   ./restore.sh              install native, then AUR, then flatpak
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]] && DRY_RUN=1

run() {
  if (( DRY_RUN )); then printf "would run: %s\n" "$*"; else "$@"; fi
}

# Only ask for what is not already installed, so reruns are quiet and fast.
missing_from() {
  local list="$1"
  [[ -f "$list" ]] || return 0
  while IFS= read -r pkg; do
    [[ -z "$pkg" || "$pkg" == \#* ]] && continue
    pacman -Qq "$pkg" &>/dev/null || printf "%s\n" "$pkg"
  done < "$list"
}

echo "== Native packages (pacman) =="
mapfile -t native < <(missing_from "${HERE}/pacman-native.txt")
if [[ ${#native[@]} -eq 0 ]]; then
  echo "  nothing to do"
else
  echo "  ${#native[@]} to install"
  run sudo pacman -S --needed "${native[@]}"
fi

echo
echo "== AUR packages =="
helper=""
for h in paru yay; do command -v "$h" &>/dev/null && { helper="$h"; break; }; done
if [[ -z "$helper" ]]; then
  echo "  no AUR helper found. Install one first:"
  echo "    sudo pacman -S --needed base-devel git"
  echo "    git clone https://aur.archlinux.org/paru-bin.git && cd paru-bin && makepkg -si"
else
  mapfile -t aur < <(missing_from "${HERE}/aur.txt")
  if [[ ${#aur[@]} -eq 0 ]]; then
    echo "  nothing to do"
  else
    echo "  ${#aur[@]} to install via $helper"
    run "$helper" -S --needed "${aur[@]}"
  fi
fi

echo
echo "== Flatpak =="
if ! command -v flatpak &>/dev/null; then
  echo "  flatpak not installed; skipping"
elif [[ -s "${HERE}/flatpak.txt" ]]; then
  while IFS= read -r app; do
    [[ -z "$app" ]] && continue
    run flatpak install -y flathub "$app"
  done < "${HERE}/flatpak.txt"
else
  echo "  nothing recorded"
fi

echo
echo "Done. Next: ../install.sh"
