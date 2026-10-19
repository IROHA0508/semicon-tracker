"""Checks for the site page (index.html): it reads the data files that exist, loads nothing from
outside except fonts, its script parses, and the data it joins together (news cards → units →
animations) all resolves. Rendering is checked by hand with a headless browser (README '화면')."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
THEORY = json.loads((ROOT / "data" / "theory.json").read_text(encoding="utf-8"))
UNITS = {u["code"]: u for u in THEORY["units"]}


class _Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.scripts = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self._in_script = tag == "script"

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.scripts.append(data)


PAGE = _Collect()
PAGE.feed(INDEX)


def test_page_shape():
    assert INDEX.lower().startswith("<!doctype html>")
    assert '<html lang="ko">' in INDEX
    assert 'name="viewport"' in INDEX and "viewport-fit=cover" in INDEX
    assert re.search(r"<title>[^<]+</title>", INDEX)
    assert 'name="robots" content="noindex, nofollow"' in INDEX
    for tab in ("news", "theory", "sources"):
        assert f'href="#{tab}" data-tab="{tab}"' in INDEX


def test_reads_existing_data():
    for path in re.findall(r'getJSON\("([^"]+)"\)', INDEX):
        assert (ROOT / path).is_file(), path
    assert {"data/manifest.json", "data/theory.json", "data/tags.json"} <= set(re.findall(r'getJSON\("([^"]+)"\)', INDEX))


def test_only_fonts_from_outside():
    for tag, attrs in PAGE.tags:
        url = attrs.get("src") or (attrs.get("href") if tag == "link" else None)
        if not url or not url.startswith("http") or attrs.get("rel") == "preconnect":
            continue
        assert tag == "link", f"no outside scripts or images: {url}"
        assert url.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com",
                               "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v")), url
    assert not any(t == "script" and a.get("src") for t, a in PAGE.tags)


def test_script_parses():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    code = "\n".join(PAGE.scripts)
    res = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=code,
                         capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr


def test_cards_link_to_units():
    for item in MANIFEST["index"]:
        assert item["kind"] in ("press", "fact", "tech"), item["id"]
        assert item["company"] in ("samsung", "skhynix"), item["id"]
        for code in item.get("relatedUnits", []):
            assert code in UNITS, (item["id"], code)
    assert {s["key"] for s in MANIFEST["sources"]} >= {i["source"] for i in MANIFEST["index"]}


def test_units_point_to_files():
    for u in THEORY["units"]:
        assert (ROOT / u["file"]).is_file(), u["file"]
        for a in u["animations"]:
            # the unit page embeds the animation with ?embed; the player hides the page header then
            assert (ROOT / a["file"]).is_file(), a["file"]
        for f in u["films"]:
            assert (ROOT / f["file"]).is_file(), f["file"]
    assert (ROOT / THEORY["overview"]["file"]).is_file()
    assert (ROOT / THEORY["sources"]["file"]).is_file()


def test_embed_mode_in_player():
    js = (ROOT / "animations" / "player.js").read_text(encoding="utf-8")
    assert "st-anim-height" in js and "st-anim-height" in INDEX
    assert '"?embed"' in INDEX and "embed" in js


def test_deploy_files():
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert cfg["cleanUrls"] is True
    ignored = (ROOT / ".vercelignore").read_text(encoding="utf-8").split()
    assert {"backend/", "tests/", "tools/", ".github/"} <= set(ignored)
