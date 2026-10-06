"""Load and save the collector's state files (backend/state/*.json)."""
from __future__ import annotations

import json
from pathlib import Path

from . import config

SEEN_LIMIT = 5000  # records kept in seen.json; far more than a year of articles


def _read(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _write(path: Path, data, *, sort_keys: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_seen() -> dict:
    """{"urls": {normalized url: record}, "backfill": {source key: {"done": bool, ...}}}"""
    seen = _read(config.SEEN_FILE, {})
    seen.setdefault("urls", {})
    seen.setdefault("backfill", {})
    return seen


def save_seen(seen: dict) -> None:
    urls = seen.get("urls", {})
    if len(urls) > SEEN_LIMIT:
        keep = sorted(urls.items(), key=lambda kv: kv[1].get("date") or "", reverse=True)[:SEEN_LIMIT]
        seen["urls"] = dict(keep)
    _write(config.SEEN_FILE, seen, sort_keys=True)


def load_queue() -> dict:
    queue = _read(config.QUEUE_FILE, {})
    queue.setdefault("items", [])
    return queue


def save_queue(queue: dict) -> None:
    queue["items"].sort(key=lambda i: (i["published"], i["id"]), reverse=True)
    _write(config.QUEUE_FILE, queue)


def save_report(report: dict) -> None:
    _write(config.REPORT_FILE, report)
