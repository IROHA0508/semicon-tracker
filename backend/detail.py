"""Long summary of one article for the site's article page (data/detail/<id>.json).

The short card (digest.py) is two sentences. This step writes what a reader needs so as not to go back
to the original: an overview, three key points, the article's sections summarized in order (numbers,
methods and reasons kept), the article's own pictures where they stand, at most one explanatory figure
drawn from a spec (figures.py), and the terms to know. English articles come out in Korean.

Same rules as the card: only what the article says, numbers checked against the article (one retry,
then the sentences that still do not match are dropped). The article text is read in memory only;
pictures are kept as links to the newsroom's own files, not copied.

    python -m backend details --limit 5     # articles without a long summary, newest first
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Callable

from . import bodies, collect, config, feeds, figures, guard, store, summarize, tags

log = logging.getLogger(__name__)

RULES_VERSION = "2026-10-19"
STR = {"type": "string"}
MAX_ATTEMPTS = 3
CREDIT = {"samsung": "삼성전자 반도체 뉴스룸", "skhynix": "SK하이닉스 뉴스룸"}

RULES = """\
너는 반도체 면접 준비용 개인 사이트의 뉴스 편집자다. 삼성전자·SK하이닉스 공식 뉴스룸 글 하나를 읽고,
독자가 원문을 다시 읽지 않아도 내용을 이해할 수 있는 '중간 길이 요약'을 한국어로 쓴다.

분량과 구성
- 읽는 데 4~5분, 본문 전체 3,000~4,500자 안팎. 원문이 짧으면 그만큼 짧게 쓰고 원문 길이의 절반을 넘기지 않는다.
- lead: 무엇에 관한 글인지 3~4문장(누가, 무엇을, 핵심 결과·수치, 어떤 글인지: 연재 몇 편, 논문 소개, 보도자료 등).
- keyPoints: 바쁠 때 이것만 읽어도 되는 핵심 정확히 3개, 한 문장씩.
- blocks: 원문의 흐름을 따라 소제목(h)과 내용을 차례로. 소제목은 3~8개, 원문 소제목을 한국어로 다듬어 쓰되
  짧고 내용이 드러나게. 소제목마다 문단(p) 1~3개와 필요하면 글머리표(ul). 수치·방법·이유·비교는 빠짐없이,
  홍보 문구·반복·인사말은 뺀다. 원문에 비유·대응표가 있으면 표(table: head 2~4칸, rows)로 정리한다.
  인터뷰가 있으면 '질문의 요지: 답의 요지' 형태의 글머리표로 줄인다.
- terms: 이 글을 이해하는 데 필요한 전문 용어 3~8개와 한 줄 풀이(원문 정의가 있으면 그것을 따름).
- studyUnits: 아래 '이론 단원 목록'에서 이 글과 함께 공부하면 좋은 단원 코드 2~4개.

원칙
- 원문에 있는 내용만 쓴다. 원문에 없는 사실, 수치, 날짜, 전망은 쓰지 않는다(용어 풀이의 일반적 정의는 괜찮다).
- 수치는 원문 그대로 옮긴다. 영어 단위를 한국어로 바꿀 때 자릿수를 정확히 지킨다($15 billion = 150억 달러).
  원문 수치로 새로 계산한 값(합계, 차이, 배수)은 쓰지 않는다. 이 단계 뒤에 프로그램이 모든 수치를 원문과 대조한다.
- 원문이 영어면 자연스러운 한국어로 옮긴다. 제품명·기술명·고유명사는 원문 표기를 따르고, 사람 이름은 한국어로 음역하며
  처음 한 번 소속·직함을 붙인다. 회사 주장('세계 최초' 등)은 "~라고 밝혔습니다"로 쓴다. 문체는 '-습니다'.

원문 그림
- 원문 안의 '[그림 n]'은 그 자리에 원문 그림이 있다는 표시다. '원문 그림 목록'의 모든 그림을 원문 위치와 가장 가까운
  자리에 {"t": "img", "n": 번호, "caption": "..."} 블록으로 한 번씩 넣는다.
- 너는 그림을 볼 수 없다. caption은 목록에 적힌 캡션이나 대체 텍스트를 한국어로 옮긴 것만 쓰고, 둘 다 없으면 빈 문자열로 둔다.
  그림 내용을 짐작해서 쓰지 않는다.

새로 그리는 그림(figure)
- 글 이해에 꼭 도움이 될 때만 하나 그린다. 대부분의 글은 null이다. 그리는 경우:
  1) 여러 부분에 흩어진 수치·결과를 한눈에 모을 때 → type "columns": 2~4개 열(name 12자 이내, sub 18자 이내,
     lines 최대 4줄·줄마다 22자 이내, foot 22자 이내)과 결과 상자(result.label 30자 이내, result.value 36자 이내).
  2) 데이터·신호·공정이 A→B→C로 흐르는 구조를 보여 줄 때 → type "flow": 상자 2~4개(name 10자, sub 16자, desc 16자 이내,
     강조할 상자 하나에 accent true), 화살표 이름 edges(상자 수-1개, 6자 이내, 없으면 빈 문자열),
     아래 설명 줄 rows 최대 4개(label 8자, text 22자, note 30자 이내), footer 60자 이내.
- 원문 그림과 같은 내용을 다시 그리지 않는다. title은 그림이 말하는 내용을 한 문장(30자 안팎)으로, caption은 20자 안팎.
  note에는 필요할 때 '수치는 원문 값' 같은 읽는 법을 쓴다. 그림 속 글자에도 원문 수치만 쓴다.
- figure를 그리면 blocks의 알맞은 자리에 {"t": "fig"} 블록을 하나 둔다.
"""

FIG_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "type": {"type": "string", "enum": ["columns", "flow"]},
        "title": STR, "caption": STR, "note": STR, "footer": STR,
        "columns": {"type": "array", "items": {"type": "object", "properties": {
            "name": STR, "sub": STR, "lines": {"type": "array", "items": STR}, "foot": STR}}},
        "result": {"type": "object", "properties": {"label": STR, "value": STR}},
        "nodes": {"type": "array", "items": {"type": "object", "properties": {
            "name": STR, "sub": STR, "desc": STR, "accent": {"type": "boolean"}}}},
        "edges": {"type": "array", "items": STR},
        "rows": {"type": "array", "items": {"type": "object", "properties": {"label": STR, "text": STR, "note": STR}}},
    },
}
SCHEMA = {
    "type": "object",
    "properties": {
        "lead": STR,
        "keyPoints": {"type": "array", "items": STR},
        "blocks": {"type": "array", "items": {"type": "object", "properties": {
            "t": {"type": "string", "enum": ["h", "p", "ul", "table", "img", "fig"]},
            "text": STR, "items": {"type": "array", "items": STR},
            "head": {"type": "array", "items": STR},
            "rows": {"type": "array", "items": {"type": "array", "items": STR}},
            "n": {"type": "integer"}, "caption": STR}, "required": ["t"]}},
        "figure": FIG_SCHEMA,
        "terms": {"type": "array", "items": {"type": "object", "properties": {"term": STR, "desc": STR},
                                             "required": ["term", "desc"]}},
        "studyUnits": {"type": "array", "items": STR},
    },
    "required": ["lead", "keyPoints", "blocks", "figure", "terms", "studyUnits"],
}


class DetailError(RuntimeError):
    """The long summary could not be made (no usable text, too little content)."""


def detail_path(article_id: str):
    return config.DETAIL_DIR / f"{article_id}.json"


def fig_path(article_id: str):
    return config.DETAIL_DIR / "figs" / f"{article_id}-1.svg"


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def prompt(article: dict, text: str, images: list[dict], author: str) -> str:
    source = config.SOURCE_BY_KEY[article["source"]]
    lines = [
        "# 글 정보",
        f"- 출처: {source.name} / 채널: {article['channel']} (글 종류: {config.KIND_LABELS.get(article['kind'], article['kind'])})",
        f"- 원문 제목: {article.get('originalTitle') or article['title']}",
        f"- 원문 언어: {'영어' if article['lang'] == 'en' else '한국어'}",
        f"- 발행일: {article['date']}",
    ]
    if author and not config.is_company_author(author):
        lines.append(f"- 피드에 적힌 필자: {author} (회사 계정이 아님. 외부 기고일 수 있음)")
    lines += ["", "# 원문 그림 목록"]
    if images:
        for im in images:
            lines.append(f"- [그림 {im['n']}] 캡션: {im['caption'] or '(없음)'} / 대체 텍스트: {im['alt'] or '(없음)'}")
    else:
        lines.append("(그림 없음)")
    lines += ["", "# 이론 단원 목록"]
    lines += [f"- {u['code']} {u['title']}" for u in tags.units()]
    lines += ["", "# 원문", text]
    return "\n".join(lines)


def write(llm, article: dict, text: str, images: list[dict], author: str, *, fix: tuple[dict, list[str]] | None = None) -> dict:
    user = prompt(article, text, images, author)
    if fix:
        previous, bad = fix
        user += ("\n\n# 수정 요청\n직전에 쓴 요약:\n" + json.dumps(previous, ensure_ascii=False) +
                 "\n\n다음 수치를 원문에서 찾지 못했습니다: " + ", ".join(bad) +
                 "\n원문에 있는 그대로의 수치로 고치거나(단위 자릿수 주의) 그 수치를 빼고 다시 써라. 나머지 원칙은 같다.")
    return llm.json_call(model=config.SUMMARY_MODEL, system=RULES, user=user, schema=SCHEMA)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[다요]\.)\s+", text) if s]


def clean(raw: dict, article: dict, images: list[dict]) -> tuple[dict, dict | None]:
    """(detail without figure file, figure spec or None) in the stored shape."""
    by_n = {im["n"]: im for im in images}
    blocks, used, has_fig = [], set(), False
    for b in raw.get("blocks") or []:
        t = b.get("t")
        if t in ("h", "p") and _text(b.get("text")):
            blocks.append({"t": t, "text": _text(b["text"])})
        elif t == "ul":
            items = [_text(x) for x in b.get("items") or [] if _text(x)]
            if items:
                blocks.append({"t": "ul", "items": items})
        elif t == "table":
            head = [_text(x) for x in b.get("head") or []]
            rows = [[_text(x) for x in r] for r in b.get("rows") or [] if len(r) == len(head)]
            if 2 <= len(head) <= 4 and rows:
                blocks.append({"t": "table", "head": head, "rows": rows})
        elif t == "img" and b.get("n") in by_n and b["n"] not in used:
            used.add(b["n"])
            blocks.append({"t": "img", "n": b["n"], "caption": _text(b.get("caption"))})
        elif t == "fig" and not has_fig:
            has_fig = True
            blocks.append({"t": "fig"})
    for im in images:   # every picture of the article is shown, even if it was left out
        if im["n"] not in used:
            blocks.append({"t": "img", "n": im["n"], "caption": ""})
    units = {u["code"] for u in tags.units()}
    study = []
    for c in raw.get("studyUnits") or []:
        c = _text(c)
        if c in units and c not in study:
            study.append(c)
    detail = {
        "lead": _text(raw.get("lead")),
        "keyPoints": [_text(x) for x in raw.get("keyPoints") or [] if _text(x)][:3],
        "blocks": blocks,
        "terms": [[_text(x.get("term")), _text(x.get("desc"))] for x in raw.get("terms") or []
                  if _text(x.get("term")) and _text(x.get("desc"))][:8],
        "studyUnits": study[:4],
    }
    spec = raw.get("figure") if isinstance(raw.get("figure"), dict) and raw["figure"].get("type") else None
    if not spec:
        detail["blocks"] = [b for b in blocks if b["t"] != "fig"]
    return detail, spec


def _all_texts(detail: dict, spec: dict | None) -> list[str]:
    out = [detail["lead"], *detail["keyPoints"]]
    for b in detail["blocks"]:
        if b["t"] in ("h", "p"):
            out.append(b["text"])
        elif b["t"] == "ul":
            out += b["items"]
        elif b["t"] == "table":
            out += [c for r in b["rows"] for c in r] + b["head"]
        elif b["t"] == "img":
            out.append(b["caption"])
    out += [d for _, d in detail["terms"]]
    if spec:
        out += figures.texts(spec)
    return [t for t in out if t]


def number_problems(detail: dict, spec: dict | None, source: str) -> list[str]:
    bad = []
    for t in _all_texts(detail, spec):
        for n in guard.unsupported(t, source):
            if n not in bad:
                bad.append(n)
    return bad


def drop_unsupported(detail: dict, spec: dict | None, source: str) -> tuple[dict | None, list[str]]:
    """Remove the sentences, items, rows and terms whose numbers the article does not support."""
    removed: list[str] = []

    def ok(t: str) -> bool:
        if guard.unsupported(t, source):
            removed.append(t)
            return False
        return True

    detail["lead"] = " ".join(s for s in _sentences(detail["lead"]) if ok(s))
    detail["keyPoints"] = [k for k in detail["keyPoints"] if ok(k)]
    blocks = []
    for b in detail["blocks"]:
        if b["t"] == "p":
            b["text"] = " ".join(s for s in _sentences(b["text"]) if ok(s))
            if not b["text"]:
                continue
        elif b["t"] == "ul":
            b["items"] = [x for x in b["items"] if ok(x)]
            if not b["items"]:
                continue
        elif b["t"] == "table":
            b["rows"] = [r for r in b["rows"] if all(ok(c) for c in r)]
            if not b["rows"]:
                continue
        elif b["t"] == "img" and b["caption"] and not ok(b["caption"]):
            b["caption"] = ""
        blocks.append(b)
    detail["blocks"] = blocks
    detail["terms"] = [x for x in detail["terms"] if ok(x[1])]
    if spec and any(guard.unsupported(t, source) for t in figures.texts(spec)):
        removed.append("그림: " + spec.get("title", ""))
        spec = None
    return spec, removed


def make(llm, article: dict, body: bodies.Body) -> tuple[dict, dict | None, dict]:
    """(detail, figure spec, checks). Raises DetailError, summarize.AuthError, summarize.LimitError."""
    html = body.html or ""
    if html:
        text, images = feeds.html_to_marked(html, article["url"], config.DETAIL_CHAR_LIMIT)
    else:
        text, images = body.text, []
    if len(text) < config.MIN_BODY_CHARS:
        raise DetailError("본문이 너무 짧음")
    plain = re.sub(r"\[그림 \d+\]", " ", text)
    source = (article.get("originalTitle") or article["title"]) + "\n" + plain
    raw = write(llm, article, text, images, body.author)
    detail, spec = clean(raw, article, images)
    checks: dict = {}
    bad = number_problems(detail, spec, source)
    if bad:
        checks["retriedFor"] = bad
        raw2 = write(llm, article, text, images, body.author, fix=(raw, bad))
        detail2, spec2 = clean(raw2, article, images)
        bad2 = number_problems(detail2, spec2, source)
        if len(bad2) <= len(bad) and detail2["lead"]:
            detail, spec, bad = detail2, spec2, bad2
    if bad:
        spec, removed = drop_unsupported(detail, spec, source)
        if removed:
            checks["removed"] = removed
    if spec:
        try:
            figures.render(spec, "f-" + re.sub(r"[^a-z0-9]", "", article["id"].lower())[-12:])
        except figures.FigureError as exc:
            checks["figureDropped"] = str(exc)
            spec = None
    if not spec:
        detail["blocks"] = [b for b in detail["blocks"] if b["t"] != "fig"]
    body_chars = sum(len(t) for t in _all_texts(detail, None))
    if not detail["lead"] or sum(1 for b in detail["blocks"] if b["t"] == "h") < 2 or body_chars < 500:
        raise DetailError(f"요약이 너무 짧거나 소제목이 부족함({body_chars}자)")
    detail["_images"] = images
    return detail, spec, checks


def record(article: dict, detail: dict, spec: dict | None, checks: dict, now: datetime) -> dict:
    images = {im["n"]: im for im in detail.pop("_images", [])}
    credit = CREDIT.get(article["company"], "원문")
    blocks = []
    for b in detail["blocks"]:
        if b["t"] == "img":
            im = images[b["n"]]
            blocks.append({"t": "img", "src": im["src"], "caption": b["caption"] or f"원문 그림 {b['n']}",
                           "credit": credit, **({"alt": im["alt"]} if im["alt"] else {})})
        elif b["t"] == "fig":
            blocks.append({"t": "fig", "file": f"data/detail/figs/{article['id']}-1.svg",
                           "caption": _text(spec.get("caption")) or _text(spec.get("title"))})
        else:
            blocks.append(b)
    lang = "원문(영어)을 한국어로 옮겨 요약했습니다." if article["lang"] == "en" else "원문(한국어)을 요약했습니다."
    basis = lang + " 원문 그림은 원문 서버에서 그대로 불러옵니다."
    if spec:
        basis += " 구리색 테두리 그림은 이 사이트에서 새로 그린 개념도입니다."
    rec = {
        "id": article["id"], "level": "mid", "translated": article["lang"] == "en", "basis": basis,
        "lead": detail["lead"], "keyPoints": detail["keyPoints"], "blocks": blocks, "terms": detail["terms"],
        "studyUnits": detail["studyUnits"],
        "generatedAt": now.isoformat(timespec="seconds"), "model": config.SUMMARY_MODEL, "rules": RULES_VERSION,
    }
    if checks:
        rec["checks"] = checks
    return rec


def save(article: dict, rec: dict, spec: dict | None) -> None:
    if spec:
        path = fig_path(article["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(figures.render(spec, "f-" + re.sub(r"[^a-z0-9]", "", article["id"].lower())[-12:]), encoding="utf-8")
    store._write(detail_path(article["id"]), rec)


def _articles() -> list[dict]:
    if not config.NEWS_DIR.exists():
        return []
    out = [json.loads(p.read_text(encoding="utf-8")) for p in config.NEWS_DIR.glob("*.json")]
    return sorted(out, key=lambda a: (a["published"], a["id"]), reverse=True)


def run(*, llm=None, finder=None, limit: int | None = None, now: datetime | None = None,
        clock: Callable[[], float] = time.monotonic, started: float | None = None,
        budget: int | None = None) -> dict:
    """Write long summaries for up to `limit` articles that have none (newest first)."""
    now = now or collect.now_kst()
    limit = config.DETAIL_LIMIT if limit is None else limit
    budget = config.DETAIL_TIME_BUDGET if budget is None else budget
    started = clock() if started is None else started
    state = store._read(config.DETAIL_STATE, {}) if config.DETAIL_STATE.exists() else {}
    todo = [a for a in _articles() if not detail_path(a["id"]).exists()
            and state.get(a["id"], {}).get("attempts", 0) < MAX_ATTEMPTS]
    report = {"limit": limit, "detailed": [], "failed": {}, "gaveUp": [], "authError": False, "limitHit": False,
              "stoppedBy": "", "left": len(todo)}
    if not todo or limit <= 0:
        report["stoppedBy"] = "nothing to do"
        return report
    if llm is None:
        if summarize.llm_available() is None:
            report["stoppedBy"] = "no credentials"
            return report
        llm = summarize.make_llm()
    finder = finder or bodies.BodyFinder(fetch_page_html=feeds.fetch_article_html)
    done = 0
    try:
        for article in todo[:limit]:
            if clock() - started > budget:
                report["stoppedBy"] = "time budget"
                break
            body = finder.find(article)
            try:
                if body is None:
                    raise DetailError("본문을 찾지 못함(피드와 기사 페이지 모두)")
                detail, spec, checks = make(llm, article, body)
            except summarize.AuthError as exc:
                report.update(authError=True, stoppedBy="auth error", message=str(exc)[:300])
                break
            except summarize.LimitError as exc:
                report.update(limitHit=True, stoppedBy="usage limit", message=str(exc)[:300])
                break
            except Exception as exc:  # noqa: BLE001 - try again next run, give up after MAX_ATTEMPTS
                reason = (str(exc) if isinstance(exc, DetailError) else f"{type(exc).__name__}: {exc}")[:300]
                st = state.setdefault(article["id"], {"attempts": 0})
                st.update(attempts=st["attempts"] + 1, lastError=reason)
                report["failed"][article["id"]] = reason
                if st["attempts"] >= MAX_ATTEMPTS:
                    report["gaveUp"].append({"id": article["id"], "title": article["title"], "reason": reason})
                log.warning("detail %s: %s", article["id"], reason)
                continue
            save(article, record(article, detail, spec, checks, now), spec)
            state.pop(article["id"], None)
            done += 1
            report["detailed"].append({"id": article["id"], "title": article["title"], "figure": bool(spec)})
            log.info("detail %s (%s)", article["id"], "figure" if spec else "no figure")
        else:
            report["stoppedBy"] = "limit" if len(todo) > limit else "all done"
    finally:
        store._write(config.DETAIL_STATE, state)
        report["left"] = len(todo) - done
    return report
