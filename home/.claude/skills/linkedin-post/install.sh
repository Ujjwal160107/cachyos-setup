#!/usr/bin/env sh
# Install the linkedin-post skill for Claude Code.
#
#   Global (every repo):
#     curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh
#
#   This workspace only:
#     curl -fsSL https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.sh | sh -s -- --local
set -e

REPO_URL="https://github.com/Ujjwal160107/linkedin-post-skill.git"
SKILL_NAME="linkedin-post"
SCOPE="global"

for arg in "$@"; do
  case "$arg" in
    --global) SCOPE="global" ;;
    --local)  SCOPE="local" ;;
    -h|--help)
      echo "usage: install.sh [--global|--local]"
      echo "  --global  install to \$HOME/.claude/skills (default)"
      echo "  --local   install to ./.claude/skills in the current directory"
      exit 0
      ;;
    *)
      echo "install: unknown option '$arg' (try --help)" >&2
      exit 2
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "install: git is required but was not found on PATH" >&2
  exit 1
fi

if [ "$SCOPE" = "local" ]; then
  SKILLS_DIR="$(pwd)/.claude/skills"
else
  SKILLS_DIR="$HOME/.claude/skills"
fi
TARGET="$SKILLS_DIR/$SKILL_NAME"

mkdir -p "$SKILLS_DIR"

if [ -d "$TARGET/.git" ]; then
  echo "install: updating existing install at $TARGET"
  git -C "$TARGET" pull --ff-only --quiet
elif [ -e "$TARGET" ]; then
  echo "install: $TARGET already exists and is not a git clone." >&2
  echo "install: move or delete it, then re-run." >&2
  exit 1
else
  echo "install: cloning into $TARGET"
  git clone --depth 1 --quiet "$REPO_URL" "$TARGET"
fi

echo ""
echo "Installed $SKILL_NAME to $TARGET"
if [ "$SCOPE" = "local" ]; then
  echo "Scope: this workspace only."
else
  echo "Scope: global. Available in every repo."
fi
echo ""
echo "Use it by running /$SKILL_NAME inside any git repository."
echo ""
echo "Optional companion, improves the writing pass:"
echo "  git clone https://github.com/blader/humanizer.git \"$SKILLS_DIR/humanizer\""
