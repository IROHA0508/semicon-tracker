"""Build data/theory.json and data/units.json from the theory manuscript in theory/.

    python tools/build_theory.py          # write both files
    python tools/build_theory.py --check  # exit 1 if either file is out of date (used by the tests)

theory/units/<code>.md is the source for every unit. The only hand-kept data is the front matter
(`code`, `tags` = standard tags); everything else is read from the text:

    # <code> <title>                                   → code, title, floor
    면접 빈도 <freq> · 이어지는 단원: <...>              → stars (★ before any bracket), freq, related codes
    ![<caption>](../figures/<file>.svg)                → figures
    **관련 뉴스 태그** `a` `b` — ...                     → manuscriptTags
    **영상으로 보기** followed by "- [title](url) — note" → videos
    animations/catalog.json entries with the same unit  → animations
    animations/catalog.json "films" with the same unit   → films (time-based film pages)

data/units.json keeps its schema (the backend reads it to pick each news card's related units) and
its `version`/`note` fields; change `version` by hand when unit tags change.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEORY = ROOT / "theory"
UNITS_DIR = THEORY / "units"
UNITS_JSON = ROOT / "data" / "units.json"
THEORY_JSON = ROOT / "data" / "theory.json"
CATALOG = ROOT / "animations" / "catalog.json"

CODE = re.compile(r"\b(\d)-(\d{1,2})\b")
RANGE = re.compile(r"\b(\d)-(\d{1,2})\s*\\?~\s*(\d)-(\d{1,2})\b")
FIGURE = re.compile(r"!\[(.*?)\]\(\.\./figures/([\w.-]+\.svg)\)")
LINK_ITEM = re.compile(r"^- \[(.+?)\]\((https?://[^)\s]+)\)(?:\s*—\s*(.*))?$")


def unescape(text: str) -> str:
    """Markdown backslash escapes (\\~, \\[, \\]) → plain text."""
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!~|>])", r"\1", text)


def unit_key(code: str) -> tuple[int, int]:
    floor, num = code.split("-")
    return int(floor), int(num)


def front_matter(text: str, name: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{name}: front matter missing")
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key.strip()] = value
    return meta, body.lstrip("\n")


def section_lines(body: str, label: str) -> list[str]:
    """Lines of the block that follows a '**label**' line (which may go on with a lead-in), up to the
    next bold label or heading."""
    lines = body.splitlines()
    out, inside = [], False
    for line in lines:
        if line.startswith(f"**{label}**"):
            inside = True
            continue
        if inside:
            if line.startswith("**") or line.startswith("#"):
                break
            out.append(line)
    return out


def related_codes(text: str, own: str, known: set[str]) -> list[str]:
    codes = []
    for m in RANGE.finditer(text):
        f1, a, f2, b = m.groups()
        if f1 == f2:
            codes += [f"{f1}-{n}" for n in range(int(a), int(b) + 1)]
    for m in CODE.finditer(RANGE.sub(" ", text)):
        codes.append(f"{m.group(1)}-{m.group(2)}")
    seen = []
    for c in codes:
        if c != own and c in known and c not in seen:
            seen.append(c)
    return seen


def parse_unit(path: Path, known: set[str]) -> dict:
    text = path.read_text(encoding="utf-8")
    meta, body = front_matter(text, path.name)
    first = body.splitlines()[0]
    m = re.match(r"# (\d-\d+) (.+)$", first)
    if not m:
        raise ValueError(f"{path.name}: first line must be '# <code> <title>'")
    code, title = m.group(1), unescape(m.group(2).strip())
    if code != path.stem or meta.get("code") != code:
        raise ValueError(f"{path.name}: code mismatch ({meta.get('code')}, {code})")
    info = next((l for l in body.splitlines() if l.startswith("면접 빈도 ")), "")
    fm = re.match(r"면접 빈도 (.+?) · 이어지는 단원: (.+)$", info)
    if not fm:
        raise ValueError(f"{path.name}: '면접 빈도 … · 이어지는 단원: …' line missing")
    freq = unescape(fm.group(1).strip())
    stars = freq.split("(")[0].count("★")
    tag_line = next((l for l in body.splitlines() if l.startswith("**관련 뉴스 태그**")), "")
    manuscript_tags = re.findall(r"`([^`]+)`", tag_line.split(" — ")[0])
    videos = []
    for line in section_lines(body, "영상으로 보기"):
        lm = LINK_ITEM.match(line.strip())
        if lm:
            videos.append({"title": unescape(lm.group(1)), "url": lm.group(2), "note": unescape(lm.group(3) or "")})
    figures = [{"file": f"theory/figures/{f}", "caption": unescape(c)} for c, f in FIGURE.findall(body)]
    return {
        "code": code,
        "floor": int(code.split("-")[0]),
        "title": title,
        "stars": stars,
        "freq": freq,
        "related": related_codes(fm.group(2), code, known),
        "tags": meta.get("tags", []),
        "manuscriptTags": manuscript_tags,
        "file": f"theory/units/{path.name}",
        "figures": figures,
        "videos": videos,
    }


def parse_floor(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    title = lines[0].lstrip("# ").strip()
    return {"floor": int(path.stem), "title": title, "name": title.split("·", 1)[-1].strip(),
            "intro": "\n".join(lines[1:]).strip(), "file": f"theory/floors/{path.name}"}


def build() -> tuple[dict, dict]:
    paths = sorted(UNITS_DIR.glob("*.md"), key=lambda p: unit_key(p.stem))
    known = {p.stem for p in paths}
    units = [parse_unit(p, known) for p in paths]
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog = cat["animations"]
    for u in units:
        u["films"] = [
            {"file": f"animations/{f['file']}", "title": f["title"], "seconds": f["seconds"], "chapters": f["chapters"]}
            for f in cat.get("films", []) if f["unit"] == u["code"]]
        u["animations"] = [
            {"file": f"animations/{a['file']}", "title": a["title"],
             "modes": [{"id": m["id"], "label": m["label"], "steps": m["steps"]} for m in a["modes"]],
             "steps": sum(m["steps"] for m in a["modes"])}
            for a in catalog if a["unit"] == u["code"]]
    floors = [parse_floor(p) for p in sorted((THEORY / "floors").glob("*.md"), key=lambda p: int(p.stem))]
    for f in floors:
        f["units"] = [u["code"] for u in units if u["floor"] == f["floor"]]
    old = json.loads(UNITS_JSON.read_text(encoding="utf-8"))
    units_json = {
        "version": old["version"],
        "note": old["note"],
        "units": [{k: u[k] for k in ("code", "floor", "title", "stars", "freq", "manuscriptTags", "tags")} for u in units],
    }
    overview_figs = [{"file": f"theory/figures/{f}", "caption": unescape(c)}
                     for c, f in re.findall(r"!\[(.*?)\]\(figures/([\w.-]+\.svg)\)", (THEORY / "overview.md").read_text(encoding="utf-8"))]
    urls = [v["url"] for u in units for v in u["videos"]]
    theory = {
        "version": old["version"],
        "note": "이론 원고 59단원의 목록. 본문은 theory/ 아래 마크다운 파일이고, 이 파일은 tools/build_theory.py가 만든다.",
        "overview": {"file": "theory/overview.md", "figures": overview_figs},
        "sources": {"file": "theory/sources.md"},
        "floors": floors,
        "units": units,
        "counts": {
            "units": len(units),
            "figures": sum(len(u["figures"]) for u in units) + len(overview_figs),
            "videoLinks": len(urls),
            "videoUrls": len(set(urls)),
            "unitsWithVideos": sum(1 for u in units if u["videos"]),
            "animations": sum(len(u["animations"]) for u in units),
            "films": sum(len(u["films"]) for u in units),
        },
    }
    return theory, units_json


def dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str]) -> int:
    theory, units_json = build()
    outputs = {THEORY_JSON: dump(theory), UNITS_JSON: dump(units_json)}
    if "--check" in argv:
        stale = [p.name for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            print("out of date:", ", ".join(stale), "— run python tools/build_theory.py")
            return 1
        return 0
    for p, text in outputs.items():
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8")
            print("wrote", p.relative_to(ROOT))
    print(json.dumps(theory["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
