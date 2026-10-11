"""Summary step: turn queued articles into Korean cards (data/news/<id>.json).

Per run, at most SUMMARY_LIMIT queued articles are taken, newest first. For each one:
1. Find the article text (RSS feed first, then the article page). The text stays in memory.
2. Ask Claude for the card: Korean title (English articles), two-sentence summary, one line for
   interviews, 1-4 standard tags, companies mentioned.
3. Check every number with a unit against the article. If one cannot be found, ask Claude once more
   with the list; if a number is still unsupported, drop the sentence that holds it.
4. Save the card and mark the article summarized. Failed articles stay queued and are retried on
   the next run, up to MAX_ATTEMPTS runs; then they are given up and recorded in seen.json.

An authentication error or a usage limit stops the run; nothing is counted against the articles.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Callable

from . import bodies, collect, config, feeds, guard, store, summarize, tags

log = logging.getLogger(__name__)

MAX_COMPANIES = 6
HANGUL = re.compile(r"[가-힣]")
# Claude sometimes leaves company names in English. Folded (lower case) name -> Korean name.
COMPANY_NAMES = {
    "sk hynix": "SK하이닉스", "samsung electronics": "삼성전자", "samsung": "삼성전자", "nvidia": "엔비디아",
    "openai": "오픈AI", "anthropic": "앤트로픽", "google": "구글", "meta": "메타", "microsoft": "마이크로소프트",
    "amazon": "아마존", "apple": "애플", "intel": "인텔", "micron": "마이크론", "solidigm": "솔리다임",
    "qualcomm": "퀄컴", "broadcom": "브로드컴", "cadence": "케이던스", "synopsys": "시놉시스",
    "dell technologies": "델 테크놀로지스", "dell": "델", "mistral ai": "미스트랄 AI", "kioxia": "키옥시아",
    "western digital": "웨스턴디지털", "sandisk": "샌디스크", "applied materials": "어플라이드 머티어리얼즈",
    "lam research": "램리서치", "tokyo electron": "도쿄일렉트론", "hanmi semiconductor": "한미반도체",
}


def company_name(name: str) -> str:
    name = _text(name)
    return COMPANY_NAMES.get(name.lower(), name)


class CardError(Exception):
    """Claude's card cannot be used as it is (the article is retried on the next run)."""


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sentences(value) -> list[str]:
    """The summary as a list of sentences, at most 2. Splits an element that holds two sentences."""
    parts = value if isinstance(value, list) else [value]
    out = []
    for part in parts:
        for s in re.split(r"(?<=[다요]\.)\s+", _text(part)):
            if s:
                out.append(s)
    return out[:2]


def clean_card(raw: dict, item: dict, book: tags.TagBook) -> tuple[dict, list[str]]:
    """(card fields, tag strings that are not standard tags)."""
    title = item["title"] if item["lang"] == "ko" else _text(raw.get("title")).rstrip(".")
    kept, unknown = book.normalize(raw.get("tags") or [])
    companies = []
    for c in raw.get("companies") or []:
        c = company_name(c)
        if c and c not in companies:
            companies.append(c)
    return {
        "title": title,
        "summary": sentences(raw.get("summary")),
        "interview": _text(raw.get("interview")),
        "tags": kept,
        "companies": companies[:MAX_COMPANIES],
    }, unknown


def number_problems(card: dict, item: dict, source_text: str) -> list[str]:
    """Numbers in the card that the article does not support (title only for translated titles)."""
    fields = [*card["summary"], card["interview"]]
    if item["lang"] != "ko":
        fields.insert(0, card["title"])
    bad = []
    for text in fields:
        for n in guard.unsupported(text, source_text):
            if n not in bad:
                bad.append(n)
    return bad


def make_card(llm, item: dict, body: bodies.Body, book: tags.TagBook) -> tuple[dict, dict]:
    """(card fields, checks) for one article. Raises CardError, summarize.AuthError, summarize.LimitError."""
    source_text = item["title"] + "\n" + body.text
    raw = summarize.write_card(llm, item, body.text, body.author, book)
    card, unknown = clean_card(raw, item, book)
    bad = number_problems(card, item, source_text)
    checks: dict = {}
    if bad:
        checks["retriedFor"] = bad
        raw2 = summarize.write_card(llm, item, body.text, body.author, book, fix=(raw, bad))
        card2, unknown2 = clean_card(raw2, item, book)
        bad2 = number_problems(card2, item, source_text)
        if len(card2["summary"]) and len(bad2) <= len(bad):
            card, unknown, bad = card2, unknown2, bad2

    if item["lang"] != "ko":
        if not card["title"] or not HANGUL.search(card["title"]):
            raise CardError(f"번역 제목이 비었거나 한국어가 아님: {card['title']!r}")
        wrong = guard.unsupported(card["title"], source_text)
        if wrong:
            raise CardError(f"제목의 수치를 원문에서 찾지 못함: {', '.join(wrong)}")
    if bad:
        removed = [s for s in card["summary"] if guard.unsupported(s, source_text)]
        card["summary"] = [s for s in card["summary"] if s not in removed]
        if card["interview"] and guard.unsupported(card["interview"], source_text):
            removed.append(card["interview"])
            card["interview"] = ""
        checks["removed"] = removed
    if not card["summary"]:
        raise CardError("쓸 수 있는 요약 문장이 없음")
    if unknown:
        checks["unknownTags"] = unknown
    return card, checks


def article_record(item: dict, card: dict, checks: dict, body: bodies.Body, now: datetime) -> dict:
    record = {
        "id": item["id"], "company": item["company"], "source": item["source"], "channel": item["channel"],
        "kind": item["kind"], "lang": item["lang"], "title": card["title"],
    }
    if item["lang"] != "ko":
        record["originalTitle"] = item["title"]
    record.update({
        "url": item["url"], "published": item["published"], "date": item["date"],
        "summary": card["summary"], "interview": card["interview"], "tags": card["tags"],
        "companies": card["companies"],
    })
    if body.author and not config.is_company_author(body.author):
        record["author"] = body.author
    record.update({
        "categories": item.get("categories", []), "alsoIn": item.get("alsoIn", []),
        "summarizedAt": now.isoformat(timespec="seconds"), "model": config.SUMMARY_MODEL,
        "rules": summarize.RULES_VERSION, "bodyVia": body.via,
    })
    if checks:
        record["checks"] = checks
    return record


def news_path(article_id: str):
    return config.NEWS_DIR / f"{article_id}.json"


def write_article(record: dict) -> None:
    store._write(news_path(record["id"]), record)


def run(*, llm=None, finder: bodies.BodyFinder | None = None, limit: int | None = None,
        now: datetime | None = None, clock: Callable[[], float] = time.monotonic) -> dict:
    """Summarize up to `limit` queued articles. Returns the run report (also stored by the caller)."""
    now = now or collect.now_kst()
    limit = config.SUMMARY_LIMIT if limit is None else limit
    report = {"startedAt": now.isoformat(timespec="seconds"), "backend": None, "model": config.SUMMARY_MODEL,
              "limit": limit, "summarized": [], "failed": {}, "gaveUp": [], "authError": False,
              "limitHit": False, "stoppedBy": "", "queueLeft": 0}
    seen = store.load_seen()
    queue = store.load_queue()
    report["queueLeft"] = len(queue["items"])
    if not queue["items"] or limit <= 0:
        report["stoppedBy"] = "nothing to do"
        return report
    if llm is None:
        report["backend"] = summarize.llm_available()
        if report["backend"] is None:
            report["stoppedBy"] = "no credentials"
            return report
        llm = summarize.make_llm()
    else:
        report["backend"] = type(llm).__name__
    finder = finder or bodies.BodyFinder()
    book = tags.tagbook()
    started = clock()
    done: set[str] = set()

    def finish(item: dict, status: str, **extra) -> None:
        rec = seen["urls"].setdefault(feeds.normalize_url(item["url"]), {
            "title": item["title"], "date": item["date"], "sources": [item["source"], *item.get("alsoIn", [])],
            "id": item["id"]})
        rec.update(status=status, **extra)
        done.add(item["id"])

    def fail(item: dict, reason: str) -> None:
        reason = reason[:300]
        item["attempts"] = item.get("attempts", 0) + 1
        item["lastError"] = reason
        report["failed"][item["id"]] = reason
        log.warning("%s: %s (attempt %d)", item["id"], reason, item["attempts"])
        if item["attempts"] >= config.MAX_ATTEMPTS:
            finish(item, "failed", reason=reason)
            report["gaveUp"].append({"id": item["id"], "title": item["title"], "reason": reason})

    todo = sorted(queue["items"], key=lambda i: (i["published"], i["id"]), reverse=True)[:limit]
    try:
        for item in todo:
            if clock() - started > config.SUMMARY_TIME_BUDGET:
                report["stoppedBy"] = "time budget"
                break
            if news_path(item["id"]).exists():  # written by an earlier run that stopped before saving state
                finish(item, "summarized")
                continue
            body = finder.find(item)
            if body is None:
                fail(item, "본문을 찾지 못함(피드와 기사 페이지 모두)")
                continue
            try:
                card, checks = make_card(llm, item, body, book)
            except summarize.AuthError as exc:
                report.update(authError=True, stoppedBy="auth error", message=str(exc)[:300])
                break
            except summarize.LimitError as exc:
                report.update(limitHit=True, stoppedBy="usage limit", message=str(exc)[:300])
                break
            except Exception as exc:  # noqa: BLE001 - CardError, bad JSON, CLI failure: retry next run
                fail(item, str(exc) if isinstance(exc, CardError) else f"{type(exc).__name__}: {exc}")
                continue
            write_article(article_record(item, card, checks, body, now))
            finish(item, "summarized")
            report["summarized"].append({"id": item["id"], "title": card["title"]})
            log.info("summarized %s: %s", item["id"], card["title"])
        else:
            report["stoppedBy"] = "limit" if len(todo) == limit else "queue done"
    finally:
        queue["items"] = [i for i in queue["items"] if i["id"] not in done]
        report["queueLeft"] = len(queue["items"])
        if report["summarized"]:
            queue["updatedAt"] = now.isoformat(timespec="seconds")
        store.save_seen(seen)
        store.save_queue(queue)
    report["finishedAt"] = collect.now_kst().isoformat(timespec="seconds")
    return report


def requeue(ids: list[str] | None = None, *, outdated: bool = False, now: datetime | None = None) -> list[str]:
    """Put summarized articles back in the queue so the next run writes their cards again (after the
    rules changed). ids=None with outdated=False means every card. Their card files are deleted."""
    now = now or collect.now_kst()
    seen = store.load_seen()
    queue = store.load_queue()
    queued = {i["id"] for i in queue["items"]}
    moved = []
    for path in sorted(config.NEWS_DIR.glob("*.json")) if config.NEWS_DIR.exists() else []:
        a = json.loads(path.read_text(encoding="utf-8"))
        if ids is not None and a["id"] not in ids:
            continue
        if outdated and a.get("rules") == summarize.RULES_VERSION:
            continue
        if a["id"] not in queued:
            queue["items"].append({
                "id": a["id"], "company": a["company"], "source": a["source"], "channel": a["channel"],
                "kind": a["kind"], "lang": a["lang"], "title": a.get("originalTitle") or a["title"],
                "url": a["url"], "published": a["published"], "date": a["date"],
                "categories": a.get("categories", []), "alsoIn": a.get("alsoIn", []),
                "collectedAt": now.isoformat(timespec="seconds"),
            })
        rec = seen["urls"].get(feeds.normalize_url(a["url"]))
        if rec is not None:
            rec["status"] = "queued"
            rec.pop("reason", None)
        path.unlink()
        moved.append(a["id"])
    if moved:
        queue["updatedAt"] = now.isoformat(timespec="seconds")
        store.save_seen(seen)
        store.save_queue(queue)
    return moved
