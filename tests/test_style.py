"""Style rules from im-not-ai: the checker (tools/style_check.py), the automatic style step for cards and
article pages (backend/humanize.py), and a guard that the site text keeps no comma after a connective ending."""
from __future__ import annotations

import hashlib

from backend import config, digest, humanize, summarize

from .test_summary import FakeLLM, card, data, news, queued, run, setup_queue  # noqa: F401 (data is a fixture)

SC = humanize.checker()


def test_connective_comma_removed_but_nouns_quotes_and_links_kept():
    text = "모델을 고르고, 결과를 확인하며, 참고, 로고, 빠르지만, 비쌉니다."
    assert SC.fix_c11(text) == "모델을 고르고 결과를 확인하며 참고, 로고, 빠르지만 비쌉니다."
    assert SC.c11_spans("최고, 광고, 하고,") == ["하고,"]
    # 생기고·앞당기고 are verbs (not the noun 기고); 재고/보고 are verbs after an object or '로'
    assert SC.fix_c11("전기장이 생기고, 일정을 앞당기고, 결과를 재고, 수요로 보고, 끝") == \
        "전기장이 생기고 일정을 앞당기고 결과를 재고 수요로 보고 끝"
    assert SC.fix_c11("→ 재고, 비트 출하, 즉시 보고, 정비") == "→ 재고, 비트 출하, 즉시 보고, 정비"
    # spoken quotes, names in quotes, inline code and link text stay as written
    quoted = "회장은 \"빠르고, 싸다\"고 말했고, '쌓고, 뚫고' 공정과 `a고, b` [영상 제목이고, 끝](https://x.y)"
    assert SC.fix_c11(quoted) == "회장은 \"빠르고, 싸다\"고 말했고 '쌓고, 뚫고' 공정과 `a고, b` [영상 제목이고, 끝](https://x.y)"
    # in HTML and scripts straight quotes delimit strings, so only curly quotes are protected
    assert SC.fix_c11('["올라가고</b>, 0이면 “빠르고, 싸다”"]', html=True) == '["올라가고</b> 0이면 “빠르고, 싸다”"]'


def test_checker_counts_repeats_per_document_and_skips_quotes_and_terms():
    assert "C-8" not in SC.check_text("A가 아니라 B입니다.")
    assert "C-8" in SC.check_text("A가 아니라 B입니다. C가 아니라 D입니다.")
    assert "C-8" not in SC.check_text("A가 아니라 B입니다. \"C가 아니라 D\"라고 말했습니다.")
    # semiconductor terms ending in -적 are not abstract modifiers (F-5)
    assert "F-5" not in SC.check_text("확률적 결함, 동적 전력, 기계적 연마, 전기적 특성, 물리적 한계, 집적 회로")
    assert "F-5" in SC.check_text("전략적 협력, 안정적 공급, 구조적 변화, 실질적 효과")
    assert SC.check_title("2026 시장 전망: HBM이 이끄는 슈퍼사이클") and not SC.check_title("HBM4 12단 공급")


def test_style_rules_go_into_both_prompts():
    rules = humanize.style_rules()
    assert "im-not-ai" in rules and "C-11" in rules and "Quick Rules" in rules
    assert summarize.system_prompt(summarize.RULES).endswith(rules)


def test_vendored_rulebook_is_the_upstream_copy():
    # quick-rules.md is copied whole from epoko77-ai/im-not-ai v2.3.2 (b37e020); replace it whole, never edit it
    digest_ = hashlib.sha256(humanize.QUICK_RULES.read_bytes()).hexdigest()
    assert digest_ == "7a8e66c7b9326c1df7413f7a5662d69e89907591e16ba740e5746bf01f544b85"


class StyleLLM:
    def __init__(self, fields):
        self.fields, self.calls = fields, 0

    def json_call(self, **kw):
        self.calls += 1
        return {"fields": self.fields}


def test_polish_card_keeps_numbers_and_quotes_and_rejects_big_rewrites():
    c = {"title": "2026 시장 전망: HBM이 이끄는 메모리 슈퍼사이클",
         "summary": ["핵심은 HBM4 공급입니다. 매출이 263% 늘었고, 영업이익은 21조 6천억 원입니다.",
                     "회장은 \"공급이 아니라 수요\"라고 말했고 이는 투자로 이어집니다."],
         "interview": "가격이 아니라 물량이, 이익이 아니라 매출이 실적을 정합니다."}
    llm = StyleLLM([
        {"path": "title", "text": "HBM이 이끄는 2026년 메모리 슈퍼사이클 전망"},
        {"path": "summary.0", "text": "HBM4 공급이 중요합니다. 매출이 263% 늘었고 영업이익은 21조 6천억 원입니다."},
        {"path": "summary.1", "text": "회장은 \"수요가 중요하다\"라고 말했고 회사는 투자를 늘립니다."},  # changes a quote: rejected
        {"path": "interview", "text": "가격이 아니라 물량이 실적을 정하고 매출은 99% 그대로입니다."},  # adds a number: rejected
    ])
    notes = humanize.polish_card(llm, c, "en")
    assert llm.calls == 1
    assert c["title"] == "HBM이 이끄는 2026년 메모리 슈퍼사이클 전망"
    assert c["summary"][0].startswith("HBM4 공급이 중요합니다") and "늘었고 영업이익" in c["summary"][0]
    assert c["summary"][1] == "회장은 \"공급이 아니라 수요\"라고 말했고 이는 투자로 이어집니다."
    assert c["interview"] == "가격이 아니라 물량이, 이익이 아니라 매출이 실적을 정합니다."
    assert sum("거부" in n for n in notes) == 2


def test_polish_skips_clean_text_without_a_call_and_never_touches_a_korean_title():
    c = {"title": "삼성전자, HBM4 공급: 12단", "summary": ["빠르고, 쌉니다."], "interview": ""}
    llm = StyleLLM([])
    assert humanize.polish_card(llm, c, "ko") == [] and llm.calls == 0
    assert c["summary"] == ["빠르고 쌉니다."] and c["title"] == "삼성전자, HBM4 공급: 12단"


def test_polish_detail_offers_only_flagged_sentences():
    d = {"lead": "연재 1편입니다.", "keyPoints": ["메모리가 병목입니다."],
         "blocks": [{"t": "h", "text": "배경: 학습에서 추론으로"}, {"t": "p", "text": "학습에서 추론으로 옮겨 갑니다."},
                    {"t": "h", "text": "전망: 단계적 전환"},
                    {"t": "p", "text": "줄일 수 있습니다. 늘릴 수 있습니다. 바꿀 수 있습니다. 쓸 수 있습니다."},
                    {"t": "table", "head": ["구분", "값"], "rows": [["빠르고, 싸다", "1"]]}],
         "terms": [["HBM", "D램을 쌓고, 연결한 메모리입니다."]]}
    seen = []

    class Spy(StyleLLM):
        def json_call(self, **kw):
            seen.append(kw["user"])
            return super().json_call(**kw)

    llm = Spy([{"path": "blocks.0.text", "text": "학습에서 추론으로 바뀐 배경"},
               {"path": "blocks.2.text", "text": "단계적으로 옮겨 가는 전망"},
               {"path": "blocks.3.text", "text": "줄일 수 있습니다. 늘릴 수도 있습니다. 바꾸는 것도 가능합니다. 쓸 수 있습니다."}])
    notes = humanize.polish_detail(llm, d)
    assert llm.calls == 1 and len(notes) == 3
    assert "keyPoints.0" not in seen[0] and "lead" not in seen[0]
    assert d["blocks"][0]["text"] == "학습에서 추론으로 바뀐 배경"
    assert d["blocks"][4]["rows"] == [["빠르고 싸다", "1"]] and d["terms"][0][1] == "D램을 쌓고 연결한 메모리입니다."


def test_summary_step_runs_the_style_step_and_records_it(data):
    setup_queue(queued("a", "2026-10-09T10:00:00+09:00"))
    flagged = card(summary=["SK하이닉스는 청주 M15X 공장에 150억 달러를 투자한다고 밝혔고, 핵심은 HBM입니다.",
                            "회사는 12단 HBM4 샘플을 고객사에 공급하기 시작했습니다."])
    polished = {"fields": [{"path": "summary.0", "text": "SK하이닉스는 청주 M15X 공장에 150억 달러를 투자한다고 밝혔고 HBM이 중심입니다."}]}
    llm = FakeLLM(flagged, polished)
    report = run(llm)
    a = news(data, "skhynix-a")
    assert a["summary"][0].endswith("HBM이 중심입니다.") and ", " not in a["summary"][0].split("밝혔고")[1][:2]
    assert a["checks"]["style"] == ["문체 수정: summary.0"]
    assert report["styleNotes"]["skhynix-a"] == ["문체 수정: summary.0"]
    assert "D-8" in llm.prompts[1] and "M15X" in llm.prompts[1]


def test_site_text_has_no_comma_after_a_connective_ending():
    found = {name: hits["C-11"] for name, hits in SC.scan().items() if "C-11" in hits}
    assert not found, f"python3 tools/style_check.py --fix-c11 로 지우세요: {dict(list(found.items())[:5])}"


def test_the_skill_and_checker_are_kept_out_of_the_deployed_site():
    ignore = (config.ROOT / ".vercelignore").read_text(encoding="utf-8").split()
    assert ".claude/" in ignore and "tools/" in ignore
