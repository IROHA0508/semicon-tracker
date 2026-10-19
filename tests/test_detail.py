"""Offline tests for the long summary (article page): pictures found in the article HTML, figure
drawing, the number check, the run loop with a fake Claude, and what publish/validate do with it."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from backend import bodies, config, detail, digest, feeds, figures, publish, store

from .test_summary import EN_TEXT, NOW, FakeLLM, card, data, queued, run, setup_queue  # noqa: F401 (data is a fixture)

HTML = ("<p>SK hynix announced today that it will invest $15 billion in its new M15X fab in Cheongju.</p>"
        "<figure><img src='/wp-content/uploads/fab.jpg' srcset='/a-300.jpg 300w, /a-1024.jpg 1024w' alt='M15X fab'>"
        "<figcaption>The M15X fab</figcaption></figure>"
        "<p>The company began supplying 12-high HBM4 samples to customers, with bandwidth above 2 TB/s.</p>"
        "<img src='https://news.skhynix.com/logo.png'><img src='https://cdn.example.com/emoji.gif'>"
        "<img src='https://cdn.example.com/tiny.jpg' width='20'><img src='https://cdn.example.com/chart.png'>"
        "<p>Operating profit rose 263% year over year to KRW 21.6 trillion in the third quarter.</p>") * 1


def test_marked_text_keeps_article_pictures_in_place():
    text, images = feeds.html_to_marked(HTML, "https://news.skhynix.com/en/a/")
    assert [i["src"] for i in images] == ["https://news.skhynix.com/a-1024.jpg", "https://cdn.example.com/chart.png"]
    assert images[0]["alt"] == "M15X fab" and images[0]["caption"] == "The M15X fab"
    lines = text.splitlines()
    assert lines.index("[그림 1]") == 1 and "[그림 2]" in lines
    assert "logo" not in text


COLUMNS = {"type": "columns", "title": "세 곳을 함께 최적화한 효과", "caption": "효과 한눈에",
           "columns": [{"name": "셀", "sub": "정밀한 전류", "lines": ["셀당 4단계"], "foot": "정밀"},
                       {"name": "배선", "sub": "전환 부담", "lines": ["효율 2배"], "foot": "함께 2.2배"}],
           "result": {"label": "기존 대비", "value": "처리량 약 10~20배"}}


def test_figures_draw_valid_svg_and_reject_overlong_text():
    svg = figures.render(COLUMNS, "t1")
    root = ET.fromstring(svg)
    assert root.get("class") == "fig" and "prefers-color-scheme:dark" in svg
    flow = {"type": "flow", "title": "데이터 길", "nodes": [{"name": "스토리지"}, {"name": "메모리", "accent": True}, {"name": "xPU"}],
            "edges": ["", "대역폭"], "rows": [{"label": "용량", "text": "더 큰 모델", "note": "부족하면 지연"}], "footer": "가깝게"}
    ET.fromstring(figures.render(flow, "t2"))
    with pytest.raises(figures.FigureError):
        figures.render({**COLUMNS, "columns": [{"name": "가" * 40}, {"name": "나"}]}, "t3")
    with pytest.raises(figures.FigureError):
        figures.render({**COLUMNS, "columns": COLUMNS["columns"][:1]}, "t4")


def long_detail(figure=None, lead=None, extra_p=None):
    para = "SK하이닉스는 청주 M15X 공장에 150억 달러를 투자한다고 밝혔습니다. " * 8
    blocks = [{"t": "h", "text": "투자 내용"}, {"t": "p", "text": para}, {"t": "img", "n": 1, "caption": "M15X 공장"},
              {"t": "h", "text": "HBM4 공급"}, {"t": "p", "text": "회사는 12단 HBM4 샘플을 고객사에 공급하기 시작했습니다. " * 4},
              {"t": "ul", "items": ["대역폭은 2TB/s 이상입니다.", "영업이익은 21조 6천억 원입니다."]}]
    if extra_p:
        blocks.append({"t": "p", "text": extra_p})
    if figure:
        blocks.append({"t": "fig"})
    return {"lead": lead or "SK하이닉스가 청주 M15X 공장에 150억 달러를 투자합니다. 12단 HBM4 샘플 공급도 시작했습니다.",
            "keyPoints": ["150억 달러 투자", "12단 HBM4 샘플", "영업이익 263% 증가"], "blocks": blocks, "figure": figure,
            "terms": [{"term": "HBM", "desc": "D램을 쌓아 대역폭을 넓힌 메모리"}], "studyUnits": ["4-5", "9-9"]}


class HtmlFinder:
    def find(self, item):
        return bodies.Body(EN_TEXT, "SK hynix", "feed", HTML)


@pytest.fixture()
def summarized(data, monkeypatch):
    monkeypatch.setattr(config, "DETAIL_DIR", data / "data" / "detail")
    monkeypatch.setattr(config, "DETAIL_STATE", data / "state" / "details.json")
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"), queued("b", "2026-10-01T10:00:00+09:00"))
    run(FakeLLM(card(), card()))
    return data


def details(llm, **kw):
    return detail.run(llm=llm, finder=HtmlFinder(), now=NOW, **kw)


def test_long_summary_places_every_picture_and_draws_the_figure(summarized):
    spec = {"type": "columns", "title": "투자와 제품", "caption": "한눈에",
            "columns": [{"name": "투자", "lines": ["M15X 150억 달러"], "foot": "청주"},
                        {"name": "제품", "lines": ["12단 HBM4"], "foot": "2TB/s 이상"}],
            "result": {"label": "실적", "value": "영업이익 263% 증가"}}
    report = details(FakeLLM(long_detail(figure=spec), long_detail()))
    assert [d["id"] for d in report["detailed"]] == ["skhynix-a", "skhynix-b"] and report["stoppedBy"] == "all done"
    d = json.loads((config.DETAIL_DIR / "skhynix-a.json").read_text(encoding="utf-8"))
    imgs = [b for b in d["blocks"] if b["t"] == "img"]
    assert [i["src"] for i in imgs] == ["https://news.skhynix.com/a-1024.jpg", "https://cdn.example.com/chart.png"]
    assert imgs[0]["caption"] == "M15X 공장" and imgs[1]["caption"] == "원문 그림 2"   # left out by Claude: added
    assert imgs[0]["credit"] == "SK하이닉스 뉴스룸"
    fig = [b for b in d["blocks"] if b["t"] == "fig"]
    assert fig and (summarized / fig[0]["file"].replace("data/", "data/", 1)).name == "skhynix-a-1.svg"
    assert (config.DETAIL_DIR / "figs" / "skhynix-a-1.svg").exists()
    assert d["studyUnits"] == ["4-5"] and d["translated"] is True and "새로 그린" in d["basis"]
    b = json.loads((config.DETAIL_DIR / "skhynix-b.json").read_text(encoding="utf-8"))
    assert not any(x["t"] == "fig" for x in b["blocks"]) and "새로 그린" not in b["basis"]
    # the article page knows which cards have a long summary
    publish.build(now=NOW)
    m = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    assert all(i.get("detail") for i in m["index"])
    # nothing left to do on the next run
    assert detail.run(llm=FakeLLM(), finder=HtmlFinder(), now=NOW)["stoppedBy"] == "nothing to do"


def test_wrong_numbers_are_retried_then_dropped(summarized):
    bad = long_detail(extra_p="공장 투자액은 15억 달러입니다. 생산은 계속됩니다.",
                      figure=dict(COLUMNS, result={"label": "투자", "value": "999억 달러"}))
    llm = FakeLLM(bad, bad, long_detail(), long_detail())
    details(llm, limit=1)
    assert "다음 수치를 원문에서 찾지 못했습니다" in llm.prompts[1]
    d = json.loads((config.DETAIL_DIR / "skhynix-a.json").read_text(encoding="utf-8"))
    texts = json.dumps(d["blocks"], ensure_ascii=False)
    assert "15억 달러입니다" not in texts and "생산은 계속됩니다." in texts
    assert not any(b["t"] == "fig" for b in d["blocks"])
    assert "그림: 세 곳을 함께 최적화한 효과" in d["checks"]["removed"]


def test_failures_are_counted_and_given_up(summarized):
    short = {"lead": "짧습니다.", "keyPoints": [], "blocks": [{"t": "p", "text": "짧습니다."}], "figure": None,
             "terms": [], "studyUnits": []}
    for k in range(detail.MAX_ATTEMPTS):
        report = details(FakeLLM(short), limit=1)
        assert "skhynix-a" in report["failed"]
    assert report["gaveUp"][0]["id"] == "skhynix-a"
    report = details(FakeLLM(long_detail()), limit=1)
    assert [d["id"] for d in report["detailed"]] == ["skhynix-b"]


def test_validate_checks_detail_files(summarized):
    details(FakeLLM(long_detail(), long_detail()))
    publish.build(now=NOW)
    assert publish.validate() == []
    path = config.DETAIL_DIR / "skhynix-a.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    d["blocks"].append({"t": "img", "src": "http://insecure/x.jpg"})
    d["blocks"].append({"t": "fig", "file": "data/detail/figs/none.svg"})
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    problems = publish.validate()
    assert any("https가 아님" in p for p in problems) and any("그림 파일 없음" in p for p in problems)
