"""Walk each feed page by page and queue new articles for the summary step.

How far a run walks, per source:
- Until the first run for a source has reached START_DATE (the backfill), every run walks from
  page 1 down to START_DATE. Pages are cheap; nothing is summarized here. A run that fails midway
  simply walks again next time, so no article in the range can be missed.
- After that, a run stops at the first page holding an article this source has already seen.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Callable

from . import config, feeds, store

log = logging.getLogger(__name__)

Fetch = Callable[[config.Source, int], "list[feeds.Item] | None"]

# The only fields a queued article has. No article text is kept (copyright policy of the site).
QUEUE_FIELDS = ("id", "company", "source", "channel", "kind", "lang", "title", "url",
                "published", "date", "categories", "alsoIn", "collectedAt")


def now_kst() -> datetime:
    return datetime.now(feeds.KST)


def _unique_id(wanted: str, key: str, taken: dict[str, str]) -> str:
    nid, n = wanted, 2
    while nid in taken and taken[nid] != key:
        nid, n = f"{wanted}-{n}", n + 1
    return nid


def collect_source(source: config.Source, fetch: Fetch, seen: dict, queue_by_key: dict[str, dict],
                   taken_ids: dict[str, str], now: datetime, sleep: Callable[[float], None] | None) -> dict:
    stats = {"pages": 0, "items": 0, "new": 0, "skippedByCategory": 0, "older": 0,
             "stoppedBy": "", "error": None}
    urls = seen["urls"]
    backfill = seen["backfill"].setdefault(source.key, {"done": False})
    today = now.date().isoformat()

    for page in range(1, config.MAX_PAGES + 1):
        if page > 1 and sleep:
            sleep(config.PAGE_DELAY)
        try:
            items = fetch(source, page)
        except Exception as exc:  # noqa: BLE001 - one broken source must not stop the others
            stats["error"] = f"page {page}: {type(exc).__name__}: {exc}"
            log.warning("%s: %s", source.key, stats["error"])
            return stats
        if not items:
            stats["stoppedBy"] = "end of feed"
            backfill.update(done=True, finishedAt=backfill.get("finishedAt") or today)
            return stats

        stats["pages"] += 1
        known_here = False
        for item in items:
            stats["items"] += 1
            key = item.key
            rec = urls.get(key)
            if rec is not None:
                if source.key in rec.get("sources", []):
                    known_here = True
                    continue
                # The same article is filed under another channel of the same newsroom.
                rec.setdefault("sources", []).append(source.key)
                queued = queue_by_key.get(key)
                if queued is not None and source.key != queued["source"] and source.key not in queued["alsoIn"]:
                    queued["alsoIn"].append(source.key)
                continue

            day = item.published.date()
            if day < config.START_DATE:
                stats["older"] += 1
                continue
            record = {"title": item.title, "date": day.isoformat(), "sources": [source.key], "checkedAt": today}
            kind = feeds.classify(source, item.categories)
            if kind is None:
                urls[key] = {**record, "status": "skipped", "reason": "category"}
                stats["skippedByCategory"] += 1
                continue
            channel, kind_name = kind
            nid = _unique_id(feeds.make_id(item.company, item.url), key, taken_ids)
            taken_ids[nid] = key
            queue_by_key[key] = {
                "id": nid, "company": item.company, "source": source.key, "channel": channel,
                "kind": kind_name, "lang": item.lang, "title": item.title, "url": item.url,
                "published": item.published.isoformat(), "date": day.isoformat(),
                "categories": item.categories, "alsoIn": [], "collectedAt": now.isoformat(timespec="seconds"),
            }
            urls[key] = {**record, "id": nid, "status": "queued"}
            stats["new"] += 1

        if min(i.published.date() for i in items) < config.START_DATE:
            stats["stoppedBy"] = f"reached {config.START_DATE.isoformat()}"
            backfill.update(done=True, finishedAt=backfill.get("finishedAt") or today)
            return stats
        if known_here and backfill.get("done"):
            stats["stoppedBy"] = "reached known articles"
            return stats

    stats["stoppedBy"] = f"page limit ({config.MAX_PAGES})"
    return stats


def run(*, dry_run: bool = False, fetch: Fetch = feeds.fetch_page, sources=config.SOURCES,
        sleep: Callable[[float], None] | None = time.sleep, now: datetime | None = None,
        save_report: bool = True) -> dict:
    """Collect every source once. With dry_run, nothing is written. With save_report=False the caller
    stores the report (the update command adds the summary step's report first)."""
    now = now or now_kst()
    seen = store.load_seen()
    queue = store.load_queue()
    queue_by_key = {feeds.normalize_url(i["url"]): i for i in queue["items"]}
    before = set(queue_by_key)
    taken_ids = {rec["id"]: key for key, rec in seen["urls"].items() if rec.get("id")}
    taken_ids.update({i["id"]: k for k, i in queue_by_key.items()})

    report = {"startedAt": now.isoformat(timespec="seconds"), "dryRun": dry_run,
              "startDate": config.START_DATE.isoformat(), "sources": {}, "errors": {}, "added": []}
    for source in sources:
        stats = collect_source(source, fetch, seen, queue_by_key, taken_ids, now, sleep)
        report["sources"][source.key] = stats
        if stats["error"]:
            report["errors"][source.key] = stats["error"]

    added = sorted((i for k, i in queue_by_key.items() if k not in before),
                   key=lambda i: i["published"], reverse=True)
    report["added"] = [{"id": i["id"], "date": i["date"], "source": i["source"], "title": i["title"]} for i in added]
    queue["items"] = list(queue_by_key.values())
    report["queueSize"] = len(queue["items"])
    report["backfillDone"] = {s.key: bool(seen["backfill"].get(s.key, {}).get("done")) for s in sources}
    report["finishedAt"] = now_kst().isoformat(timespec="seconds")

    if not dry_run:
        if added:
            queue["updatedAt"] = now.isoformat(timespec="seconds")
        store.save_seen(seen)
        store.save_queue(queue)
        if save_report:
            store.save_report(report)
    return report


def selftest(fetch: Fetch = feeds.fetch_page, sources=config.SOURCES, notice: bool = False) -> bool:
    """Read page 1 of every source and check it still parses into dated articles that carry their
    text (the summary step reads it from the feed). Writes nothing. With notice, each result is also
    printed as a GitHub Actions notice so it shows on the run's summary page."""
    ok = True
    for source in sources:
        try:
            items = fetch(source, 1)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {source.key}: {type(exc).__name__}: {exc}")
            ok = False
            continue
        if not items:
            print(f"FAIL {source.key}: page 1 has no articles")
            ok = False
            continue
        kept = [i for i in items if feeds.classify(source, i.categories) is not None]
        newest = max(i.published for i in items)
        lengths = [len(feeds.html_to_text(i.body)) for i in kept]
        with_text = sum(1 for n in lengths if n >= config.MIN_BODY_CHARS)
        authors = sorted({i.author or "(없음)" for i in kept})
        line = (f"{source.key}: {len(items)} articles on page 1, {len(kept)} kept by category rules, "
                f"newest {newest.date().isoformat()}, text in feed {with_text}/{len(kept)} "
                f"(median {sorted(lengths)[len(lengths) // 2] if lengths else 0} chars), authors {', '.join(authors)}")
        print(("OK   " if with_text else "WARN ") + line)
        if notice:
            print(f"::notice title=출처 점검 {source.key}::{line}")
    return ok
