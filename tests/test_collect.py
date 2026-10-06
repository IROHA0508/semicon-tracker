"""Offline tests for the collector. Run: python -m pytest tests -q

The feed pages below copy the structure of the real WordPress feeds (checked on 2026-10-06):
SK hynix English category feeds and the Samsung Semiconductor Korean newsroom feed.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from backend import collect, config, feeds, store

SK_FACT, SK_TECH, SK_PRESS, SAMSUNG = config.SOURCES

NOW = datetime(2026, 10, 7, 7, 10, tzinfo=feeds.KST)


def sk_item(slug: str, title: str, pub: str, *cats: str) -> str:
    tags = "".join(f"<category><![CDATA[{c}]]></category>" for c in cats)
    return (f"<item><title>{title}</title><link>https://news.skhynix.com/en/{slug}/</link>"
            f"<dc:creator><![CDATA[SK hynix]]></dc:creator><pubDate>{pub}</pubDate>{tags}"
            f"<guid isPermaLink=\"false\">https://news.skhynix.com/en/?p=1</guid>"
            f"<description><![CDATA[Short teaser that must not be stored.]]></description>"
            f"<content:encoded><![CDATA[<p>Full article body that must not be stored.</p>]]></content:encoded></item>")


def sk_feed(channel: str, *items: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
            'xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<channel><title>{channel} &#8211; SK hynix Newsroom</title><link>https://news.skhynix.com/en</link>"
            f"<description></description><language>en-US</language>{''.join(items)}</channel></rss>")


def ss_item(slug: str, title: str, pub: str, *cats: str) -> str:
    tags = "".join(f"<category><![CDATA[{c}]]></category>" for c in cats)
    return (f"<item><title>{title}</title>"
            f"<link>https://news.samsungsemiconductor.com/kr/{slug}/?utm_source=rss&amp;utm_medium=direct</link>"
            f"<pubDate>{pub}</pubDate><dc:creator><![CDATA[삼성전자 반도체]]></dc:creator>{tags}"
            f"<description><![CDATA[<p>요약문</p>]]></description>"
            f"<content:encoded><![CDATA[<p>본문 전체</p>]]></content:encoded></item>")


def ss_feed(*items: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
            'xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<channel><title>삼성전자 반도체 뉴스룸</title><link>https://news.samsungsemiconductor.com/kr</link>"
            f"<language>ko-KR</language>{''.join(items)}</channel></rss>")


class FakeFetch:
    """Serves feed pages from a dict {(source key, page): xml | None | Exception}; missing pages are 404."""

    def __init__(self, pages: dict):
        self.pages = pages
        self.calls: list[tuple[str, int]] = []

    def __call__(self, source: config.Source, page: int):
        self.calls.append((source.key, page))
        value = self.pages.get((source.key, page))
        if isinstance(value, Exception):
            raise value
        if value is None:
            return None
        return feeds.parse_feed(value, source)


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SEEN_FILE", tmp_path / "seen.json")
    monkeypatch.setattr(config, "QUEUE_FILE", tmp_path / "queue.json")
    monkeypatch.setattr(config, "REPORT_FILE", tmp_path / "last-run.json")
    monkeypatch.setattr(config, "START_DATE", date(2026, 1, 1))
    monkeypatch.setattr(config, "MAX_PAGES", 25)
    return tmp_path


def run(fetch, sources=(SK_FACT,), now=NOW, **kw):
    return collect.run(fetch=fetch, sources=sources, sleep=None, now=now, **kw)


# ---------------------------------------------------------------- parsing


def test_parse_sk_feed_converts_to_korean_time_and_cleans_title():
    xml = sk_feed("FACT",
                  sk_item("fact-11", "Clarification Regarding Recent Media Reports on Solidigm",
                          "Thu, 01 Oct 2026 01:22:33 +0000", "FACT", "semiconductor industry"),
                  sk_item("fact-10", "SK hynix&#8217;s Position on Reports",
                          "Wed, 16 Sep 2026 16:30:00 +0000", "FACT"))
    items = feeds.parse_feed(xml, SK_FACT)
    assert [i.title for i in items] == ["Clarification Regarding Recent Media Reports on Solidigm",
                                        "SK hynix’s Position on Reports"]
    assert items[0].url == "https://news.skhynix.com/en/fact-11/"
    assert items[0].published.isoformat() == "2026-10-01T10:22:33+09:00"
    # 16:30 UTC on Sep 16 is already Sep 17 in Korea.
    assert items[1].published.date() == date(2026, 9, 17)
    assert items[0].categories == ["FACT", "semiconductor industry"]


def test_parse_rejects_non_feed():
    with pytest.raises(feeds.FeedError):
        feeds.parse_feed("<html><body>Access denied</body></html>", SK_FACT)


def test_samsung_link_loses_utm_and_gets_hashed_id():
    slug = "%ec%82%bc%ec%84%b1%ec%a0%84%ec%9e%90"
    items = feeds.parse_feed(ss_feed(ss_item(slug, "삼성전자, ASML과 차세대 반도체 제조 협력 확대",
                                             "Tue, 08 Sep 2026 15:03:02 +0000", "보도자료", "프레스센터")), SAMSUNG)
    url = items[0].url
    assert url == f"https://news.samsungsemiconductor.com/kr/{slug}/"
    nid = feeds.make_id("samsung", url)
    assert nid.startswith("samsung-") and len(nid) == len("samsung-") + 10
    # The same page linked with upper-case percent escapes is the same article.
    assert nid == feeds.make_id("samsung", f"https://news.samsungsemiconductor.com/kr/{slug.upper()}/")
    assert feeds.make_id("skhynix", "https://news.skhynix.com/en/fact-11/") == "skhynix-fact-11"


def test_samsung_category_rules():
    assert feeds.classify(SAMSUNG, ["보도자료", "프레스센터", "ASML"]) == ("보도자료", "press")
    assert feeds.classify(SAMSUNG, ["기술", "반도체+", "UFS"]) == ("기술", "tech")
    assert feeds.classify(SAMSUNG, ["문화", "Fab"]) is None
    assert feeds.classify(SAMSUNG, ["ESG", "수자원"]) is None
    assert feeds.classify(SK_FACT, ["anything"]) == ("FACT", "fact")


def test_page_urls():
    assert feeds.page_url(SK_PRESS, 1) == "https://news.skhynix.com/en/category/press/feed/"
    assert feeds.page_url(SK_PRESS, 3) == "https://news.skhynix.com/en/category/press/feed/?paged=3"


# ---------------------------------------------------------------- walking pages


def backfill_pages():
    return {
        ("sk-fact", 1): sk_feed("FACT",
                                sk_item("fact-11", "Solidigm", "Thu, 01 Oct 2026 01:22:33 +0000", "FACT"),
                                sk_item("fact-10", "Intel talks", "Wed, 16 Sep 2026 10:01:11 +0000", "FACT")),
        ("sk-fact", 2): sk_feed("FACT",
                                sk_item("fact-07", "Chungcheong", "Thu, 02 Jul 2026 02:26:25 +0000", "FACT"),
                                sk_item("2026-market-outlook", "2026 Outlook", "Mon, 05 Jan 2026 00:00:00 +0000", "FACT")),
        ("sk-fact", 3): sk_feed("FACT",
                                sk_item("fact-02", "Late 2025", "Tue, 30 Dec 2025 01:00:00 +0000", "FACT"),
                                sk_item("fact-01", "Mid 2025", "Mon, 02 Jun 2025 01:00:00 +0000", "FACT")),
        ("sk-fact", 4): sk_feed("FACT", sk_item("fact-00", "2024", "Mon, 03 Jun 2024 01:00:00 +0000", "FACT")),
    }


def test_first_run_walks_back_to_start_date_and_stops(state):
    fetch = FakeFetch(backfill_pages())
    report = run(fetch)
    assert fetch.calls == [("sk-fact", 1), ("sk-fact", 2), ("sk-fact", 3)]  # page 4 is never read
    queue = store.load_queue()["items"]
    assert [i["id"] for i in queue] == ["skhynix-fact-11", "skhynix-fact-10", "skhynix-fact-07",
                                        "skhynix-2026-market-outlook"]
    assert report["sources"]["sk-fact"]["older"] == 2
    assert report["sources"]["sk-fact"]["stoppedBy"] == "reached 2026-01-01"
    assert report["backfillDone"] == {"sk-fact": True}
    assert report["errors"] == {}
    assert json.loads(config.REPORT_FILE.read_text(encoding="utf-8"))["queueSize"] == 4


def test_later_run_reads_only_until_known_articles(state):
    pages = backfill_pages()
    run(FakeFetch(pages))
    pages[("sk-fact", 1)] = sk_feed("FACT",
                                    sk_item("fact-12", "New statement", "Tue, 06 Oct 2026 23:30:00 +0000", "FACT"),
                                    sk_item("fact-11", "Solidigm", "Thu, 01 Oct 2026 01:22:33 +0000", "FACT"))
    fetch = FakeFetch(pages)
    report = run(fetch)
    assert fetch.calls == [("sk-fact", 1)]
    assert [a["id"] for a in report["added"]] == ["skhynix-fact-12"]
    assert report["added"][0]["date"] == "2026-10-07"
    assert store.load_queue()["items"][0]["id"] == "skhynix-fact-12"


def test_failure_midway_is_reported_and_backfill_resumes(state):
    pages = backfill_pages()
    pages[("sk-fact", 2)] = ConnectionError("reset by peer")
    report = run(FakeFetch(pages))
    assert "sk-fact" in report["errors"] and "page 2" in report["errors"]["sk-fact"]
    assert report["backfillDone"] == {"sk-fact": False}
    assert len(store.load_queue()["items"]) == 2

    # Next run: page 1 is all known, but the backfill is not done, so it keeps walking.
    pages = backfill_pages()
    fetch = FakeFetch(pages)
    report = run(fetch)
    assert fetch.calls == [("sk-fact", 1), ("sk-fact", 2), ("sk-fact", 3)]
    assert report["errors"] == {}
    assert [a["id"] for a in report["added"]] == ["skhynix-fact-07", "skhynix-2026-market-outlook"]
    assert report["backfillDone"] == {"sk-fact": True}


def test_missing_page_means_end_of_feed(state):
    pages = {("sk-fact", 1): sk_feed("FACT", sk_item("fact-11", "Solidigm", "Thu, 01 Oct 2026 01:22:33 +0000"))}
    fetch = FakeFetch(pages)
    report = run(fetch)
    assert fetch.calls == [("sk-fact", 1), ("sk-fact", 2)]
    assert report["sources"]["sk-fact"]["stoppedBy"] == "end of feed"
    assert report["backfillDone"] == {"sk-fact": True}


def test_page_limit(state, monkeypatch):
    monkeypatch.setattr(config, "MAX_PAGES", 2)
    report = run(FakeFetch(backfill_pages()))
    assert report["sources"]["sk-fact"]["stoppedBy"] == "page limit (2)"
    assert report["backfillDone"] == {"sk-fact": False}


def test_article_in_two_channels_is_queued_once(state):
    shared = sk_item("hbm4-mass-production", "HBM4 mass production", "Mon, 14 Sep 2026 00:00:00 +0000",
                     "TECH&AI", "PRESS")
    pages = {
        ("sk-tech", 1): sk_feed("TECH&amp;AI", shared,
                                sk_item("old-tech", "Old", "Mon, 01 Dec 2025 00:00:00 +0000", "TECH&AI")),
        ("sk-press", 1): sk_feed("PRESS",
                                 sk_item("press-only", "Press only", "Tue, 15 Sep 2026 00:00:00 +0000", "PRESS"),
                                 shared,
                                 sk_item("old-press", "Old", "Mon, 01 Dec 2025 00:00:00 +0000", "PRESS")),
    }
    report = run(FakeFetch(pages), sources=(SK_TECH, SK_PRESS))
    queue = {i["id"]: i for i in store.load_queue()["items"]}
    assert set(queue) == {"skhynix-hbm4-mass-production", "skhynix-press-only"}
    assert queue["skhynix-hbm4-mass-production"]["source"] == "sk-tech"
    assert queue["skhynix-hbm4-mass-production"]["alsoIn"] == ["sk-press"]
    assert report["sources"]["sk-press"]["new"] == 1

    # After the backfill, an article first seen in TECH&AI does not stop the PRESS walk early.
    pages[("sk-press", 1)] = sk_feed("PRESS",
                                     sk_item("new-joint", "Joint", "Tue, 06 Oct 2026 00:00:00 +0000", "PRESS", "TECH&AI"))
    pages[("sk-tech", 1)] = sk_feed("TECH&amp;AI",
                                    sk_item("new-joint", "Joint", "Tue, 06 Oct 2026 00:00:00 +0000", "PRESS", "TECH&AI"),
                                    shared)
    pages[("sk-press", 2)] = sk_feed("PRESS",
                                     sk_item("press-only", "Press only", "Tue, 15 Sep 2026 00:00:00 +0000", "PRESS"))
    fetch = FakeFetch(pages)
    run(fetch, sources=(SK_TECH, SK_PRESS))
    assert ("sk-press", 2) in fetch.calls
    assert store.load_queue()["items"][0]["alsoIn"] == ["sk-press"]


def test_samsung_skips_culture_and_esg_but_remembers_them(state):
    pages = {("samsung-newsroom", 1): ss_feed(
        ss_item("ai-forum", "삼성 AI 포럼 2026 개최", "Wed, 30 Sep 2026 09:00:02 +0000", "보도자료", "프레스센터"),
        ss_item("p9-p7", "포터블 SSD P9·P7 출시", "Tue, 22 Sep 2026 09:03:47 +0000", "기술", "반도체+"),
        ss_item("toolbox", "거인의 도구들", "Mon, 21 Sep 2026 11:27:15 +0000", "문화"),
        ss_item("kiww", "국제물주간", "Wed, 09 Sep 2026 17:11:13 +0000", "ESG"),
        ss_item("old", "작년 글", "Wed, 10 Dec 2025 01:00:00 +0000", "보도자료"),
    )}
    report = run(FakeFetch(pages), sources=(SAMSUNG,))
    queue = store.load_queue()["items"]
    assert [(i["channel"], i["kind"], i["lang"]) for i in queue] == [("보도자료", "press", "ko"), ("기술", "tech", "ko")]
    assert report["sources"]["samsung-newsroom"]["skippedByCategory"] == 2
    seen = store.load_seen()["urls"]
    assert sum(1 for r in seen.values() if r["status"] == "skipped") == 2


def test_queue_items_hold_metadata_only(state):
    run(FakeFetch(backfill_pages()))
    raw = config.QUEUE_FILE.read_text(encoding="utf-8")
    assert "must not be stored" not in raw
    for item in json.loads(raw)["items"]:
        assert tuple(item) == collect.QUEUE_FIELDS


def test_detect_writes_nothing(state):
    report = run(FakeFetch(backfill_pages()), dry_run=True)
    assert len(report["added"]) == 4
    assert not config.QUEUE_FILE.exists() and not config.SEEN_FILE.exists() and not config.REPORT_FILE.exists()


def test_id_collision_gets_suffix(state):
    pages = {("sk-fact", 1): sk_feed("FACT",
                                     sk_item("fact-11", "A", "Thu, 01 Oct 2026 01:00:00 +0000"),
                                     sk_item("other/fact-11", "B", "Wed, 30 Sep 2026 01:00:00 +0000"))}
    run(FakeFetch(pages))
    assert sorted(i["id"] for i in store.load_queue()["items"]) == ["skhynix-fact-11", "skhynix-fact-11-2"]


def test_selftest_reports_broken_source(capsys):
    pages = {("sk-fact", 1): sk_feed("FACT", sk_item("fact-11", "Solidigm", "Thu, 01 Oct 2026 01:22:33 +0000")),
             ("sk-tech", 1): RuntimeError("403 Forbidden")}
    assert collect.selftest(FakeFetch(pages), sources=(SK_FACT,)) is True
    assert collect.selftest(FakeFetch(pages), sources=(SK_FACT, SK_TECH)) is False
    out = capsys.readouterr().out
    assert "FAIL sk-tech" in out
