"""Build data/manifest.json and data/feed/<year>.json, and check the data files.

data/news/<id>.json is the source of truth for each card. The site reads
  - data/manifest.json: sources, labels and a small index of every card (id, date, company, kind,
    tags, related units) for filters, counts and unit pages, plus the list of year files;
  - data/feed/<year>.json: the full cards of one year, loaded only when the reader gets to them,
    so the first visit stays light however many years pile up.
Related theory units are worked out from the tags at build time so that a change in
data/units.json reaches every card without summarizing again.
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
# what the manifest index keeps of each card (enough to filter, count and link without the text)
INDEX_FIELDS = ("id", "date", "published", "company", "source", "kind", "tags", "relatedUnits")
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


def feed_dir():
    return config.MANIFEST.parent / "feed"


def detail_dir():
    return config.MANIFEST.parent / "detail"


DETAIL_BLOCKS = {"h", "p", "ul", "table", "img", "fig"}


def check_detail(d: dict, stem: str, ids: set[str]) -> list[str]:
    out = []
    if d.get("id") != stem or stem not in ids:
        out.append("id가 파일 이름과 다르거나 data/news에 없는 기사")
    if not str(d.get("lead", "")).strip() or not isinstance(d.get("keyPoints"), list):
        out.append("lead·keyPoints 없음")
    for b in d.get("blocks", []):
        t = b.get("t")
        if t not in DETAIL_BLOCKS:
            out.append(f"모르는 블록: {t}")
        elif t == "img" and not str(b.get("src", "")).startswith("https://"):
            out.append(f"그림 주소가 https가 아님: {b.get('src')}")
        elif t == "fig" and not (config.MANIFEST.parent.parent / b.get("file", "")).exists():
            out.append(f"그림 파일 없음: {b.get('file')}")
        elif t in ("h", "p") and LIST_TEXT.match(str(b.get("text", ""))):
            out.append("글이 배열을 글자로 적은 모양")
    return out


def manifest_data(articles: list[dict]) -> tuple[dict, dict[str, dict]]:
    """(manifest, {year: year file}) for the given cards, newest first."""
    unit_index = tags.units()
    items = []
    for a in sorted(articles, key=lambda a: (a["published"], a["id"]), reverse=True):
        card = {k: a[k] for k in CARD_FIELDS if k in a}
        card["relatedUnits"] = tags.related_units(a.get("tags", []), unit_index)
        items.append(card)
    years: dict[str, dict] = {}
    for card in items:
        y = card["date"][:4]
        years.setdefault(y, {"year": y, "count": 0, "items": []})
        years[y]["items"].append(card)
        years[y]["count"] += 1
    manifest = {
        "count": len(items),
        "tagsVersion": _version(config.TAGS_FILE),
        "unitsVersion": _version(config.UNITS_FILE),
        "kinds": config.KIND_LABELS,
        "sources": [{"key": s.key, "name": s.name, "company": s.company, "lang": s.lang, "page": s.page,
                     "channels": [s.channel] if s.channel else sorted({c[1] for c in s.categories})}
                    for s in config.SOURCES],
        "linkOnly": [{"name": name, "url": url} for name, url in config.LINK_ONLY],
        "years": [{"year": y, "file": f"feed/{y}.json", "count": years[y]["count"]} for y in sorted(years, reverse=True)],
        "index": [{**{k: c[k] for k in INDEX_FIELDS if k in c}, **({"detail": True} if (detail_dir() / f"{c['id']}.json").exists() else {})}
                  for c in items],
    }
    return manifest, years


def _same(path, data: dict) -> bool:
    if not path.exists():
        return False
    old = json.loads(path.read_text(encoding="utf-8"))
    old.pop("generatedAt", None)
    return old == data


def build(now: datetime | None = None) -> dict:
    """Rewrite the manifest and the year files whose content changed (and drop year files that no
    longer have cards). Returns {"count", "changed"}."""
    manifest, years = manifest_data(load_articles())
    changed = False
    out = feed_dir()
    for y, data in years.items():
        path = out / f"{y}.json"
        if not _same(path, data):
            store._write(path, data)
            changed = True
    if out.exists():
        for path in out.glob("*.json"):
            if path.stem not in years:
                path.unlink()
                changed = True
    if not _same(config.MANIFEST, manifest):
        changed = True
    if changed:
        stamp = (now or collect.now_kst()).isoformat(timespec="seconds")
        store._write(config.MANIFEST, {"generatedAt": stamp, **manifest})
    return {"count": manifest["count"], "changed": changed}


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

    if detail_dir().exists():
        for path in sorted(detail_dir().glob("*.json")):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"detail/{path.name}: JSON 오류 {exc}")
                continue
            problems += [f"detail/{path.name}: {p}" for p in check_detail(d, path.stem, ids)]

    if config.MANIFEST.exists():
        m = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
        if {i["id"] for i in m.get("index", [])} != ids:
            problems.append("manifest.json이 data/news와 다름(python -m backend publish로 다시 만들기)")
        for i in m.get("index", []):
            wrong = [c for c in i.get("relatedUnits", []) if c not in codes]
            if wrong:
                problems.append(f"manifest.json {i['id']}: 없는 단원 {', '.join(wrong)}")
        in_years = set()
        for y in m.get("years", []):
            path = config.MANIFEST.parent / y["file"]
            if not path.exists():
                problems.append(f"{y['file']} 없음(python -m backend publish로 다시 만들기)")
                continue
            year_items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
            if len(year_items) != y["count"] or any(not c["date"].startswith(y["year"]) for c in year_items):
                problems.append(f"{y['file']}: 건수나 연도가 manifest와 다름")
            in_years |= {c["id"] for c in year_items}
        if in_years != ids:
            problems.append("data/feed의 연도 파일이 data/news와 다름(python -m backend publish로 다시 만들기)")
    elif ids:
        problems.append("manifest.json 없음")
    return problems
