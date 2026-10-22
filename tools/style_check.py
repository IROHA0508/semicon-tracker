#!/usr/bin/env python3
"""사이트 글에서 'AI 티' 문체 신호를 찾는다. (im-not-ai의 humanize-korean 규칙 중 이 사이트 장르에 맞는 것만)

규칙 원본: .claude/skills/humanize-korean-site/references/quick-rules.md (MIT, epoko77-ai/im-not-ai v2.3.2)
규칙 ID(C-11, D-8 …)는 원본 분류 체계를 그대로 따른다. 원본이 '기각'한 신호(A-2 '~를 통해', I-1 '~것이다',
H-1 문두 접속사, J-2 따옴표, D-4 hype 어휘)는 일부러 보지 않는다. 릴리스 레이더의 scripts/style_check.py와
같은 규칙이고, 이 사이트에 맞춰 두 가지를 더했다.

- 따옴표 안(발언 인용, 원문 제목, 행사·제품 이름), 인라인 코드, 링크 주소와 링크 글자(영상·자료 제목)는
  보지도 고치지도 않는다(원본 Do-NOT: 발화자가 있는 직접 인용, 고유명사).
- '~적 N'(F-5)에서 '-적' 접미사가 아닌 명사(면적, 집적, 퇴적, 실적 …)는 세지 않는다.

보는 글:
  news       data/news/*.json        카드(번역 제목, 요약, 면접 한 줄). 한국어 기사 제목은 원제라 보지 않는다
  detail     data/detail/*.json      기사 페이지(개요, 핵심 3줄, 소제목, 문단, 목록, 표, 그림 설명, 용어 풀이)와
             data/detail/figs/*.svg  새로 그린 그림의 글자
  theory     theory/**/*.md          이론 원고(단원, 층 소개, 개요, 출처)와 theory/figures/*.svg 도식의 글자
  animations animations/*.html       단계 애니메이션·영상의 설명과 자막, catalog.json의 제목·소개 글
  ui         index.html              화면 문구

사용:
  python3 tools/style_check.py                  # 전체 요약
  python3 tools/style_check.py --spans          # 걸린 문장까지 출력
  python3 tools/style_check.py --only theory    # 한 종류만
  python3 tools/style_check.py --json out.json
  python3 tools/style_check.py --fix-c11        # 연결어미 뒤 쉼표(C-11)만 파일에서 지운다(뜻이 바뀌지 않는 수정)
판정은 경고용이다(실패 코드 없음). 다만 C-11은 tests/test_style.py가 0건인지 확인한다.
자동 요약(backend/humanize.py)도 이 파일의 함수를 그대로 쓴다.
"""
from __future__ import annotations

import argparse
import json
import re
import signal
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
THEORY = ROOT / "theory"
ANIMATIONS = ROOT / "animations"

# ---------- 보호 구간: 따옴표 안, 코드, 링크 ----------
# 큰따옴표는 한 문단 안에서 짝을 찾고, 작은따옴표는 이름·용어 강조라 짧은 것만 본다(영어 소유격 's와 헷갈리지 않게).
# HTML·스크립트 파일에서는 곧은 따옴표와 백틱이 문자열 구분자라서 둥근 따옴표·꺾쇠·주소만 보호한다.
_CURLY = (r"“[^”\n]{0,600}”|‘[^’\n]{0,120}’|「[^」\n]{0,200}」|『[^』\n]{0,200}』|https?://[^\s\"'<>`]+")
_PROTECT = re.compile(
    _CURLY + r"|\"[^\"\n]{1,600}\""
    r"|(?<![A-Za-z])'[^'\n]{1,120}'(?![A-Za-z])"
    r"|`[^`\n]+`"
    r"|!?\[[^\]\n]*\]\([^)\s]*\)"
)
_PROTECT_HTML = re.compile(_CURLY)


def protected(text: str, html: bool = False) -> list[tuple[int, int]]:
    return [m.span() for m in (_PROTECT_HTML if html else _PROTECT).finditer(text)]


def mask(text: str) -> str:
    """보호 구간을 같은 길이의 공백으로 바꾼다(신호를 셀 때만 씀)."""
    out = list(text)
    for a, b in protected(text):
        out[a:b] = " " * (b - a)
    return "".join(out)


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


# ---------- C-11 연결어미 직후 쉼표 ----------
# '고'로 끝나는 명사(참고·재고·레고 …) 뒤 쉼표는 연결어미가 아니므로 제외한다. 낱말 전체가 같을 때만 명사로 본다
# (생기고·앞당기고는 '기고'가 아니다).
GO_NOUNS = {"참고", "최고", "광고", "경고", "보고", "재고", "창고", "사고", "신고", "원고", "제고", "공고", "잔고",
            "상고", "투고", "기고", "회고", "숙고", "중고", "선고", "로고", "레고", "산티아고", "샌디에이고", "시카고",
            "엔고", "망고"}
# 동사로도 쓰는 말(보다·재다·사다): 앞말이 목적어·부사격(을/를/로)이거나 '-아/-어 보고'면 연결어미다.
GO_VERBS = {"보고", "재고", "사고"}
_VERB_BEFORE = re.compile(r"(?:[을를로]|으로|[아어해워와봐])\s*$")
# 이름 '아서'(아서 왕 등)는 연결어미가 아니다.
SEO_NOUNS = {"아서"}
_C11 = re.compile(r"(?<![가-힣])([가-힣]*?)(고|며|지만|면서|아서|어서)((?:</(?:b|strong|em)>)?)\s*,")


def _not_ending(m: re.Match, text: str) -> bool:
    word, ending = m.group(1) + m.group(2), m.group(2)
    if ending == "고" and word in GO_NOUNS:
        return not (word in GO_VERBS and _VERB_BEFORE.search(text[max(0, m.start() - 4):m.start()]))
    return ending == "아서" and word in SEO_NOUNS


def _c11_matches(text: str, html: bool = False) -> list[re.Match]:
    spans = protected(text, html)
    return [m for m in _C11.finditer(text) if not _inside(m.start(2), spans) and not _not_ending(m, text)]


def c11_spans(text: str, html: bool = False) -> list[str]:
    return [m.group(0) for m in _c11_matches(text, html)]


def fix_c11(text: str, html: bool = False) -> str:
    """연결어미 뒤 쉼표만 지운다(명사 '참고,'와 따옴표·코드·링크 안은 그대로). 다른 글자는 바꾸지 않는다."""
    out, last = [], 0
    for m in _c11_matches(text, html):
        out += [text[last:m.start()], m.group(1), m.group(2), m.group(3)]
        last = m.end()
    return "".join(out) + text[last:]


# ---------- 나머지 신호 ----------
# '-적' 접미사가 아니라 그 자체로 명사인 말(F-5에서 세지 않음)
JEOK_NOUNS = {"면적", "집적", "퇴적", "축적", "누적", "실적", "목적", "최적", "흔적", "표적", "지적", "체적", "용적",
              "업적", "국적", "기적", "서적", "성적", "궤적", "족적", "전적", "필적", "적적", "호적", "단면적",
              "표면적", "총면적", "고집적", "칩면적", "셀면적", "다목적",
              # 반도체·물리 용어로 쓰는 '-적'(추상 수식이 아님): 확률적 결함, 동적 전력, 화학적·기계적 연마 …
              "물리적", "확률적", "기계적", "전기적", "화학적", "전기화학적", "열적", "광학적", "동적", "정적",
              "선형적", "비선형적", "통계적", "이론적", "수학적", "계절적", "양적", "선택적", "자기적", "법적"}
_F5 = re.compile(r"(?<![가-힣])([가-힣]{1,5}적)\s(?!으로)[가-힣]")

# (ID, 심각도, 설명, 정규식, 문서당 몇 번부터 신호로 볼지)
PATTERNS = [
    ("A-3", "S1", "'~에 있어(서)' 번역투", r"에\s?있어(?:서)?(?![가-힣])", 1),
    ("A-7", "S1", "'가지고 있다' 직역", r"가지고\s?있", 1),
    ("A-8", "S1", "이중 피동 '~되어지다'", r"되어지|어지게\s?되", 1),
    ("A-9", "S2", "'~에 의해' 피동", r"에\s?의해", 1),
    ("A-21", "S2", "'단순한 X를 넘어'", r"단순(?:한|히)\s?[^.]{0,20}넘어", 1),
    ("A-22", "S2", "'~은 명확하다/분명하다' 평가 술어", r"(?:명확|분명)(?:하다|합니다)", 1),
    ("A-24", "S2", "'더 이상' 반복", r"더\s?이상", 2),
    ("C-8", "S1", "'A가 아니라 B' 대구 반복", r"(?:가|이)\s?아니라|것이\s?아니라|이기보다", 2),
    ("D-1", "S1", "결산 접속어", r"결론적으로|요약하면|정리하자면|그러므로", 1),
    ("D-2", "S1", "의의 과장", r"시사하는\s?바|주목할\s?만하|매우\s?중요", 1),
    ("D-3", "S1", "열거 도입구", r"(?:두|세|네|다섯)\s?가지로\s?나눌|다음과\s?같(?:은|습니다|다)", 1),
    ("D-6", "S2", "결말 공식 '~할 때입니다'", r"할\s?때(?:입니다|이다)|시점(?:입니다|이다)", 1),
    ("D-8", "S2", "분열문 '핵심은/중요한 것은'", r"(?:핵심|관건|중요한\s?것|필요한\s?것|문제)은\s", 1),
    ("D-9", "S2", "'~로 이어진다' 결산", r"(?:로|으로)\s?이어(?:진다|집니다)|직결", 1),
    ("D-10", "S2", "도치 결산 '~하는 이유다'", r"이유(?:다|입니다)[.\s]", 1),
    ("D-12", "S2", "문패 문장 '과제도 남아 있다'", r"과제도\s?남|한계도\s?분명|아쉬운\s?점도", 1),
    ("D-14", "S2", "사전 은유", r"청사진|신호탄|잠식|적신호|경고등|뿌리내|움켜쥐|짓누르", 1),
    ("I-2", "S2", "형식명사 강조 '주목할 점은'", r"주목할\s?점은|점에\s?있다", 1),
    ("I-3", "S2", "'~다는 것이다/뜻이다' 결말", r"다는\s?(?:것이다|것입니다|뜻이다|뜻입니다)", 2),
    ("H-4", "S2", "'즉' 남발", r"(?:^|[\s.])즉[,\s]", 3),
    ("J-3", "S2", "대시(—) 부가 설명", r"—", 2),
    ("F-5", "S2", "'~적 N' 추상 체인", None, 4),
    ("A-10", "S2", "'~할 수 있습니다' 반복", r"수\s?있(?:습니다|다)", 4),
]
_COMPILED = [(i, s, d, re.compile(p) if p else None, n) for i, s, d, p, n in PATTERNS]
# 문서 전체에 걸쳐 세는 신호(한 문장만 고쳐서는 사라지지 않음)
REPEAT_SIGNALS = {p[0] for p in PATTERNS if p[4] > 1}


def _f5(text: str) -> list[str]:
    return [m.group(0) for m in _F5.finditer(text) if m.group(1) not in JEOK_NOUNS]


def check_title(title: str) -> dict[str, list[str]]:
    """C-10: 제목의 'X: Y' 콜론 부제."""
    return {"C-10": [title]} if re.search(r"[^\d]:\s", mask(title or "")) else {}


def check_text(text: str) -> dict[str, list[str]]:
    """문서 하나(카드 하나, 기사 페이지 하나, 단원 하나)의 글을 받아 걸린 규칙과 일치 구간을 돌려준다."""
    hits: dict[str, list[str]] = {}
    c11 = c11_spans(text)
    if c11:
        hits["C-11"] = c11
    plain = mask(text)
    for pid, _sev, _desc, rx, at_least in _COMPILED:
        found = _f5(plain) if rx is None else [m.group(0) for m in rx.finditer(plain)]
        if len(found) >= at_least:
            hits[pid] = found
    return hits


def check_raw(text: str) -> dict[str, list[str]]:
    """모든 신호의 일치 구간(문서당 기준 횟수 없이). 어느 문장에 반복 신호가 들어 있는지 찾을 때 쓴다(C-11 제외)."""
    plain = mask(text)
    hits = {}
    for pid, _sev, _desc, rx, _n in _COMPILED:
        found = _f5(plain) if rx is None else [m.group(0) for m in rx.finditer(plain)]
        if found:
            hits[pid] = found
    return hits


def describe(pid: str) -> str:
    if pid == "C-11":
        return "연결어미(-고/-며/-지만/-면서/-아서/-어서) 뒤 쉼표"
    if pid == "C-10":
        return "제목의 'X: Y' 콜론 부제"
    return next(d for i, _s, d, _p, _n in PATTERNS if i == pid)


def severity(pid: str) -> str:
    if pid in ("C-11",):
        return "S1"
    if pid == "C-10":
        return "S2"
    return next(s for i, s, _d, _p, _n in PATTERNS if i == pid)


# ---------- 사이트 글 꺼내기 ----------
def card_parts(a: dict) -> list[str]:
    parts = [a["title"]] if a.get("lang") == "en" else []
    parts += [s for s in a.get("summary") or [] if isinstance(s, str)]
    if a.get("interview"):
        parts.append(a["interview"])
    return [p for p in parts if p]


def detail_parts(d: dict) -> list[str]:
    parts = [d.get("lead", ""), *(d.get("keyPoints") or [])]
    for b in d.get("blocks") or []:
        t = b.get("t")
        if t in ("h", "p"):
            parts.append(b.get("text", ""))
        elif t == "ul":
            parts += b.get("items") or []
        elif t == "table":
            parts += (b.get("head") or []) + [c for r in b.get("rows") or [] for c in r]
        elif t in ("img", "fig"):
            parts.append(b.get("caption", ""))
    parts += [x[1] for x in d.get("terms") or [] if len(x) > 1]
    return [p for p in parts if p]


def detail_headings(d: dict) -> list[str]:
    return [b.get("text", "") for b in d.get("blocks") or [] if b.get("t") == "h"]


def _theory_body(text: str) -> str:
    """머리말·코드 블록을 빼고, 서식으로 쓰는 대시(영상 줄 '- [제목](주소) — 메모', 태그 줄)는 셈에서 뺀다."""
    if text.startswith("---\n"):
        text = text[4:].partition("\n---\n")[2]
    lines, in_code = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("- [") or line.startswith("**관련 뉴스 태그**"):
            line = line.replace("—", " ")
        lines.append(line)
    return "\n".join(lines)


def theory_files() -> list[Path]:
    files = sorted((THEORY / "units").glob("*.md")) + sorted((THEORY / "floors").glob("*.md"))
    return files + [p for p in (THEORY / "overview.md", THEORY / "sources.md") if p.exists()]


def svg_files(kind: str) -> list[Path]:
    return sorted((THEORY / "figures" if kind == "theory" else DATA / "detail" / "figs").glob("*.svg"))


_HTML_TEXT = re.compile(r"[^\"'`<>{}\n]*[가-힣][^\"'`<>{}\n]*")


def html_parts(html: str) -> list[str]:
    """HTML·스크립트에서 한글이 든 글 조각(문자열, 태그 사이 글자). 주석과 CSS는 뺀다."""
    html = re.sub(r"<!--.*?-->|<style\b.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"/\*.*?\*/", " ", html, flags=re.S)
    html = re.sub(r"(?m)^\s*//[^\n]*$", " ", html)
    return [m.group(0).strip() for m in _HTML_TEXT.finditer(html) if len(m.group(0).strip()) > 1]


def site_docs(only: str | None = None) -> dict[str, list[str]]:
    """{문서 이름: 글 조각}. 문서 하나가 반복 신호를 세는 단위다."""
    docs: dict[str, list[str]] = {}
    if only in (None, "news"):
        for f in sorted((DATA / "news").glob("*.json")):
            docs[f"news/{f.stem}"] = card_parts(json.loads(f.read_text(encoding="utf-8")))
    if only in (None, "detail"):
        for f in sorted((DATA / "detail").glob("*.json")):
            docs[f"detail/{f.stem}"] = detail_parts(json.loads(f.read_text(encoding="utf-8")))
        for f in svg_files("detail"):
            docs[f"detail/figs/{f.stem}"] = html_parts(f.read_text(encoding="utf-8"))
    if only in (None, "theory"):
        for f in theory_files():
            docs[f"theory/{f.relative_to(THEORY).with_suffix('')}"] = [_theory_body(f.read_text(encoding="utf-8"))]
        for f in svg_files("theory"):
            docs[f"theory/figures/{f.stem}"] = html_parts(f.read_text(encoding="utf-8"))
    if only in (None, "animations"):
        for f in sorted(ANIMATIONS.glob("*.html")):
            if f.name != "index.html":
                docs[f"animations/{f.stem}"] = html_parts(f.read_text(encoding="utf-8"))
        cat = json.loads((ANIMATIONS / "catalog.json").read_text(encoding="utf-8"))
        docs["animations/catalog"] = [x for a in cat.get("animations", []) + cat.get("films", [])
                                      for x in (a.get("title", ""), a.get("summary", "")) if x]
    if only in (None, "ui"):
        docs["ui/index"] = html_parts((ROOT / "index.html").read_text(encoding="utf-8"))
    return docs


def site_titles(only: str | None = None) -> dict[str, list[str]]:
    """C-10을 볼 제목: 번역한 카드 제목과 기사 페이지 소제목(소제목은 한 기사에 둘 이상일 때만 '반복')."""
    out: dict[str, list[str]] = {}
    if only in (None, "news"):
        for f in sorted((DATA / "news").glob("*.json")):
            a = json.loads(f.read_text(encoding="utf-8"))
            if a.get("lang") == "en":
                out[f"news/{f.stem}"] = [a["title"]]
    if only in (None, "detail"):
        for f in sorted((DATA / "detail").glob("*.json")):
            hs = [h for h in detail_headings(json.loads(f.read_text(encoding="utf-8"))) if check_title(h)]
            if len(hs) >= 2:
                out[f"detail/{f.stem}"] = hs
    return out


def scan(only: str | None = None) -> dict[str, dict[str, list[str]]]:
    per_doc: dict[str, dict[str, list[str]]] = {}
    titles = site_titles(only)
    for name, parts in site_docs(only).items():
        hits = check_text("\n".join(parts))
        for t in titles.get(name, []):
            for pid, spans in check_title(t).items():
                hits.setdefault(pid, []).extend(spans)
        if hits:
            per_doc[name] = hits
    return per_doc


# ---------- --fix-c11: 파일에서 연결어미 뒤 쉼표 지우기 ----------
def _fix_json_strings(value, keys: set[str] | None = None, key: str | None = None):
    if isinstance(value, str):
        return fix_c11(value) if keys is None or key in keys else value
    if isinstance(value, list):
        return [_fix_json_strings(v, keys, key) for v in value]
    if isinstance(value, dict):
        return {k: _fix_json_strings(v, keys, k) for k, v in value.items()}
    return value


def fix_card(a: dict) -> dict:
    a = dict(a)
    if a.get("lang") == "en":
        a["title"] = fix_c11(a["title"])
    a["summary"] = [fix_c11(s) for s in a.get("summary") or []]
    a["interview"] = fix_c11(a.get("interview") or "")
    return a


def fix_detail(d: dict) -> dict:
    d = dict(d)
    d["lead"] = fix_c11(d.get("lead", ""))
    d["keyPoints"] = [fix_c11(s) for s in d.get("keyPoints") or []]
    d["blocks"] = [_fix_json_strings(b, {"text", "items", "head", "rows", "caption"}) for b in d.get("blocks") or []]
    d["terms"] = [[t[0], fix_c11(t[1]), *t[2:]] for t in d.get("terms") or []]
    return d


def fix_theory(text: str) -> str:
    head = ""
    if text.startswith("---\n"):
        meta, sep, body = text[4:].partition("\n---\n")
        head, text = "---\n" + meta + sep, body
    out, in_code = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        out.append(line if in_code or line.startswith("```") else fix_c11(line))
    return head + "\n".join(out)


def _write_json(path: Path, data, like: str = "") -> None:
    """원래 파일과 같은 들여쓰기로 쓴다(대부분 2칸, 손으로 만든 예시는 1칸)."""
    m = re.match(r"[\[{]\n( +)", like)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=len(m.group(1)) if m else 2) + "\n", encoding="utf-8")


def fix_files(only: str | None = None) -> Counter:
    """연결어미 뒤 쉼표를 파일에서 지운다. 고친 파일 수를 종류별로 돌려준다."""
    changed: Counter = Counter()
    if only in (None, "news"):
        for f in sorted((DATA / "news").glob("*.json")):
            text = f.read_text(encoding="utf-8")
            a = json.loads(text)
            b = fix_card(a)
            if b != a:
                _write_json(f, b, text)
                changed["news"] += 1
    if only in (None, "detail"):
        for f in sorted((DATA / "detail").glob("*.json")):
            text = f.read_text(encoding="utf-8")
            a = json.loads(text)
            b = fix_detail(a)
            if b != a:
                _write_json(f, b, text)
                changed["detail"] += 1
    if only in (None, "theory"):
        for f in theory_files():
            a = f.read_text(encoding="utf-8")
            b = fix_theory(a)
            if b != a:
                f.write_text(b, encoding="utf-8")
                changed["theory"] += 1
    if only in (None, "animations"):
        # catalog.json은 손으로 맞춘 줄 모양(chapters 한 줄)을 지키려고 제목·소개 줄만 글자 단위로 고친다.
        f = ANIMATIONS / "catalog.json"
        a = f.read_text(encoding="utf-8")
        b = "\n".join(fix_c11(line, html=True) if line.lstrip().startswith(('"summary":', '"title":')) else line
                      for line in a.split("\n"))
        if b != a:
            json.loads(b)
            f.write_text(b, encoding="utf-8")
            changed["animations"] += 1
    html = []
    if only in (None, "theory"):
        html += svg_files("theory")
    if only in (None, "detail"):
        html += svg_files("detail")
    if only in (None, "animations"):
        html += [f for f in sorted(ANIMATIONS.glob("*.html")) if f.name != "index.html"]
    if only in (None, "ui"):
        html.append(ROOT / "index.html")
    for f in html:
        a = f.read_text(encoding="utf-8")
        b = fix_c11(a, html=True)
        if b != a:
            f.write_text(b, encoding="utf-8")
            kind = "ui" if f == ROOT / "index.html" else "theory" if f.parent == THEORY / "figures" \
                else "detail" if f.suffix == ".svg" else "animations"
            changed[kind] += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    if hasattr(signal, "SIGPIPE"):          # '| head'로 잘라 봐도 오류를 내지 않게
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spans", action="store_true", help="걸린 구간까지 출력")
    ap.add_argument("--only", choices=["news", "detail", "theory", "animations", "ui"], help="한 종류만 보기")
    ap.add_argument("--json", help="결과를 JSON 파일로 저장")
    ap.add_argument("--fix-c11", action="store_true", help="연결어미 뒤 쉼표를 파일에서 지운다")
    args = ap.parse_args(argv)
    if args.fix_c11:
        changed = fix_files(args.only)
        print("연결어미 뒤 쉼표를 지운 파일: " + (", ".join(f"{k} {v}개" for k, v in changed.items()) or "없음"))
        if changed["news"]:
            print("카드를 고쳤으면 python -m backend publish로 data/feed를 다시 만드세요.")
        if changed["theory"]:
            print("원고를 고쳤으면 python tools/build_theory.py로 data/theory.json을 다시 만드세요.")
        if changed["animations"]:
            print("애니메이션 목록을 고쳤으면 python tools/build_animation_index.py로 목록 페이지를 다시 만드세요.")
    total, per_doc = Counter(), scan(args.only)
    for hits in per_doc.values():
        for pid, spans in hits.items():
            total[pid] += len(spans)
    n_docs = len(site_docs(args.only))
    print(f"문서 {n_docs}개 중 신호가 있는 문서 {len(per_doc)}개")
    for pid, n in total.most_common():
        print(f"  {pid:5} {severity(pid)} {n:5}건  {describe(pid)}")
    if args.spans:
        for name, hits in per_doc.items():
            print(f"\n[{name}]")
            for pid, spans in hits.items():
                print(f"  {pid}: {' | '.join(spans[:8])}")
    if args.json:
        Path(args.json).write_text(json.dumps(per_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
