"""Build animations/index.html from animations/catalog.json.

Run after adding a page to the catalog:  python tools/build_animation_index.py
The page groups animations by floor (the first digit of the unit code) in unit order.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANIM = ROOT / "animations"
FLOORS = {
    "0": "0층 · 입문",
    "1": "1층 · 기초 전기와 물리",
    "2": "2층 · 소자",
    "3": "3층 · 제조 공정",
    "4": "4층 · 첨단 기술",
    "5": "5층 · 산업과 시장",
}

HEAD = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>반도체 동작·공정 애니메이션</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="player.css">
<style>
  .toc { display: flex; flex-wrap: wrap; gap: 8px; }
  .toc a { font: 500 13px/1 var(--font-sans); color: var(--ink); text-decoration: none; border: 1px solid var(--line-strong); border-radius: 999px; padding: 8px 12px; background: var(--surface); }
  .toc a:hover { border-color: var(--accent); color: var(--accent); }
  .toc a span { font-family: var(--font-mono); color: var(--muted); margin-left: 4px; }
  .floor { display: grid; gap: 10px; scroll-margin-top: 16px; }
  .floor > h2 { margin: 0; display: flex; gap: 10px; align-items: baseline; font: 700 17px/1.4 var(--font-sans); }
  .floor > h2 span { font: 500 12px var(--font-mono); color: var(--muted); letter-spacing: .04em; }
  .cards { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); }
  .card {
    display: grid; gap: 8px; align-content: start; grid-template-rows: auto auto 1fr auto;
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 14px 16px; color: var(--ink); text-decoration: none;
    transition: border-color .2s, transform .2s;
  }
  .card:hover { border-color: var(--accent); transform: translateY(-2px); }
  .card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .card .top { display: flex; gap: 8px; align-items: center; justify-content: space-between; }
  .card .unit { font: 600 12px/1 var(--font-mono); color: var(--accent); border: 1px solid var(--accent); border-radius: 999px; padding: 4px 8px; }
  .card .meta { font: 500 12px/1 var(--font-mono); color: var(--muted); }
  .card h3 { margin: 0; font: 700 17px/1.35 var(--font-sans); text-wrap: balance; }
  .card p { margin: 0; color: var(--muted); font-size: 13.5px; line-height: 1.55; }
  .card .modes { display: flex; flex-wrap: wrap; gap: 4px; }
  .card .modes span { font-size: 12px; color: var(--muted); background: var(--bg); border-radius: 4px; padding: 3px 6px; }
  kbd { font: 500 12px var(--font-mono); border: 1px solid var(--line-strong); border-bottom-width: 2px; border-radius: 4px; padding: 1px 5px; background: var(--surface); }
  @media (prefers-reduced-motion: reduce) { .card { transition: none; } .card:hover { transform: none; } }
</style>
</head>
<body>
<main class="anim">
  <header class="anim-head">
    <div class="eyebrow"><span>반도체 뉴스 트래커 · 이론</span></div>
    <h1>반도체 동작·공정 애니메이션</h1>
    <p class="lead">이론 원고의 단원을 단계별로 움직이는 그림으로 만들었습니다. 각 단계는 원고 문장과 맞춰 두었고, <kbd>←</kbd> <kbd>→</kbd> 키로 단계를 넘기고 <kbd>Space</kbd>로 자동 재생합니다. 지금 {count}개입니다.</p>
  </header>
"""

FOOT = """
  <p class="foot">모든 그림은 개념도입니다. 비율과 순서는 이해를 돕기 위해 단순화했습니다.</p>
</main>
</body>
</html>
"""


def unit_key(code: str) -> tuple[int, int]:
    a, _, b = code.partition("-")
    return int(a), int(b)


def build() -> str:
    catalog = json.loads((ANIM / "catalog.json").read_text(encoding="utf-8"))
    items = sorted(catalog["animations"], key=lambda a: unit_key(a["unit"]))
    floors: dict[str, list[dict]] = {}
    for a in items:
        floors.setdefault(a["unit"].split("-")[0], []).append(a)
    out = [HEAD.replace("{count}", str(len(items)))]
    out.append('  <nav class="toc" aria-label="층 바로가기">')
    for f, rows in floors.items():
        out.append(f'    <a href="#floor-{f}">{html.escape(FLOORS.get(f, f + "층"))}<span>{len(rows)}</span></a>')
    out.append("  </nav>")
    for f, rows in floors.items():
        out.append(f'\n  <section class="floor" id="floor-{f}">')
        out.append(f'    <h2>{html.escape(FLOORS.get(f, f + "층"))} <span>{len(rows)}개</span></h2>')
        out.append('    <div class="cards">')
        for a in rows:
            steps = sum(m["steps"] for m in a["modes"])
            modes = "".join(f"<span>{html.escape(m['label'])}</span>" for m in a["modes"] if m["id"] != "main")
            out.append(f'      <a class="card" href="{a["file"]}">')
            out.append(f'        <div class="top"><span class="unit">{a["unit"]}</span><span class="meta">{steps}단계</span></div>')
            out.append(f'        <h3>{html.escape(a["title"])}</h3>')
            out.append(f'        <p>{html.escape(a["summary"])}</p>')
            out.append(f'        <div class="modes">{modes}</div>' if modes else '        <div class="modes"></div>')
            out.append("      </a>")
        out.append("    </div>")
        out.append("  </section>")
    out.append(FOOT)
    return "\n".join(out)


if __name__ == "__main__":
    page = build()
    (ANIM / "index.html").write_text(page, encoding="utf-8")
    print("wrote animations/index.html")
