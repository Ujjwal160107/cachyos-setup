---
name: total-usage
version: 1.0.0
description: |
  Show total Claude API token usage and estimated cost across all projects/repos.
  Parses session JSONL files from ~/.claude/projects to aggregate input/output tokens,
  cache tokens, and calculates USD cost per project and overall.
license: MIT
allowed-tools:
  - Bash
  - Read
  - Glob
---

# Total Usage: Claude API Token & Cost Report

You are a usage analytics tool. When invoked, parse all Claude Code session data and produce a comprehensive report of token usage and estimated costs broken down by project/repo.

## Instructions

1. Find all `.jsonl` session files under `~/.claude/projects/` (including subagent files in `subagents/` subdirectories).

2. For each file, read lines and extract token usage from assistant messages. The relevant fields are in `message.usage`:
   - `input_tokens` — standard input tokens
   - `output_tokens` — output tokens  
   - `cache_creation_input_tokens` — tokens written to cache
   - `cache_read_input_tokens` — tokens read from cache

3. Group usage by project. The project is determined by the directory structure:
   - `~/.claude/projects/{project-slug}/{session-id}.jsonl`
   - `~/.claude/projects/{project-slug}/{session-id}/subagents/*.jsonl`
   
   Map project slugs back to readable folder names:
   - `c--Users-ujjwa-OneDrive-Desktop-Casino-` → `Casino-`
   - `c--Users-ujjwa-OneDrive-Desktop-cruitical` → `cruitical`
   - `C--Users-ujjwa` → `~ (home)`
   - Extract the last meaningful path segment from the slug

4. Calculate costs using current Claude API pricing (as of May 2025):
   
   **Opus:**
   - Input: $15 / 1M tokens
   - Output: $75 / 1M tokens
   - Cache write: $18.75 / 1M tokens
   - Cache read: $1.50 / 1M tokens

   **Sonnet:**
   - Input: $3 / 1M tokens
   - Output: $15 / 1M tokens
   - Cache write: $3.75 / 1M tokens
   - Cache read: $0.30 / 1M tokens

   **Haiku:**
   - Input: $0.80 / 1M tokens
   - Output: $4 / 1M tokens
   - Cache write: $1 / 1M tokens
   - Cache read: $0.08 / 1M tokens

   Determine the model from `message.model` field. If unknown, default to Sonnet pricing.

5. Use a bash script with python3 to parse the data efficiently. Run a single python script that processes all files at once.

6. Present results in a formatted table:

```
╔══════════════════════════════════════════════════════════════════════╗
║                    CLAUDE CODE - TOTAL USAGE REPORT                  ║
╠══════════════════════════════════════════════════════════════════════╣

📁 Project: Casino-
   Sessions: X | Input: XX.XM | Output: XX.XM | Cache Write: XX.XM | Cache Read: XX.XM
   Estimated Cost: $XX.XX

📁 Project: cruitical  
   Sessions: X | Input: XX.XM | Output: XX.XM | Cache Write: XX.XM | Cache Read: XX.XM
   Estimated Cost: $XX.XX

... (repeat for each project)

╠══════════════════════════════════════════════════════════════════════╣
║ TOTALS                                                               ║
╠══════════════════════════════════════════════════════════════════════╣
   Total Sessions: XX
   Total Input Tokens: XX.XM
   Total Output Tokens: XX.XM  
   Total Cache Write Tokens: XX.XM
   Total Cache Read Tokens: XX.XM
   ─────────────────────────────────
   💰 Total Estimated Cost: $XX.XX
╚══════════════════════════════════════════════════════════════════════╝
```

7. Also show a breakdown by model (Opus vs Sonnet vs Haiku) at the end.

## Important Notes

- Token counts in the JSONL can appear multiple times for the same message (split across content blocks). Each line in the JSONL with a `message.usage` represents one API call's usage — count each once.
- Some lines may have `input_tokens: 3` which are continuation messages (content block splits) — still count them as they represent real API calls.
- If no usage data is found for a project, skip it in the output.
- Format large numbers with commas for readability.
- Show token counts in millions (M) if > 1M, thousands (K) if > 1K.
