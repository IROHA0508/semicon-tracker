"""Korean style rules from im-not-ai (humanize-korean) for the automatic writers (cards and article pages).

The same approach as release-radar's backend/humanize.py:

- style_rules(): the rule text added to the card and article-page prompts (site scope + the vendored
  .claude/skills/humanize-korean-site/references/quick-rules.md).
- fix_card() / fix_detail(): deterministic fixes that cannot change meaning: the comma after a connective
  ending (C-11) is removed, except inside quotes (spoken quotes, names) and after nouns like '참고,'.
- polish(): when other AI-tell signals remain, ask Claude once more to rewrite only the flagged sentences.
  A rewritten text is kept only if it keeps the same numbers, Latin words (product names, units) and URLs,
  keeps every quoted span as it was, and changes at most half of its text; otherwise the original stays.

The checks themselves live in tools/style_check.py, the script used by hand on the whole site.
"""
from __future__ import annotations

import difflib
import importlib.util
import json
import logging
import re
from collections import Counter
from functools import lru_cache

from . import config

log = logging.getLogger(__name__)

SKILL_DIR = config.ROOT / ".claude" / "skills" / "humanize-korean-site"
QUICK_RULES = SKILL_DIR / "references" / "quick-rules.md"
MAX_CHANGE = 0.5

SITE_SCOPE = """\
- 이 사이트 글은 리포트 장르다. 목록·표는 그대로 두고 문장만 다듬는다.
- 존댓말(합쇼체 "~합니다/~입니다")을 유지한다.
- 수치·단위·날짜·제품명·기술명·회사와 사람 이름·URL·따옴표 안 인용은 한 글자도 바꾸지 않는다.
- 특히 피할 것: 연결어미(-고/-며/-지만/-면서/-아서/-어서) 바로 뒤 쉼표(C-11), 제목·소제목의 "X: Y" 콜론 부제(C-10),
  한 글에 "A가 아니라 B" 대구 2번 이상(C-8), "핵심은/중요한 것은 ~" 분열문(D-8), "~로 이어집니다" 결산(D-9),
  "~하는 이유입니다" 도치(D-10), "~할 수 있습니다" 4번 이상 반복(A-10, 단정으로 바꾸지 말고 표현만 분산),
  "전략적 협력" 같은 '~적 N' 추상 수식 반복(F-5. 확률적 결함·동적 전력 같은 반도체 용어는 그대로).
"""

POLISH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["fields"],
    "properties": {"fields": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["path", "text"],
        "properties": {"path": {"type": "string"}, "text": {"type": "string"}}}}},
}


@lru_cache(maxsize=1)
def checker():
    """tools/style_check.py (the same checks the repo uses by hand)."""
    spec = importlib.util.spec_from_file_location("style_check", config.ROOT / "tools" / "style_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def style_rules() -> str:
    rules = QUICK_RULES.read_text(encoding="utf-8") if QUICK_RULES.exists() else ""
    return ("이 사이트의 글은 im-not-ai(humanize-korean)의 'AI 티' 규칙을 따른다.\n" + SITE_SCOPE
            + ("\n## im-not-ai quick-rules (원문)\n" + rules if rules else ""))


# ---------- the prose fields of a card / an article page, as paths ----------
def card_fields(card: dict, lang: str) -> dict[str, str]:
    out = {"title": card.get("title", "")} if lang == "en" else {}   # a Korean title is the original title
    for i, s in enumerate(card.get("summary") or []):
        out[f"summary.{i}"] = s
    out["interview"] = card.get("interview", "")
    return {k: v for k, v in out.items() if v}


def detail_fields(detail: dict) -> dict[str, str]:
    """Lead, key points, headings, paragraphs, list items and term notes (captions and tables are left alone)."""
    out = {"lead": detail.get("lead", "")}
    for i, s in enumerate(detail.get("keyPoints") or []):
        out[f"keyPoints.{i}"] = s
    for i, b in enumerate(detail.get("blocks") or []):
        if b.get("t") in ("h", "p"):
            out[f"blocks.{i}.text"] = b.get("text", "")
        elif b.get("t") == "ul":
            for j, s in enumerate(b.get("items") or []):
                out[f"blocks.{i}.items.{j}"] = s
    for i, t in enumerate(detail.get("terms") or []):
        out[f"terms.{i}.1"] = t[1]
    return {k: v for k, v in out.items() if v}


def _set(obj, path: str, text: str) -> None:
    parts = path.split(".")
    for p in parts[:-1]:
        obj = obj[int(p)] if isinstance(obj, list) else obj[p]
    last = parts[-1]
    if isinstance(obj, list):
        obj[int(last)] = text
    else:
        obj[last] = text


def _fix_all(obj, fields: dict[str, str]) -> int:
    fix = checker().fix_c11
    n = 0
    for path, text in fields.items():
        new = fix(text)
        if new != text:
            _set(obj, path, new)
            n += 1
    return n


def fix_card(card: dict, lang: str) -> int:
    """Remove commas after connective endings in a card. Returns how many fields changed."""
    return _fix_all(card, card_fields(card, lang))


def fix_detail(detail: dict) -> int:
    """Same for an article page (captions and table cells included)."""
    n = _fix_all(detail, detail_fields(detail))
    fix = checker().fix_c11
    for b in detail.get("blocks") or []:
        if b.get("t") == "table":
            new_rows = [[fix(c) for c in r] for r in b.get("rows") or []]
            if new_rows != b.get("rows"):
                b["rows"] = new_rows
                n += 1
        elif b.get("t") == "img" and b.get("caption"):
            new = fix(b["caption"])
            if new != b["caption"]:
                b["caption"] = new
                n += 1
    return n


# ---------- gates for a rewritten field ----------
_TOKEN = re.compile(r"https?://\S+|\$?\d[\d,.]*(?:%|×|x)?|[A-Za-z][A-Za-z0-9._/+-]*")


def anchors(text: str) -> Counter:
    """Numbers, Latin words (product names, units, IDs) and URLs: must survive a rewrite."""
    return Counter(t.rstrip(".,") for t in _TOKEN.findall(text))


def quoted(text: str) -> Counter:
    """Quoted spans (spoken quotes, names in quotes), inline code and links: kept as they are."""
    return Counter(text[a:b] for a, b in checker().protected(text))


def change_rate(a: str, b: str) -> float:
    return 1 - difflib.SequenceMatcher(None, a, b).ratio()


def accept(old: str, new: str) -> tuple[bool, str]:
    if not new.strip():
        return False, "빈 문장"
    if anchors(old) != anchors(new):
        return False, "수치·영문 표기가 달라짐"
    if quoted(old) != quoted(new):
        return False, "따옴표 안 글이 달라짐"
    if change_rate(old, new) > MAX_CHANGE:
        return False, "50% 넘게 바뀜"
    return True, ""


# ---------- signals and the one extra Claude call ----------
def signals(fields: dict[str, str], headings: list[str]) -> dict[str, list[str]]:
    """Signals over the whole card / page, without C-11 (already removed without Claude).

    headings: titles where a 'X: Y' colon subtitle counts (a translated card title, article-page headings)."""
    sc = checker()
    hits = sc.check_text("\n".join(fields.values()))
    hits.pop("C-11", None)
    colon = [h for h in headings if sc.check_title(h)]
    if colon:
        hits["C-10"] = colon
    return hits


def _flagged(fields: dict[str, str], hits: dict[str, list[str]], headings: set[str]) -> dict[str, str]:
    """The fields that hold a match of an active signal (every match of a repeated pattern is offered, so
    Claude can keep one and vary the rest)."""
    sc = checker()
    active = set(hits) - {"C-10"}
    out = {}
    for path, text in fields.items():
        if active & set(sc.check_raw(text)) or ("C-10" in hits and text in headings and sc.check_title(text)):
            out[path] = text
    return out


def polish(llm, fields: dict[str, str], headings: list[str], kind: str) -> tuple[dict[str, str], list[str]]:
    """({path: new text} to apply, notes for the run report). One Claude call at most, none when clean."""
    hits = signals(fields, headings)
    if not hits:
        return {}, []
    sc = checker()
    flagged = _flagged(fields, hits, set(headings))
    if not flagged:
        return {}, []
    user = (f"아래는 사이트 {kind} 하나의 문장들이다. 점검에서 걸린 신호: "
            + ", ".join(f"{k}({sc.describe(k)}) {len(v)}건" for k, v in hits.items())
            + "\n걸린 문장만 문체 규칙대로 고쳐 path별로 돌려줘라. 고칠 필요가 없는 문장은 그대로 돌려준다. "
              "한 글에서 반복된 표현은 하나만 남기고 나머지를 바꾼다. 수치·단위·제품명·영문 표기·URL·따옴표 안 글은 "
              "글자 그대로 둔다. 내용을 더하거나 빼지 않고 '-습니다' 존댓말을 지킨다. 연결어미 뒤에 쉼표를 넣지 않는다.\n\n"
            + json.dumps([{"path": p, "text": t} for p, t in flagged.items()], ensure_ascii=False, indent=1))
    try:
        out = llm.json_call(model=config.SUMMARY_MODEL, system=style_rules(), user=user, schema=POLISH_SCHEMA)
    except Exception as exc:  # noqa: BLE001 - the unpolished text is still fine to publish
        log.warning("style polish failed: %s", exc)
        return {}, [f"문체 다듬기 실패: {type(exc).__name__}"]
    changes, notes = {}, []
    for f in out.get("fields") or []:
        path, new = f.get("path"), sc.fix_c11(str(f.get("text") or "").strip())
        if path not in flagged or new == flagged[path]:
            continue
        ok, why = accept(flagged[path], new)
        if ok:
            changes[path] = new
            notes.append(f"문체 수정: {path}")
        else:
            notes.append(f"문체 수정 거부({why}): {path}")
    return changes, notes


def polish_card(llm, card: dict, lang: str) -> list[str]:
    """Fix commas, then polish the flagged sentences of a card in place. Returns notes."""
    fix_card(card, lang)
    fields = card_fields(card, lang)
    changes, notes = polish(llm, fields, [card["title"]] if lang == "en" else [], "기사 카드")
    for path, text in changes.items():
        _set(card, path, text)
    return notes


def polish_detail(llm, detail: dict) -> list[str]:
    """Fix commas, then polish the flagged sentences of an article page in place. Returns notes."""
    fix_detail(detail)
    fields = detail_fields(detail)
    heads = [b.get("text", "") for b in detail.get("blocks") or [] if b.get("t") == "h"]
    changes, notes = polish(llm, fields, heads, "기사 페이지")
    for path, text in changes.items():
        _set(detail, path, text)
    return notes
