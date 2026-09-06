import json
import os
import glob
from collections import defaultdict

CLAUDE_DIR = os.path.expanduser("~/.claude/projects")

PRICING = {
    "opus": {"input": 15, "output": 75, "cache_write": 18.75, "cache_read": 1.50},
    "sonnet": {"input": 3, "output": 15, "cache_write": 3.75, "cache_read": 0.30},
    "haiku": {"input": 0.80, "output": 4, "cache_write": 1.0, "cache_read": 0.08},
}

def get_model_tier(model_name):
    if not model_name:
        return "sonnet"
    model_lower = model_name.lower()
    if "opus" in model_lower:
        return "opus"
    elif "haiku" in model_lower:
        return "haiku"
    else:
        return "sonnet"

def get_project_name(slug):
    mapping = {
        "C--Users-ujjwa": "~ (home)",
        "C--Users-ujjwa-OneDrive-Desktop": "Desktop",
        "c--Users-ujjwa-OneDrive-Desktop-Casino-": "Casino-",
        "c--Users-ujjwa-OneDrive-Desktop-cruitical": "cruitical",
        "c--Users-ujjwa-OneDrive-Desktop-cruitical-landing-page": "cruitical-landing-page",
        "c--Users-ujjwa-OneDrive-Desktop-elevenlabs-coffee-chat": "elevenlabs-coffee-chat",
        "c--Users-ujjwa-OneDrive-Desktop-elevenlabs-coffee-chat-context": "elevenlabs-coffee-chat-context",
        "c--Users-ujjwa-OneDrive-Desktop-kb": "kb",
    }
    if slug in mapping:
        return mapping[slug]
    parts = slug.replace("c--", "").replace("C--", "").split("-")
    return parts[-1] if parts else slug

def format_tokens(count):
    if count >= 1_000_000:
        return f"{count/1_000_000:.2f}M"
    elif count >= 1_000:
        return f"{count/1_000:.1f}K"
    else:
        return str(count)

all_files = glob.glob(os.path.join(CLAUDE_DIR, "**", "*.jsonl"), recursive=True)

projects = defaultdict(lambda: {
    "sessions": set(),
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_write_tokens": 0,
    "cache_read_tokens": 0,
    "cost": 0.0,
    "by_model": defaultdict(lambda: {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost": 0.0}),
    "api_calls": 0,
})

seen_messages = defaultdict(set)

for filepath in all_files:
    rel_path = os.path.relpath(filepath, CLAUDE_DIR)
    parts = rel_path.replace("\\", "/").split("/")
    project_slug = parts[0]
    project_name = get_project_name(project_slug)

    session_file = os.path.basename(filepath)
    session_id = session_file.replace(".jsonl", "")
    projects[project_name]["sessions"].add(session_id)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if data.get("type") != "assistant":
                    continue

                msg = data.get("message", {})
                usage = msg.get("usage")
                if not usage:
                    continue

                msg_id = msg.get("id", "")
                uuid = data.get("uuid", "")
                dedup_key = f"{msg_id}_{uuid}"
                if dedup_key in seen_messages[project_name]:
                    continue
                seen_messages[project_name].add(dedup_key)

                model = msg.get("model", "")
                tier = get_model_tier(model)
                pricing = PRICING[tier]

                input_t = usage.get("input_tokens", 0) or 0
                output_t = usage.get("output_tokens", 0) or 0
                cache_write_t = usage.get("cache_creation_input_tokens", 0) or 0
                cache_read_t = usage.get("cache_read_input_tokens", 0) or 0

                cost = (
                    (input_t / 1_000_000) * pricing["input"] +
                    (output_t / 1_000_000) * pricing["output"] +
                    (cache_write_t / 1_000_000) * pricing["cache_write"] +
                    (cache_read_t / 1_000_000) * pricing["cache_read"]
                )

                projects[project_name]["input_tokens"] += input_t
                projects[project_name]["output_tokens"] += output_t
                projects[project_name]["cache_write_tokens"] += cache_write_t
                projects[project_name]["cache_read_tokens"] += cache_read_t
                projects[project_name]["cost"] += cost
                projects[project_name]["api_calls"] += 1

                projects[project_name]["by_model"][tier]["input"] += input_t
                projects[project_name]["by_model"][tier]["output"] += output_t
                projects[project_name]["by_model"][tier]["cache_write"] += cache_write_t
                projects[project_name]["by_model"][tier]["cache_read"] += cache_read_t
                projects[project_name]["by_model"][tier]["cost"] += cost
    except Exception as e:
        pass

print()
print("+" + "=" * 74 + "+")
print("|" + "CLAUDE CODE - TOTAL USAGE REPORT".center(74) + "|")
print("+" + "=" * 74 + "+")
print()

total_sessions = 0
total_input = 0
total_output = 0
total_cache_write = 0
total_cache_read = 0
total_cost = 0.0
total_calls = 0
global_by_model = defaultdict(lambda: {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "cost": 0.0})

sorted_projects = sorted(projects.items(), key=lambda x: x[1]["cost"], reverse=True)

for name, data in sorted_projects:
    if data["api_calls"] == 0:
        continue

    sessions = len(data["sessions"])
    total_sessions += sessions
    total_input += data["input_tokens"]
    total_output += data["output_tokens"]
    total_cache_write += data["cache_write_tokens"]
    total_cache_read += data["cache_read_tokens"]
    total_cost += data["cost"]
    total_calls += data["api_calls"]

    for tier, mdata in data["by_model"].items():
        global_by_model[tier]["input"] += mdata["input"]
        global_by_model[tier]["output"] += mdata["output"]
        global_by_model[tier]["cache_write"] += mdata["cache_write"]
        global_by_model[tier]["cache_read"] += mdata["cache_read"]
        global_by_model[tier]["cost"] += mdata["cost"]

    print(f"  Project: {name}")
    print(f"     Sessions: {sessions} | API Calls: {data['api_calls']:,}")
    print(f"     Input: {format_tokens(data['input_tokens'])} | Output: {format_tokens(data['output_tokens'])} | Cache Write: {format_tokens(data['cache_write_tokens'])} | Cache Read: {format_tokens(data['cache_read_tokens'])}")
    print(f"     Estimated Cost: ${data['cost']:.2f}")
    print()

print("+" + "-" * 74 + "+")
print("|" + "TOTALS".center(74) + "|")
print("+" + "-" * 74 + "+")
print()
print(f"     Total Sessions: {total_sessions}")
print(f"     Total API Calls: {total_calls:,}")
print(f"     Total Input Tokens: {format_tokens(total_input)}")
print(f"     Total Output Tokens: {format_tokens(total_output)}")
print(f"     Total Cache Write Tokens: {format_tokens(total_cache_write)}")
print(f"     Total Cache Read Tokens: {format_tokens(total_cache_read)}")
print(f"     -------------------------------------------")
print(f"     TOTAL ESTIMATED COST: ${total_cost:.2f}")
print()
print("+" + "-" * 74 + "+")
print("|" + "BY MODEL".center(74) + "|")
print("+" + "-" * 74 + "+")
print()

for tier in ["opus", "sonnet", "haiku"]:
    if tier in global_by_model and global_by_model[tier]["cost"] > 0:
        m = global_by_model[tier]
        print(f"     {tier.capitalize()}")
        print(f"        Input: {format_tokens(m['input'])} | Output: {format_tokens(m['output'])} | Cache Write: {format_tokens(m['cache_write'])} | Cache Read: {format_tokens(m['cache_read'])}")
        print(f"        Cost: ${m['cost']:.2f}")
        print()

print("+" + "=" * 74 + "+")
