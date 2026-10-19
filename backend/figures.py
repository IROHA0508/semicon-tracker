"""Draw the explanatory figure of a long article summary as a static SVG, from a small spec Claude writes.

Two layouts only, so every figure has the same look as the theory figures (same colour names, light
and dark themes, Pretendard) and nothing depends on hand-placed coordinates:

  columns: 2-4 boxes side by side (name, sub line, up to 4 lines, a foot line), arrows into one
           result box (label + value). For "A, B and C together gave X".
  flow:    2-4 boxes in a row joined by arrows (optional label on each arrow), then up to 4 rows of
           label / text / note, then a footer box. For "data goes from A to B to C, and these are
           the problems / steps".

Text is measured roughly (Hangul ~1 em, Latin ~0.55 em); a line that does not fit is wrapped once and
a figure that still does not fit is rejected (FigureError), so the caller leaves it out.
"""
from __future__ import annotations

from html import escape

STYLE = """.fig{--fig-ink:#1a1f26;--fig-quiet:#5a6472;--fig-edge:#8a94a0;--fig-grid:#c9d0d8;--fig-tint:#eef1f4;--fig-acc:#b5541a;--fig-acc2:#376797;font-family:"Pretendard Variable",Pretendard,"Noto Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}@media (prefers-color-scheme:dark){.fig{--fig-ink:#e5e8ec;--fig-quiet:#9ba5b2;--fig-edge:#6f7a87;--fig-grid:#3a414a;--fig-tint:#20252c;--fig-acc:#ef8a4c;--fig-acc2:#7ea8d6}}:root[data-theme="dark"] .fig{--fig-ink:#e5e8ec;--fig-quiet:#9ba5b2;--fig-edge:#6f7a87;--fig-grid:#3a414a;--fig-tint:#20252c;--fig-acc:#ef8a4c;--fig-acc2:#7ea8d6}:root[data-theme="light"] .fig{--fig-ink:#1a1f26;--fig-quiet:#5a6472;--fig-edge:#8a94a0;--fig-grid:#c9d0d8;--fig-tint:#eef1f4;--fig-acc:#b5541a;--fig-acc2:#376797}.fig .f-ink{fill:var(--fig-ink)}.fig .s-ink{stroke:var(--fig-ink)}.fig .f-quiet{fill:var(--fig-quiet)}.fig .s-quiet{stroke:var(--fig-quiet)}.fig .f-edge{fill:var(--fig-edge)}.fig .s-edge{stroke:var(--fig-edge)}.fig .f-grid{fill:var(--fig-grid)}.fig .s-grid{stroke:var(--fig-grid)}.fig .f-tint{fill:var(--fig-tint)}.fig .s-tint{stroke:var(--fig-tint)}.fig .f-acc{fill:var(--fig-acc)}.fig .s-acc{stroke:var(--fig-acc)}.fig .f-acc2{fill:var(--fig-acc2)}.fig .s-acc2{stroke:var(--fig-acc2)}"""
W = 760


class FigureError(ValueError):
    """The spec cannot be drawn cleanly (too much text, wrong shape)."""


def text_width(s: str, size: float) -> float:
    w = 0.0
    for ch in s:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF or ch in "①②③④⑤·→←↑↓×÷":
            w += 0.94
        elif ch == " ":
            w += 0.3
        elif ch.isupper() or ch.isdigit() or ch in "%~":
            w += 0.62
        else:
            w += 0.52
    return w * size


def wrap(s: str, size: float, width: float, max_lines: int = 2) -> list[str]:
    s = " ".join(str(s or "").split())
    if text_width(s, size) <= width:
        return [s] if s else []
    lines, cur = [], ""
    for word in s.split(" "):
        cand = (cur + " " + word).strip()
        if text_width(cand, size) <= width:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        cur = word
        while text_width(cur, size) > width:   # one very long word: cut by characters
            k = len(cur)
            while k > 1 and text_width(cur[:k], size) > width:
                k -= 1
            lines.append(cur[:k])
            cur = cur[k:]
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        raise FigureError(f"글이 너무 김: {s[:40]}")
    return lines


def _t(x, y, s, cls="f-ink", size=13, anchor="start", weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return f'<text x="{x:.0f}" y="{y:.0f}" class="{cls}" font-size="{size}" text-anchor="{anchor}"{w}>{escape(s)}</text>'


def _rect(x, y, w, h, cls="f-tint s-edge", rx=8):
    return f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx}" class="{cls}" stroke-width="1.2"/>'


def _arrow(x1, y1, x2, y2, mid, cls="s-edge"):
    return f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="{cls}" stroke-width="1.5" marker-end="url(#{mid})"/>'


def _svg(h, label, body, mid):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h:.0f}" viewBox="0 0 {W} {h:.0f}" role="img" '
            f'aria-label="{escape(label)}" font-size="13" class="fig"><title>{escape(label)}</title><style>{STYLE}</style>'
            f'<defs><marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
            f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="f-edge"/></marker></defs>{body}</svg>\n')


def _title(spec, body):
    lines = wrap(spec.get("title", ""), 16, W - 40, 2)
    if not lines:
        raise FigureError("제목 없음")
    for k, line in enumerate(lines):
        body.append(_t(20, 30 + k * 22, line, size=16, weight=700))
    return 30 + (len(lines) - 1) * 22 + 20


def columns(spec: dict, mid: str) -> str:
    cols = spec.get("columns") or []
    if not 2 <= len(cols) <= 4:
        raise FigureError("columns는 2~4개")
    body: list[str] = []
    y0 = _title(spec, body)
    gap = 15
    cw = (W - 40 - gap * (len(cols) - 1)) / len(cols)
    inner = cw - 28
    laid = []
    for c in cols:
        name = wrap(c.get("name", ""), 15, inner, 1)
        sub = wrap(c.get("sub", ""), 12.5, inner, 2)
        lines = []
        for line in (c.get("lines") or [])[:4]:
            lines += wrap(line, 12.5, inner, 2)
        foot = wrap(c.get("foot", ""), 12.5, inner, 2)
        if not name:
            raise FigureError("열 이름 없음")
        laid.append((name, sub, lines, foot))
    sub_h = max(len(l[1]) for l in laid) * 18
    lines_h = max(len(l[2]) for l in laid) * 24
    foot_h = max(len(l[3]) for l in laid) * 20
    box_h = 26 + 16 + sub_h + 14 + lines_h + (16 + foot_h if foot_h else 0) + 10
    top = y0
    for i, (name, sub, lines, foot) in enumerate(laid):
        x = 20 + i * (cw + gap)
        body.append(_rect(x, top, cw, box_h))
        y = top + 26
        body.append(_t(x + 14, y, name[0], cls="f-acc", size=15, weight=700))
        y += 20
        for line in sub:
            body.append(_t(x + 14, y, line, cls="f-quiet", size=12.5)); y += 18
        y = top + 26 + 20 + sub_h + 16
        for line in lines:
            body.append(_t(x + 14, y, line, size=12.5)); y += 24
        if foot:
            fy = top + 26 + 20 + sub_h + 16 + lines_h - 6
            body.append(f'<line x1="{x+14:.0f}" y1="{fy:.0f}" x2="{x+cw-14:.0f}" y2="{fy:.0f}" class="s-grid" stroke-width="1"/>')
            for k, line in enumerate(foot):
                body.append(_t(x + 14, fy + 22 + k * 20, line, cls="f-acc2", size=12.5, weight=600))
    y = top + box_h
    res = spec.get("result") or {}
    if res.get("value"):
        rw = 520
        value = wrap(res["value"], 17, rw - 40, 2)
        label = wrap(res.get("label", ""), 12.5, rw - 40, 1)
        rh = 22 + len(label) * 20 + len(value) * 26 + 6
        ry = y + 46
        for i in range(len(laid)):
            cx = 20 + i * (cw + gap) + cw / 2
            body.append(_arrow(cx, y + 4, W / 2, ry - 4, mid))
        body.append(_rect((W - rw) / 2, ry, rw, rh, cls="f-tint s-acc", rx=10))
        yy = ry + 26
        for line in label:
            body.append(_t(W / 2, yy, line, cls="f-quiet", size=12.5, anchor="middle")); yy += 22
        for line in value:
            body.append(_t(W / 2, yy + 4, line, cls="f-acc", size=17, anchor="middle", weight=700)); yy += 26
        y = ry + rh
    for line in wrap(spec.get("note", ""), 11.5, W - 40, 2):
        y += 22
        body.append(_t(20, y, line, cls="f-quiet", size=11.5))
    return _svg(y + 14, spec.get("title", ""), "".join(body), mid)


def flow(spec: dict, mid: str) -> str:
    nodes = spec.get("nodes") or []
    if not 2 <= len(nodes) <= 4:
        raise FigureError("nodes는 2~4개")
    body: list[str] = []
    top = _title(spec, body) + 10
    gap = 74
    nw = (W - 60 - gap * (len(nodes) - 1)) / len(nodes)
    laid = []
    for n in nodes:
        name = wrap(n.get("name", ""), 16, nw - 20, 1)
        if not name:
            raise FigureError("상자 이름 없음")
        laid.append((name, wrap(n.get("sub", ""), 12.5, nw - 20, 1), wrap(n.get("desc", ""), 12.5, nw - 20, 2), bool(n.get("accent"))))
    nh = 36 + max(len(l[1]) for l in laid) * 22 + max(len(l[2]) for l in laid) * 20 + 14
    edges = spec.get("edges") or []
    for i, (name, sub, desc, acc) in enumerate(laid):
        x = 30 + i * (nw + gap)
        body.append(_rect(x, top, nw, nh, cls="f-tint s-acc" if acc else "f-tint s-edge"))
        y = top + 32
        body.append(_t(x + nw / 2, y, name[0], cls="f-acc" if acc else "f-ink", size=16, anchor="middle", weight=700))
        y += 22
        for line in sub:
            body.append(_t(x + nw / 2, y, line, cls="f-quiet", size=12.5, anchor="middle")); y += 22
        for line in desc:
            body.append(_t(x + nw / 2, y, line, size=12.5, anchor="middle")); y += 20
        if i < len(laid) - 1:
            ay = top + nh / 2
            label = edges[i] if i < len(edges) else ""
            body.append(_arrow(x + nw + 4, ay, x + nw + gap - 4, ay, mid, cls="s-acc" if label else "s-edge"))
            if label:
                for k, line in enumerate(wrap(label, 12, gap - 4, 2)):
                    body.append(_t(x + nw + gap / 2, ay - 10 - 14 * (len(wrap(label, 12, gap - 4, 2)) - 1 - k), line,
                                   cls="f-acc", size=12, anchor="middle", weight=700))
    y = top + nh + 18
    rows = (spec.get("rows") or [])[:4]
    for r in rows:
        label = wrap(r.get("label", ""), 13.5, 130, 1)
        text = wrap(r.get("text", ""), 13, 250, 2)
        note = wrap(r.get("note", ""), 12.5, 330, 2)
        h = max(len(text), len(note), 1) * 20
        y += 26
        if label:
            body.append(_t(30, y, label[0], cls="f-acc", size=13.5, weight=700))
        for k, line in enumerate(text):
            body.append(_t(170, y + k * 20, line, size=13))
        for k, line in enumerate(note):
            body.append(_t(410, y + k * 20, line, cls="f-quiet", size=12.5))
        y += h - 20 + 8
    footer = wrap(spec.get("footer", ""), 13, W - 100, 2)
    if footer:
        y += 22
        fh = 24 + len(footer) * 20
        body.append(_rect(30, y, W - 60, fh))
        for k, line in enumerate(footer):
            body.append(_t(W / 2, y + 28 + k * 20, line, size=13, anchor="middle"))
        y += fh
    for line in wrap(spec.get("note", ""), 11.5, W - 40, 2):
        y += 22
        body.append(_t(20, y, line, cls="f-quiet", size=11.5))
    return _svg(y + 16, spec.get("title", ""), "".join(body), mid)


def render(spec: dict, mid: str) -> str:
    kind = spec.get("type")
    if kind == "columns":
        return columns(spec, mid)
    if kind == "flow":
        return flow(spec, mid)
    raise FigureError(f"모르는 그림 종류: {kind}")


def texts(spec: dict) -> list[str]:
    """Every piece of text in a spec (for the number check)."""
    out = [spec.get("title", ""), spec.get("note", ""), spec.get("footer", "")]
    for c in spec.get("columns") or []:
        out += [c.get("name", ""), c.get("sub", ""), c.get("foot", ""), *(c.get("lines") or [])]
    res = spec.get("result") or {}
    out += [res.get("label", ""), res.get("value", "")]
    for n in spec.get("nodes") or []:
        out += [n.get("name", ""), n.get("sub", ""), n.get("desc", "")]
    out += list(spec.get("edges") or [])
    for r in spec.get("rows") or []:
        out += [r.get("label", ""), r.get("text", ""), r.get("note", "")]
    return [t for t in out if t]
