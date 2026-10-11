"""Offline tests for the summary step: tags, number guard, article text, the Claude wrapper, the
pipeline (with a fake Claude) and the manifest. Run: python -m pytest tests -q
"""
from __future__ import annotations

import json
import stat
import sys
from datetime import date, datetime

import pytest

from backend import bodies, config, digest, feeds, guard, publish, store, summarize, tags

from .test_collect import FakeFetch, sk_feed, ss_feed

NOW = datetime(2026, 10, 12, 7, 10, tzinfo=feeds.KST)
SK_PRESS = config.SOURCE_BY_KEY["sk-press"]
SAMSUNG = config.SOURCE_BY_KEY["samsung-newsroom"]

EN_TEXT = ("SK hynix announced today that it will invest $15 billion in its new M15X fab in Cheongju. "
           "The company began supplying 12-high HBM4 samples to customers, with bandwidth above 2 TB/s. "
           "Operating profit rose 263% year over year to KRW 21.6 trillion in the third quarter. " * 2)
KO_TEXT = ("삼성전자가 2026년 3분기 연결 기준으로 매출 86조 원, 영업이익 12조 1,000억 원의 잠정실적을 발표했다. "
           "메모리 사업은 HBM3E 12단 판매 확대로 실적이 개선됐다. 회사는 1조3,000억원 규모의 설비 투자를 집행했다. " * 2)


# ---------------------------------------------------------------- tags


def test_tag_normalize_folds_synonyms_case_and_duplicates():
    book = tags.tagbook()
    hbm = next(e for e in book.entries if e["name"] == "HBM")
    alias = (hbm["synonyms"] + hbm["keywords"])[0]
    kept, dropped = book.normalize(["hbm", alias, "없는 태그", "HBM"])
    assert kept == ["HBM"]
    assert dropped == ["없는 태그"]


def test_tag_normalize_keeps_at_most_four_in_order():
    book = tags.tagbook()
    kept, _ = book.normalize(list(book.names[:6]))
    assert kept == list(book.names[:4])


def test_related_units_rank_shared_tags_then_stars_then_number():
    index = [
        {"code": "1-2", "stars": 3, "tags": ["HBM"]},
        {"code": "4-5", "stars": 2, "tags": ["HBM", "TSV"]},
        {"code": "2-1", "stars": 3, "tags": ["TSV"]},
        {"code": "2-9", "stars": 3, "tags": ["TSV"]},
        {"code": "0-1", "stars": 1, "tags": ["DRAM"]},
    ]
    assert tags.related_units(["HBM", "TSV"], index) == ["4-5", "2-9"]
    assert tags.related_units(["HBM"], index, limit=5) == ["1-2", "4-5"]
    assert tags.related_units([], index) == []


def test_every_unit_tag_is_a_standard_tag():
    assert publish.validate() == []


# ---------------------------------------------------------------- number guard


@pytest.mark.parametrize("card, ok", [
    ("SK하이닉스는 150억 달러를 투자합니다.", True),
    ("SK하이닉스는 15억 달러를 투자합니다.", False),           # one digit off after unit conversion
    ("영업이익은 21조 6천억 원으로 263% 늘었습니다.", True),
    ("영업이익은 2조 1,600억 원입니다.", False),
    ("12단 HBM4 샘플을 공급했습니다.", True),
    ("16단 HBM4 샘플을 공급했습니다.", False),
    ("대역폭은 2TB/s 이상입니다.", True),
    ("2026년 3분기 실적과 6세대 제품을 소개했습니다.", True),     # years, quarters, generations are skipped
])
def test_guard_checks_numbers_against_english_source(card, ok):
    assert (guard.unsupported(card, EN_TEXT) == []) is ok


def test_guard_reads_korean_scale_words_in_source():
    assert guard.unsupported("1조 3,000억 원을 투자했습니다.", KO_TEXT) == []
    assert guard.unsupported("영업이익 12조 1,000억 원, 매출 86조 원입니다.", KO_TEXT) == []
    assert guard.unsupported("매출 68조 원입니다.", KO_TEXT) == ["68조 원"]


def test_guard_allows_rounding_and_rounded_scaled_values():
    src = "Market size reached $3.379 trillion, up 41.6%."
    assert guard.unsupported("시장 규모는 약 3.4조 달러로 42% 늘었습니다.", src) == []


# ---------------------------------------------------------------- article text


def test_html_to_text_drops_scripts_images_and_feed_footer():
    html = ("<p>First paragraph.</p><script>var x=1;</script><img src='a.png'><ul><li>Point one</li></ul>"
            "<p>The post Something first appeared on SK hynix Newsroom.</p>")
    assert feeds.html_to_text(html) == "First paragraph.\nPoint one"


def body_item(slug: str, title: str, pub: str, body: str, *cats: str, author: str = "SK hynix") -> str:
    return (f"<item><title>{title}</title><link>https://news.skhynix.com/en/{slug}/</link>"
            f"<dc:creator><![CDATA[{author}]]></dc:creator><pubDate>{pub}</pubDate>"
            + "".join(f"<category><![CDATA[{c}]]></category>" for c in cats) +
            f"<content:encoded><![CDATA[<p>{body}</p>]]></content:encoded></item>")


def queued(slug: str, published: str, *, source=SK_PRESS, lang="en", title="SK hynix Invests $15 Billion",
           kind="press", channel="PRESS", company="skhynix", url=None) -> dict:
    return {"id": f"{company}-{slug}", "company": company, "source": source.key, "channel": channel, "kind": kind,
            "lang": lang, "title": title, "url": url or f"https://news.skhynix.com/en/{slug}/",
            "published": published, "date": published[:10], "categories": ["PRESS"], "alsoIn": [],
            "collectedAt": "2026-10-12T07:00:00+09:00"}


def test_body_finder_reads_feed_pages_once_and_finds_older_articles():
    fetch = FakeFetch({
        ("sk-press", 1): sk_feed("PRESS", body_item("new", "New", "Fri, 09 Oct 2026 01:00:00 +0000", EN_TEXT)),
        ("sk-press", 2): sk_feed("PRESS", body_item("old", "Old", "Mon, 05 Oct 2026 01:00:00 +0000", EN_TEXT,
                                                    author="Onur Mutlu")),
    })
    finder = bodies.BodyFinder(fetch=fetch, fetch_page_text=lambda url: pytest.fail("page not needed"), sleep=None)
    old = finder.find(queued("old", "2026-10-05T10:00:00+09:00"))
    new = finder.find(queued("new", "2026-10-09T10:00:00+09:00"))
    assert old.via == new.via == "feed"
    assert old.author == "Onur Mutlu" and "M15X" in old.text
    assert fetch.calls == [("sk-press", 1), ("sk-press", 2)]


def test_body_finder_falls_back_to_article_page():
    fetch = FakeFetch({("sk-press", 1): sk_feed("PRESS", body_item("x", "X", "Fri, 09 Oct 2026 01:00:00 +0000", EN_TEXT))})
    pages = []
    finder = bodies.BodyFinder(fetch=fetch, fetch_page_text=lambda url: pages.append(url) or EN_TEXT, sleep=None)
    body = finder.find(queued("gone", "2026-09-01T10:00:00+09:00"))
    assert body.via == "page" and pages == ["https://news.skhynix.com/en/gone/"]
    assert fetch.calls == [("sk-press", 1), ("sk-press", 2)]   # page 2 does not exist: end of feed


def test_body_finder_gives_up_on_short_text_and_broken_feed():
    fetch = FakeFetch({("sk-press", 1): RuntimeError("boom")})
    finder = bodies.BodyFinder(fetch=fetch, fetch_page_text=lambda url: "too short", sleep=None)
    assert finder.find(queued("a", "2026-10-09T10:00:00+09:00")) is None
    assert finder.find(queued("b", "2026-10-09T10:00:00+09:00")) is None
    assert fetch.calls == [("sk-press", 1)]   # a broken feed is not asked again in the same run


# ---------------------------------------------------------------- Claude wrapper


@pytest.mark.parametrize("message, kind", [
    ("Invalid API key · Please run /login", summarize.AuthError),
    ('API Error: 401 {"type":"authentication_error"}', summarize.AuthError),
    ("Claude AI usage limit reached|1760000000", summarize.LimitError),
    ("You've hit your limit · resets 3pm", summarize.LimitError),
    ("API Error: 529 Overloaded", summarize.LimitError),
    ("Unexpected token in JSON", None),
])
def test_classify_error(message, kind):
    assert summarize.classify_error(message) is kind


def fake_cli(tmp_path, stdout: str, code: int = 0):
    script = tmp_path / "claude"
    script.write_text(f"#!{sys.executable}\nimport sys\nsys.stdin.read()\n"
                      f"sys.stdout.write({stdout!r})\nsys.exit({code})\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return summarize.ClaudeCodeCLI(str(script))


def test_cli_reads_structured_output(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-abc\n│ ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-be-passed")
    cli = fake_cli(tmp_path, json.dumps({"is_error": False, "structured_output": {"title": "제목"}}))
    assert cli.env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-abc"
    assert "ANTHROPIC_API_KEY" not in cli.env
    assert cli.json_call(model="m", system="s", user="u", schema={}) == {"title": "제목"}


def test_cli_raises_auth_and_limit_errors(tmp_path):
    cli = fake_cli(tmp_path, json.dumps({"is_error": True, "result": "Invalid API key · Please run /login"}))
    with pytest.raises(summarize.AuthError):
        cli.json_call(model="m", system="s", user="u", schema={})
    cli = fake_cli(tmp_path, "Claude AI usage limit reached|1760000000", code=1)
    with pytest.raises(summarize.LimitError):
        cli.json_call(model="m", system="s", user="u", schema={})


def test_prompt_marks_outside_authors_only():
    book = tags.tagbook()
    item = queued("a", "2026-10-09T10:00:00+09:00")
    assert "필자" not in summarize.article_prompt(item, EN_TEXT, "SK hynix", book)
    assert "Onur Mutlu" in summarize.article_prompt(item, EN_TEXT, "Onur Mutlu", book)


# ---------------------------------------------------------------- pipeline


class FakeLLM:
    """Returns the queued answers in order (a dict, or an exception to raise)."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def json_call(self, *, model, system, user, schema):
        self.prompts.append(user)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeFinder:
    def __init__(self, texts: dict[str, str | None], author: str = "SK hynix"):
        self.texts, self.author = texts, author

    def find(self, item):
        text = self.texts.get(item["id"], EN_TEXT)
        return None if text is None else bodies.Body(text, self.author, "feed")


def card(title="SK하이닉스, 청주 M15X에 150억 달러 투자", summary=None, interview=None, tag_list=("HBM",)):
    return {"title": title,
            "summary": summary or ["SK하이닉스는 청주 M15X 공장에 150억 달러를 투자한다고 밝혔습니다.",
                                   "회사는 12단 HBM4 샘플을 고객사에 공급하기 시작했습니다."],
            "interview": "M15X 투자는 HBM 수요에 맞춘 생산 능력 확대 사례로 들 수 있습니다." if interview is None else interview,
            "tags": list(tag_list), "companies": ["SK하이닉스", "SK하이닉스", "엔비디아"]}


@pytest.fixture()
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SEEN_FILE", tmp_path / "state" / "seen.json")
    monkeypatch.setattr(config, "QUEUE_FILE", tmp_path / "state" / "queue.json")
    monkeypatch.setattr(config, "REPORT_FILE", tmp_path / "state" / "last-run.json")
    monkeypatch.setattr(config, "NEWS_DIR", tmp_path / "data" / "news")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "data" / "manifest.json")
    monkeypatch.setattr(config, "START_DATE", date(2026, 1, 1))
    return tmp_path


def setup_queue(*items):
    seen = {"urls": {}, "backfill": {}}
    for i in items:
        seen["urls"][feeds.normalize_url(i["url"])] = {"id": i["id"], "status": "queued", "title": i["title"],
                                                       "date": i["date"], "sources": [i["source"]]}
    store.save_seen(seen)
    store.save_queue({"items": list(items)})


def run(llm, finder=None, **kw):
    return digest.run(llm=llm, finder=finder or FakeFinder({}), now=NOW, **kw)


def news(data, article_id):
    return json.loads((config.NEWS_DIR / f"{article_id}.json").read_text(encoding="utf-8"))


def test_summarizes_newest_first_up_to_the_limit(data):
    setup_queue(queued("a", "2026-10-01T10:00:00+09:00"), queued("b", "2026-10-09T10:00:00+09:00"),
                queued("c", "2026-10-05T10:00:00+09:00"))
    report = run(FakeLLM(card(), card()), limit=2)
    assert [s["id"] for s in report["summarized"]] == ["skhynix-b", "skhynix-c"]
    assert report["stoppedBy"] == "limit" and report["queueLeft"] == 1
    assert [i["id"] for i in store.load_queue()["items"]] == ["skhynix-a"]
    seen = store.load_seen()["urls"]
    assert seen["https://news.skhynix.com/en/b"]["status"] == "summarized"
    a = news(data, "skhynix-b")
    assert a["title"] == "SK하이닉스, 청주 M15X에 150억 달러 투자"
    assert a["originalTitle"] == "SK hynix Invests $15 Billion"
    assert a["companies"] == ["SK하이닉스", "엔비디아"]
    assert a["tags"] == ["HBM"] and "checks" not in a and "author" not in a
    assert a["bodyVia"] == "feed" and a["model"] == config.SUMMARY_MODEL


def test_korean_article_keeps_its_title_verbatim(data):
    item = queued("k", "2026-10-08T17:05:21+09:00", source=SAMSUNG, lang="ko", company="samsung",
                  title="삼성전자, 2026년 3분기 잠정실적 발표", channel="보도자료",
                  url="https://news.samsungsemiconductor.com/kr/k/")
    setup_queue(item)
    run(FakeLLM(card(title="다른 제목", summary=["삼성전자는 3분기 매출 86조 원을 발표했습니다.",
                                              "영업이익은 12조 1,000억 원입니다."], interview="")),
        FakeFinder({"samsung-k": KO_TEXT}))
    a = news(data, "samsung-k")
    assert a["title"] == "삼성전자, 2026년 3분기 잠정실적 발표" and "originalTitle" not in a


def test_wrong_number_is_retried_with_the_list_of_problems(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"))
    wrong = card(summary=["SK하이닉스는 15억 달러를 투자한다고 밝혔습니다.", "12단 HBM4 샘플을 공급했습니다."])
    llm = FakeLLM(wrong, card())
    run(llm)
    assert "다음 수치를 원문에서 찾지 못했습니다: 15억 달러" in llm.prompts[1]
    a = news(data, "skhynix-a")
    assert a["summary"][0].startswith("SK하이닉스는 청주 M15X 공장에 150억 달러")
    assert a["checks"] == {"retriedFor": ["15억 달러"]}


def test_number_still_wrong_after_retry_drops_the_sentence(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"))
    wrong = card(summary=["SK하이닉스는 M15X 공장 투자를 밝혔습니다.", "회사는 16단 HBM4 샘플을 공급했습니다."],
                 interview="16단 제품은 좋은 사례입니다.")
    run(FakeLLM(wrong, wrong))
    a = news(data, "skhynix-a")
    assert a["summary"] == ["SK하이닉스는 M15X 공장 투자를 밝혔습니다."]
    assert a["interview"] == ""
    assert a["checks"]["removed"] == ["회사는 16단 HBM4 샘플을 공급했습니다.", "16단 제품은 좋은 사례입니다."]


def test_untranslated_title_fails_and_is_given_up_after_three_runs(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"))
    for attempt in (1, 2, 3):
        report = run(FakeLLM(card(title="SK hynix Invests")))
        assert "한국어가 아님" in report["failed"]["skhynix-a"]
    assert report["gaveUp"][0]["id"] == "skhynix-a"
    assert store.load_queue()["items"] == []
    rec = store.load_seen()["urls"]["https://news.skhynix.com/en/a"]
    assert rec["status"] == "failed" and "한국어가 아님" in rec["reason"]


def test_missing_body_counts_as_an_attempt(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"), queued("b", "2026-10-08T10:00:00+09:00"))
    report = run(FakeLLM(card()), FakeFinder({"skhynix-a": None}))
    assert list(report["failed"]) == ["skhynix-a"]
    assert [s["id"] for s in report["summarized"]] == ["skhynix-b"]
    left = store.load_queue()["items"]
    assert left[0]["id"] == "skhynix-a" and left[0]["attempts"] == 1 and "본문" in left[0]["lastError"]


@pytest.mark.parametrize("error, flag", [(summarize.AuthError("401"), "authError"),
                                         (summarize.LimitError("usage limit"), "limitHit")])
def test_auth_error_or_usage_limit_stops_without_counting_attempts(data, error, flag):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"), queued("b", "2026-10-08T10:00:00+09:00"))
    llm = FakeLLM(card(), error)
    report = run(llm)
    assert report[flag] is True
    assert [s["id"] for s in report["summarized"]] == ["skhynix-a"]
    left = store.load_queue()["items"]
    assert [i["id"] for i in left] == ["skhynix-b"] and "attempts" not in left[0]


def test_outside_author_is_kept_and_unknown_tags_recorded(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00", kind="tech", channel="TECH&AI"))
    run(FakeLLM(card(tag_list=("HBM", "TSV", "없는태그"))), FakeFinder({}, author="Onur Mutlu"))
    a = news(data, "skhynix-a")
    assert a["author"] == "Onur Mutlu"
    # "TSV" is a synonym of a standard tag and is folded into it
    assert a["tags"] == ["HBM", "HBM 적층(TSV·MR-MUF)"] and a["checks"] == {"unknownTags": ["없는태그"]}


def test_no_credentials_does_nothing(data, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"))
    report = digest.run(now=NOW)
    assert report["stoppedBy"] == "no credentials" and report["queueLeft"] == 1


def test_time_budget_stops_starting_new_articles(data, monkeypatch):
    monkeypatch.setattr(config, "SUMMARY_TIME_BUDGET", 10)
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"), queued("b", "2026-10-08T10:00:00+09:00"))
    ticks = iter([0, 5, 20])
    report = run(FakeLLM(card(), card()), clock=lambda: next(ticks))
    assert report["stoppedBy"] == "time budget" and len(report["summarized"]) == 1


def test_sentences_splits_one_element_holding_two():
    assert digest.sentences(["첫 문장입니다. 둘째 문장입니다.", "셋째입니다."]) == ["첫 문장입니다.", "둘째 문장입니다."]


def test_requeue_puts_cards_back_with_their_original_title(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"), queued("b", "2026-10-01T10:00:00+09:00"))
    run(FakeLLM(card(), card()))
    path = config.NEWS_DIR / "skhynix-b.json"
    b = json.loads(path.read_text(encoding="utf-8"))
    b["rules"] = "old"
    path.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    assert digest.requeue(outdated=True, now=NOW) == ["skhynix-b"]
    item = store.load_queue()["items"][0]
    assert item["title"] == "SK hynix Invests $15 Billion" and item["id"] == "skhynix-b"
    assert store.load_seen()["urls"]["https://news.skhynix.com/en/b"]["status"] == "queued"
    assert not path.exists() and (config.NEWS_DIR / "skhynix-a.json").exists()
    run(FakeLLM(card()))
    assert news(data, "skhynix-b")["rules"] == summarize.RULES_VERSION


# ---------------------------------------------------------------- manifest


def test_manifest_lists_cards_with_related_units_and_skips_unchanged_rewrites(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"), queued("b", "2026-10-01T10:00:00+09:00"))
    run(FakeLLM(card(tag_list=("HBM", "HBM 적층(TSV·MR-MUF)")), card()))
    first = publish.build(now=NOW)
    assert first == {"count": 2, "changed": True}
    m = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    assert [i["id"] for i in m["items"]] == ["skhynix-a", "skhynix-b"]
    assert m["items"][0]["relatedUnits"] == tags.related_units(["HBM", "HBM 적층(TSV·MR-MUF)"])
    assert len(m["items"][0]["relatedUnits"]) == 2
    assert "checks" not in m["items"][0] and "model" not in m["items"][0]
    assert {s["key"] for s in m["sources"]} == set(config.SOURCE_BY_KEY)
    assert len(m["linkOnly"]) == 2
    assert publish.build(now=NOW) == {"count": 2, "changed": False}
    assert publish.validate() == []


def test_validate_reports_bad_article_files(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"))
    run(FakeLLM(card()))
    publish.build(now=NOW)
    path = config.NEWS_DIR / "skhynix-a.json"
    a = json.loads(path.read_text(encoding="utf-8"))
    a.update(tags=["가짜"], summary=[], originalTitle="")
    path.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    problems = publish.validate()
    assert any("표준 태그가 아님: 가짜" in p for p in problems)
    assert any("summary" in p for p in problems)
    assert any("originalTitle" in p for p in problems)
