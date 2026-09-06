<#
.SYNOPSIS
  Install the linkedin-post skill for Claude Code.

.EXAMPLE
  # Global (every repo)
  irm https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.ps1 | iex

.EXAMPLE
  # This workspace only
  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Ujjwal160107/linkedin-post-skill/main/install.ps1))) --local
#>
param(
  [ValidateSet('--global', '--local')]
  [string]$Scope = '--global'
)

$ErrorActionPreference = 'Stop'

# Under `powershell -File install.ps1 --local`, PowerShell does not bind
# `--local` to the positional $Scope parameter at all: the argument lands in
# $args and the script would silently run with the default scope, installing
# globally when the user asked for a workspace install. Installing somewhere
# the user did not ask for is worse than refusing, so any unbound argument is
# a hard error naming the offender.
if ($args.Count -gt 0) {
  Write-Error ("install: unrecognized argument(s): {0}. Use --global or --local, e.g. & ([scriptblock]::Create((irm <url>))) --local" -f ($args -join ', '))
  exit 1
}

$RepoUrl = 'https://github.com/Ujjwal160107/linkedin-post-skill.git'
$SkillName = 'linkedin-post'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error 'install: git is required but was not found on PATH'
  exit 1
}

if ($Scope -eq '--local') {
  $SkillsDir = Join-Path (Get-Location) '.claude/skills'
} else {
  $SkillsDir = Join-Path $HOME '.claude/skills'
}
$Target = Join-Path $SkillsDir $SkillName

New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null

if (Test-Path (Join-Path $Target '.git')) {
  Write-Host "install: updating existing install at $Target"
  git -C $Target pull --ff-only --quiet
} elseif (Test-Path $Target) {
  Write-Error "install: $Target already exists and is not a git clone. Move or delete it, then re-run."
  exit 1
} else {
  Write-Host "install: cloning into $Target"
  git clone --depth 1 --quiet $RepoUrl $Target
}

Write-Host ''
Write-Host "Installed $SkillName to $Target"
if ($Scope -eq '--local') {
  Write-Host 'Scope: this workspace only.'
} else {
  Write-Host 'Scope: global. Available in every repo.'
}
Write-Host ''
Write-Host "Use it by running /$SkillName inside any git repository."
Write-Host ''
Write-Host 'Optional companion, improves the writing pass:'
Write-Host "  git clone https://github.com/blader/humanizer.git `"$SkillsDir/humanizer`""
