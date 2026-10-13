"""Checks for the theory manuscript in theory/: the built files are up to date, every unit keeps the
fixed frame, figures exist and are self-contained SVG, and links between units, tags, figures and
animations all resolve.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_theory  # noqa: E402

THEORY = ROOT / "theory"
UNIT_FILES = sorted((THEORY / "units").glob("*.md"), key=lambda p: build_theory.unit_key(p.stem))
DATA = json.loads((ROOT / "data" / "theory.json").read_text(encoding="utf-8"))
UNITS = {u["code"]: u for u in DATA["units"]}
TAGBOOK = json.loads((ROOT / "data" / "tags.json").read_text(encoding="utf-8"))
STANDARD = {t["name"] for g in TAGBOOK["groups"] for t in g["tags"]}
SVG_NS = "{http://www.w3.org/2000/svg}"


def test_built_files_up_to_date():
    assert build_theory.main(["--check"]) == 0, "run python tools/build_theory.py"


def test_units_match_files():
    codes = [p.stem for p in UNIT_FILES]
    assert codes == list(UNITS)
    units_json = json.loads((ROOT / "data" / "units.json").read_text(encoding="utf-8"))["units"]
    assert [u["code"] for u in units_json] == codes
    assert [f["floor"] for f in DATA["floors"]] == list(range(7))
    assert sorted(c for f in DATA["floors"] for c in f["units"]) == sorted(codes)
    for f in DATA["floors"]:
        assert f["units"], f["title"]


@pytest.mark.parametrize("path", UNIT_FILES, ids=[p.stem for p in UNIT_FILES])
def test_unit_frame(path):
    text = path.read_text(encoding="utf-8")
    meta, body = build_theory.front_matter(text, path.name)
    assert set(meta) == {"code", "tags"}
    lines = body.splitlines()
    assert lines[0].startswith(f"# {path.stem} ")
    assert any(l.startswith("면접 빈도 ") and " · 이어지는 단원: " in l for l in lines[:4])
    for label in ("한 줄 정의", "관련 뉴스 태그", "반영 자료"):
        assert any(l.startswith(f"**{label}**") for l in lines), label
    assert "embedded content" not in text
    assert "&#91;" not in text


@pytest.mark.parametrize("code", list(UNITS))
def test_unit_links_resolve(code):
    u = UNITS[code]
    assert 0 <= u["stars"] <= 3
    assert all(t in STANDARD for t in u["tags"]), u["tags"]
    assert len(set(u["tags"])) == len(u["tags"])
    assert all(r in UNITS and r != code for r in u["related"])
    for f in u["figures"]:
        assert (ROOT / f["file"]).is_file(), f
        assert f["caption"]
    for v in u["videos"]:
        assert v["url"].startswith("https://") and v["title"], v
    for a in u["animations"]:
        assert (ROOT / a["file"]).is_file(), a
    for f in u["films"]:
        assert (ROOT / f["file"]).is_file(), f
        assert 0 < f["seconds"] <= 120 and f["chapters"], f


def test_video_lists_fully_parsed():
    # every link item under '영상으로 보기' must come out as a video (plain-text notes are allowed)
    for path in UNIT_FILES:
        body = path.read_text(encoding="utf-8")
        items = [l for l in build_theory.section_lines(body, "영상으로 보기") if l.startswith("- [")]
        assert len(items) == len(UNITS[path.stem]["videos"]), path.name


def test_every_figure_is_used_once():
    used = [f["file"] for u in DATA["units"] for f in u["figures"]] + [f["file"] for f in DATA["overview"]["figures"]]
    on_disk = sorted(f"theory/figures/{p.name}" for p in (THEORY / "figures").glob("*.svg"))
    assert sorted(used) == on_disk
    assert len(used) == len(set(used))


@pytest.mark.parametrize("path", sorted((THEORY / "figures").glob("*.svg")), ids=lambda p: p.stem)
def test_figure_svg(path):
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.tag == SVG_NS + "svg"
    assert root.get("viewBox") and root.get("width") and root.get("height")
    assert "fig" in root.get("class", "").split()
    assert root.find(SVG_NS + "title") is not None and root.find(SVG_NS + "style") is not None
    assert "prefers-color-scheme:dark" in text
    assert "var(--cds-" not in text and "data-claude" not in text
    assert not re.search(r"(?:href|src)=\"(?!#)", text), "figures must not load anything"


def test_other_pages():
    for name in ("overview.md", "sources.md"):
        text = (THEORY / name).read_text(encoding="utf-8")
        assert text.startswith("# ") and "embedded content" not in text
    for f in DATA["floors"]:
        assert f["title"].startswith(f"{f['floor']}층 · ") and f["intro"]
