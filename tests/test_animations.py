"""Checks for the step animations in animations/: the catalog matches the files, every page uses the
shared player, and pages load nothing from outside except Google Fonts. Rendering itself is checked
by hand with a headless browser (see animations/README.md).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANIM = ROOT / "animations"
CATALOG = json.loads((ANIM / "catalog.json").read_text(encoding="utf-8"))
UNITS = {u["code"] for u in json.loads((ROOT / "data" / "units.json").read_text(encoding="utf-8"))["units"]}
PAGES = CATALOG["animations"]


def test_catalog_units_exist():
    for entry in PAGES + CATALOG["planned"]:
        assert entry["unit"] in UNITS, entry


def test_catalog_ids_unique():
    ids = [a["id"] for a in PAGES]
    assert len(ids) == len(set(ids))
    assert not {a["unit"] for a in PAGES} & {p["unit"] for p in CATALOG["planned"]}


@pytest.mark.parametrize("entry", PAGES, ids=[a["id"] for a in PAGES])
def test_page_shape(entry):
    html = (ANIM / entry["file"]).read_text(encoding="utf-8")
    assert html.lower().startswith("<!doctype html>")
    assert '<html lang="ko">' in html
    assert 'name="viewport"' in html
    assert re.search(r"<title>[^<]+</title>", html)
    assert '<link rel="stylesheet" href="player.css">' in html
    assert '<script src="player.js"></script>' in html
    assert 'href="./"' in html, "back link to the animation list"
    assert f'<span class="unit-chip">{entry["unit"]}</span>' in html
    # step count in the page matches the catalog
    assert html.count("{ short: ") == sum(m["steps"] for m in entry["modes"])
    # mode ids in the page match the catalog (single-mode pages use "main")
    page_modes = re.findall(r'^\s+id: "(\w+)", label: "', html, flags=re.M)
    assert page_modes == [m["id"] for m in entry["modes"] if m["id"] != "main"]


@pytest.mark.parametrize("name", sorted(p.name for p in ANIM.glob("*.html")))
def test_no_outside_resources(name):
    html = (ANIM / name).read_text(encoding="utf-8")
    for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', html):
        assert url.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")), url


def test_index_links_every_page():
    html = (ANIM / "index.html").read_text(encoding="utf-8")
    for entry in PAGES:
        assert f'href="{entry["file"]}"' in html
    for planned in CATALOG["planned"]:
        assert f"<b>{planned['unit']}</b>" in html


def test_player_has_no_dependencies():
    js = (ANIM / "player.js").read_text(encoding="utf-8")
    assert "import " not in js and "require(" not in js
    assert "window.StepPlayer" in js
