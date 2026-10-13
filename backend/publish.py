"""Build data/manifest.json (everything the site needs in one file) and check the data files.

data/news/<id>.json is the source of truth for each card. The manifest copies the fields the site
shows and adds each card's related theory units, worked out from the tags at build time so that a
change in data/units.json reaches every card without summarizing again.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from . import collect, config, store, tags

# a card text that is really a list written out as text, e.g. '["문장"][0]'
LIST_TEXT = re.compile(r"^\s*\[\s*\".*\"\s*\]\s*(?:\[\s*\d+\s*\])?\s*$", re.S)

CARD_FIELDS = ("id", "company", "source", "channel", "kind", "lang", "title", "originalTitle", "url",
               "published", "date", "summary", "interview", "tags", "companies", "author", "alsoIn")
REQUIRED = ("id", "company", "source", "channel", "kind", "lang", "title", "url", "published", "date",
            "summary", "interview", "tags", "companies")


def load_articles() -> list[dict]:
    if not config.NEWS_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(config.NEWS_DIR.glob("*.json"))]


def _version(path) -> str:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("version", "")
    except FileNotFoundError:
        return ""


def manifest_data(articles: list[dict]) -> dict:
    unit_index = tags.units()
    items = []
    for a in sorted(articles, key=lambda a: (a["published"], a["id"]), reverse=True):
        card = {k: a[k] for k in CARD_FIELDS if k in a}
        card["relatedUnits"] = tags.related_units(a.get("tags", []), unit_index)
        items.append(card)
    return {
        "count": len(items),
        "tagsVersion": _version(config.TAGS_FILE),
        "unitsVersion": _version(config.UNITS_FILE),
        "kinds": config.KIND_LABELS,
        "sources": [{"key": s.key, "name": s.name, "company": s.company, "lang": s.lang, "page": s.page,
                     "channels": [s.channel] if s.channel else sorted({c[1] for c in s.categories})}
                    for s in config.SOURCES],
        "linkOnly": [{"name": name, "url": url} for name, url in config.LINK_ONLY],
        "items": items,
    }


def build(now: datetime | None = None) -> dict:
    """Rewrite the manifest when its content changed. Returns {"count", "changed"}."""
    data = manifest_data(load_articles())
    old = None
    if config.MANIFEST.exists():
        old = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
        old.pop("generatedAt", None)
    changed = old != data
    if changed:
        stamp = (now or collect.now_kst()).isoformat(timespec="seconds")
        store._write(config.MANIFEST, {"generatedAt": stamp, **data})
    return {"count": data["count"], "changed": changed}


def _is_iso_datetime(value: str) -> bool:
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except (TypeError, ValueError):
        return False


def check_article(a: dict, book: tags.TagBook, stem: str) -> list[str]:
    out = []
    missing = [k for k in REQUIRED if k not in a]
    if missing:
        return [f"필드 없음: {', '.join(missing)}"]
    if a["id"] != stem:
        out.append(f"파일 이름과 id가 다름({a['id']})")
    if a["company"] not in ("skhynix", "samsung"):
        out.append(f"company 값이 이상함: {a['company']}")
    if a["source"] not in config.SOURCE_BY_KEY:
        out.append(f"모르는 출처: {a['source']}")
    if a["kind"] not in config.KIND_LABELS:
        out.append(f"모르는 kind: {a['kind']}")
    if a["lang"] not in ("ko", "en"):
        out.append(f"lang 값이 이상함: {a['lang']}")
    if a["lang"] == "en" and not a.get("originalTitle"):
        out.append("영문 기사인데 originalTitle 없음")
    if not str(a["title"]).strip():
        out.append("제목이 비었음")
    if not str(a["url"]).startswith("https://"):
        out.append(f"주소가 https가 아님: {a['url']}")
    if not _is_iso_datetime(a["published"]):
        out.append(f"published 형식이 이상함: {a['published']}")
    elif a["date"] != a["published"][:10]:
        out.append(f"date와 published가 다름: {a['date']}")
    try:
        if date.fromisoformat(a["date"]) < config.START_DATE:
            out.append(f"수집 시작일 이전 기사: {a['date']}")
    except ValueError:
        out.append(f"date 형식이 이상함: {a['date']}")
    s = a["summary"]
    if not isinstance(s, list) or not 1 <= len(s) <= 2 or not all(isinstance(x, str) and x.strip() for x in s):
        out.append("summary는 문장 1~2개의 배열이어야 함")
    if not isinstance(a["interview"], str):
        out.append("interview는 문자열이어야 함")
    for field in ("title", "interview"):
        if isinstance(a.get(field), str) and LIST_TEXT.match(a[field]):
            out.append(f"{field}가 배열을 글자로 적은 모양: {a[field][:40]}")
    if isinstance(s, list) and any(isinstance(x, str) and LIST_TEXT.match(x) for x in s):
        out.append("summary 문장이 배열을 글자로 적은 모양")
    if not isinstance(a["tags"], list) or len(a["tags"]) > tags.MAX_TAGS:
        out.append("tags는 4개 이하의 배열이어야 함")
    else:
        wrong = [t for t in a["tags"] if t not in book.names]
        if wrong:
            out.append(f"표준 태그가 아님: {', '.join(wrong)}")
    if not isinstance(a["companies"], list):
        out.append("companies는 배열이어야 함")
    return out


def validate() -> list[str]:
    """Problems in data/ (empty list = all good)."""
    problems = []
    book = tags.tagbook()
    if len(set(book.names)) != len(book.names):
        problems.append("tags.json: 같은 이름의 태그가 두 번 있음")
    codes = set()
    for u in tags.units():
        if u["code"] in codes:
            problems.append(f"units.json: 단원 코드 중복 {u['code']}")
        codes.add(u["code"])
        wrong = [t for t in u["tags"] if t not in book.names]
        if wrong:
            problems.append(f"units.json {u['code']}: 표준 태그가 아님 {', '.join(wrong)}")
        if not re.fullmatch(r"\d-\d{1,2}", u["code"]):
            problems.append(f"units.json: 단원 코드 형식 {u['code']}")

    urls: dict[str, str] = {}
    ids = set()
    if config.NEWS_DIR.exists():
        for path in sorted(config.NEWS_DIR.glob("*.json")):
            try:
                a = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"news/{path.name}: JSON 오류 {exc}")
                continue
            problems += [f"news/{path.name}: {p}" for p in check_article(a, book, path.stem)]
            ids.add(a.get("id"))
            url = a.get("url", "")
            if url in urls:
                problems.append(f"news/{path.name}: {urls[url]}와 같은 주소")
            urls[url] = path.name

    if config.MANIFEST.exists():
        m = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
        if {i["id"] for i in m.get("items", [])} != ids:
            problems.append("manifest.json이 data/news와 다름(python -m backend publish로 다시 만들기)")
        for i in m.get("items", []):
            wrong = [c for c in i.get("relatedUnits", []) if c not in codes]
            if wrong:
                problems.append(f"manifest.json {i['id']}: 없는 단원 {', '.join(wrong)}")
    elif ids:
        problems.append("manifest.json 없음")
    return problems
