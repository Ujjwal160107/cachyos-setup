#!/usr/bin/env python3
"""Write workshop-items.md from the Wallpaper Engine Steam Workshop cache.

The wallpapers themselves are ~3 GB of Steam Workshop data and are not in this
repo. This manifest records which items to re-subscribe to; Steam refetches the
content once you subscribe, and the IDs are what make that possible.
"""
import json
import pathlib

WORKSHOP = pathlib.Path.home() / ".local/share/Steam/steamapps/workshop/content/431960"
HERE = pathlib.Path(__file__).parent
URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={}"


def item_title(item_dir):
    try:
        data = json.loads((item_dir / "project.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "(title unavailable)", "unknown"
    return data.get("title", "(untitled)").strip(), data.get("type", "unknown").lower()


def active_ids():
    """IDs currently applied to a monitor, so the rebuild can restore the look."""
    try:
        data = json.loads((HERE / "active-wallpapers.json").read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        pathlib.Path(w["backgroundId"]).name
        for w in data.get("activeWallpapers", {}).values()
        if w.get("backgroundId")
    }


def main():
    if not WORKSHOP.is_dir():
        raise SystemExit(f"Workshop directory not found: {WORKSHOP}")

    active = active_ids()
    items = sorted(
        (d.name, *item_title(d)) for d in WORKSHOP.iterdir() if d.is_dir()
    )

    lines = [
        "# Wallpaper Engine — subscribed Workshop items",
        "",
        f"{len(items)} items. Regenerate with `./generate-manifest.py`.",
        "",
        "Open each link and hit Subscribe; Steam downloads the content into",
        "`~/.local/share/Steam/steamapps/workshop/content/431960/<id>`. Once they are",
        "present, copy `active-wallpapers.json` and `settings.json` from this",
        "directory back into `~/.config/Linux Wallpaper Engine/`.",
        "",
        "A ★ marks a wallpaper that was applied to a monitor when this was captured.",
        "",
        "| | ID | Title | Type |",
        "|---|---|---|---|",
    ]
    for item_id, title, kind in items:
        star = "★" if item_id in active else ""
        safe = title.replace("|", "\\|")
        lines.append(f"| {star} | [{item_id}]({URL.format(item_id)}) | {safe} | {kind} |")

    (HERE / "workshop-items.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote workshop-items.md ({len(items)} items, {len(active)} active)")


if __name__ == "__main__":
    main()
