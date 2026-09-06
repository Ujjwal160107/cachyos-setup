#!/usr/bin/env bash
# Pull the live config in $HOME back into this repo.
#
# Use this when you changed something on the machine and want the repo to
# match. It is the reverse of install.sh. Files already symlinked by
# install.sh are skipped: they *are* the repo, so copying them would be a
# no-op at best and would clobber the repo with a dangling link at worst.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME}"

# Junk that should never be tracked, whatever directory it turns up in.
EXCLUDES=(
  --exclude='*.old' --exclude='*.bak' --exclude='*.tmp' --exclude='*~'
  --exclude='.git' --exclude='.gitmodules' --exclude='Cache/' --exclude='GPUCache/' --exclude='Code Cache/'
  --exclude='blob_storage/' --exclude='Crashpad/' --exclude='logs/'
  --exclude='*.log' --exclude='*.pid' --exclude='*.lock' --exclude='*.sock'
  --exclude='.DS_Store'
)

while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
  rel="${line#*:}"
  src="${HOME_DIR}/${rel}"
  dest="${REPO}/home/${rel}"

  if [[ -L "$src" ]] && [[ "$(readlink -f "$src")" == "${REPO}/"* ]]; then
    printf '  skip (already linked)  %s\n' "$rel"
    continue
  fi
  if [[ ! -e "$src" ]]; then
    printf '  MISSING on this machine  %s\n' "$rel"
    continue
  fi

  mkdir -p "$(dirname "$dest")"
  if [[ -d "$src" ]]; then
    rsync -a --delete "${EXCLUDES[@]}" "$src/" "$dest/"
  else
    rsync -a "${EXCLUDES[@]}" "$src" "$dest"
  fi
  printf '  synced  %s\n' "$rel"
done < "${REPO}/manifest.txt"

echo
echo "Refreshing package lists..."
pacman -Qqe > "${REPO}/packages/pacman-explicit.txt"
pacman -Qqm > "${REPO}/packages/aur.txt"
grep -Fxv -f "${REPO}/packages/aur.txt" "${REPO}/packages/pacman-explicit.txt" \
  > "${REPO}/packages/pacman-native.txt"
if command -v flatpak >/dev/null; then
  flatpak list --app --columns=application > "${REPO}/packages/flatpak.txt"
fi

# Extension lists come from the extension directories, not `--list-extensions`:
# the CLI needs a display and silently returns nothing over SSH or in a script.
for pair in "$HOME/.vscode/extensions:vscode" \
            "$HOME/.cursor/extensions:cursor" \
            "$HOME/.vscode-oss/extensions:vscodium"; do
  dir="${pair%%:*}"; name="${pair##*:}"
  [[ -d "$dir" ]] || continue
  find "$dir" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" \
    | sed -E "s/-[0-9]+\\.[0-9]+\\.[0-9]+.*$//" \
    | sort -u > "${REPO}/editors/${name}-extensions.txt"
done

echo
echo "Sanitizing..."
python3 "${REPO}/sanitize.py"

echo "Done. Review with 'git -C ${REPO} status' before committing."
