#!/usr/bin/env bash
# Symlink this repo's config into $HOME.
#
# Idempotent: anything already pointing at this repo is left alone. Anything
# else that is in the way gets moved into a timestamped backup directory first,
# so a bad run is always reversible.
#
#   ./install.sh --dry-run          show what would happen, change nothing
#   ./install.sh                    link every group
#   ./install.sh desktop shell      link only those groups
#   ./install.sh --list             show the groups
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${REPO}/manifest.txt"
BACKUP="${HOME}/config-backup-$(date +%Y%m%d-%H%M%S)"
DRY_RUN=0
SELECTED=()

die() { printf "error: %s\n" "$*" >&2; exit 1; }
note() { printf "  %-22s %s\n" "$1" "$2"; }

all_groups() { sed -nE "s/^([a-z]+):.*/\1/p" "$MANIFEST" | sort -u; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n) DRY_RUN=1 ;;
    --list) all_groups; exit 0 ;;
    -h|--help) sed -n "2,12p" "$0" | sed "s/^# \?//"; exit 0 ;;
    --*) die "unknown flag: $1" ;;
    *) SELECTED+=("$1") ;;
  esac
  shift
done

[[ -f "$MANIFEST" ]] || die "manifest not found: $MANIFEST"

if [[ ${#SELECTED[@]} -gt 0 ]]; then
  for g in "${SELECTED[@]}"; do
    all_groups | grep -qx "$g" || die "unknown group: $g (see --list)"
  done
fi

wanted() {
  [[ ${#SELECTED[@]} -eq 0 ]] && return 0
  local g
  for g in "${SELECTED[@]}"; do [[ "$g" == "$1" ]] && return 0; done
  return 1
}

if (( DRY_RUN )); then echo "DRY RUN — nothing will be changed."; fi
echo "Repo:   $REPO"
echo "Backup: $BACKUP"
echo

linked=0 skipped=0 backed_up=0 missing=0

while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
  group="${line%%:*}"
  rel="${line#*:}"
  wanted "$group" || continue

  src="${REPO}/home/${rel}"
  dest="${HOME}/${rel}"

  if [[ ! -e "$src" ]]; then
    note "not in repo" "$rel"; missing=$(( missing + 1 )); continue
  fi

  # Already ours? Leave it. This is what makes reruns safe.
  if [[ -L "$dest" ]] && [[ "$(readlink -f "$dest")" == "$(readlink -f "$src")" ]]; then
    skipped=$(( skipped + 1 )); continue
  fi

  if (( DRY_RUN )); then
    if [[ -e "$dest" || -L "$dest" ]]; then
      note "would back up + link" "$rel"
    else
      note "would link" "$rel"
    fi
    linked=$(( linked + 1 )); continue
  fi

  # Move whatever is there out of the way, keeping its path shape so the
  # backup directory mirrors $HOME and you can copy pieces back by hand.
  if [[ -e "$dest" || -L "$dest" ]]; then
    mkdir -p "${BACKUP}/$(dirname "$rel")"
    mv "$dest" "${BACKUP}/${rel}"
    backed_up=$(( backed_up + 1 ))
  fi

  mkdir -p "$(dirname "$dest")"
  ln -s "$src" "$dest"
  note "linked" "$rel"
  linked=$(( linked + 1 ))
done < "$MANIFEST"

echo
echo "linked=$linked  already-ok=$skipped  backed-up=$backed_up  not-in-repo=$missing"
if (( backed_up > 0 )); then
  echo "Replaced files are in $BACKUP"
fi
if (( DRY_RUN == 0 )) && [[ -d "${REPO}/home/.config/systemd/user" ]]; then
  echo
  echo "Reloading user systemd units..."
  systemctl --user daemon-reload || true
fi
