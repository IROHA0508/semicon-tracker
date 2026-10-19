"""Claude calls that turn one article into a Korean card: title, two-sentence summary, one line for
interviews, standard tags and the companies mentioned.

Two backends, as in release-radar: the Claude Code CLI with a Pro/Max subscription token
(CLAUDE_CODE_OAUTH_TOKEN, no API billing), or the Claude API with an API key.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess

from . import config, tags

log = logging.getLogger(__name__)

STR = {"type": "string"}


def card_schema(tag_names: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            "title": STR,
            "summary": {"type": "array", "items": STR},
            "interview": STR,
            "tags": {"type": "array", "items": {"type": "string", "enum": list(tag_names)}},
            "companies": {"type": "array", "items": STR},
        },
        "required": ["title", "summary", "interview", "tags", "companies"],
        "additionalProperties": False,
    }


# Bump when RULES change in a way that makes older cards worth redoing (python -m backend requeue).
RULES_VERSION = "2026-10-12"

RULES = """\
너는 반도체 면접 준비용 개인 사이트의 뉴스 편집자다. 삼성전자와 SK하이닉스 공식 뉴스룸 글 하나를
한국어 카드 하나로 정리한다. 카드는 제목, 요약 2문장, 면접에서 쓸 한 줄, 표준 태그, 언급 기업으로 이루어진다.

공통 원칙
- 아래 '원문'에 있는 내용만 근거로 쓴다. 원문에 없는 사실, 수치, 날짜, 전망, 배경지식은 쓰지 않는다.
- 수치는 원문 그대로 옮긴다. 영어 단위를 한국어로 바꿀 때 자릿수를 정확히 지킨다
  (예: $15 billion = 150억 달러, $466 billion = 4,660억 달러, KRW 21.6 trillion = 21조 6천억 원,
  KRW 1,100 trillion = 1,100조 원). 원문 수치로 직접 계산한 새 수치(합계, 차이, 배수)는 쓰지 않는다.
- 이 단계 뒤에 프로그램이 카드의 수치를 원문과 대조해, 원문에서 확인되지 않는 수치가 든 문장은 지운다.
- 문체: '-습니다'로 끝나는 간결한 존댓말. 홍보 문구(혁신적인, 압도적인, 세계 최고의 등)는 원문 주장임을
  밝히지 않는 한 쓰지 않고 사실 위주로 쓴다. '세계 최초' 같은 회사 주장은 "~라고 밝혔습니다"로 쓴다.
- 제품명·기술명·고유명사는 원문 표기를 따른다(HBM4, SOCAMM2, CXL, eSSD 등). 영어 일반어는 한국어로 옮긴다.
  사람 이름은 한국어로 음역하고 처음 한 번은 직함을 붙인다.

필드
- title: 원문이 영어면 자연스러운 한국어 기사 제목으로 옮긴다(45자 안팎, 핵심 사실이 드러나게, 끝에 마침표 없음).
  원문이 한국어면 원문 제목을 글자 그대로 쓴다.
- summary: 정확히 2문장을 배열에 한 문장씩 담는다. 한 문장은 120자 안팎을 넘지 않는다.
  첫 문장은 무엇이 일어났는지(누가 무엇을), 둘째 문장은 핵심 내용이나 근거(수치, 일정, 이유).
  - 글 종류가 '공식 해명'이면 첫 문장에 어떤 보도에 대한 회사 설명인지, 둘째 문장에 회사의 입장을 쓴다.
  - 외부 교수·전문가의 기고(글 정보의 필자나 본문의 필자 소개로 알 수 있음)면 첫 문장에 필자를 밝힌다
    (예: "ETH 취리히의 오누르 무틀루 교수는 ...라고 설명합니다"). 회사 직원 인터뷰는 기고가 아니다.
  - 연재 글이면 무엇을 다룬 몇 번째 글인지 밝혀도 된다.
- interview: 면접에서 이 기사를 근거로 말할 때 쓸 한 문장(100자 안팎). 요약을 되풀이하지 말고, 기사 속 사실
  하나가 반도체 산업·메모리 사업·엔지니어 직무에 갖는 의미를 말한다. 끝맺음은 글에 맞게 자연스럽게
  ("~를 보여 줍니다", "~라는 점에서 의미가 있습니다" 등)하고 매번 같은 틀을 쓰지 않는다.
  원문에 없는 수치는 넣지 않는다. 반도체 사업과 관계가 거의 없는 글(명절 행사, 사회공헌, 사내 문화)이면 빈 문자열.
- tags: 아래 '표준 태그 목록'의 이름을 글자 그대로, 글의 중심 주제부터 1~3개(네 주제를 고루 다룬 글만 4개).
  원문에 동의어나 영문 키워드가 나오면 그 표준 태그를 고른다. 글 전체가 다루는 주제만 고르고, 한두 문장 스쳐 가는
  언급이나 수식어는 태그로 만들지 않는다. 자주 틀리는 경우:
  - 'AI 서버·데이터센터'는 데이터센터·AI 서버 자체(수요, 구조, 전력, 투자)가 주제일 때만. 제품 설명에
    'AI용'이 붙었다는 이유로 넣지 않는다.
  - '주주환원·자본'은 배당·자사주·자금 조달·투자 재원이 주제일 때만. 실적 발표라는 이유만으로 넣지 않는다.
  - '패키징'·'팹 투자'·'온디바이스 AI'도 그 자체가 글의 주제일 때만.
  맞는 태그가 없으면 빈 배열.
- companies: 원문에 나오는 기업 이름을 한국어 통용 표기로, 중요한 순서대로 최대 6개(글을 낸 회사 포함).
  예: 삼성전자, SK하이닉스, TSMC, 엔비디아, 마이크론, ASML, 솔리다임, 인텔, AMD, 구글, 오픈AI. 기관·대학은 넣지 않는다.
"""


class AuthError(RuntimeError):
    """The credential was rejected (bad, expired or revoked token / key)."""


class LimitError(RuntimeError):
    """The subscription usage limit (or API rate limit, overload) was reached: stop for this run."""


_AUTH = re.compile(r"\b401\b|authenticat|invalid api key|invalid x-api-key", re.I)
_LIMIT = re.compile(r"usage limit|hit your limit|limit reached|rate.?limit|\b429\b|\b529\b|overloaded|quota", re.I)


def classify_error(text: str) -> type[RuntimeError] | None:
    """AuthError / LimitError for a CLI or API error message, None for anything else."""
    if _AUTH.search(text):
        return AuthError
    if _LIMIT.search(text):
        return LimitError
    return None


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


class ClaudeCodeCLI:
    """Claude Code CLI in headless mode with a subscription token (same call as release-radar).

    The API key is removed from the child environment on purpose: if it were set, Claude Code would
    bill the API instead of the subscription.
    """

    def __init__(self, binary: str = "claude"):
        import shutil

        self.binary = shutil.which(binary) or binary
        self.env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        if self.env.get("CLAUDE_CODE_OAUTH_TOKEN"):
            # A token copied from a terminal often picks up line breaks or box-drawing borders.
            self.env["CLAUDE_CODE_OAUTH_TOKEN"] = re.sub(r"[^A-Za-z0-9_-]", "", self.env["CLAUDE_CODE_OAUTH_TOKEN"])

    def json_call(self, *, model: str, system: str, user: str, schema: dict) -> dict:
        prompt = f"# 작업 지시\n{system}\n\n# 입력\n{user}\n\n결과는 주어진 JSON 스키마에 맞는 JSON 객체 하나로만 답해라."
        cmd = [self.binary, "-p", "--output-format", "json", "--json-schema", json.dumps(schema, ensure_ascii=False),
               "--model", model, "--tools", "", "--no-session-persistence",
               "--system-prompt", "너는 JSON만 출력하는 편집 도우미다. 도구를 쓰지 않는다."]
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, env=self.env, timeout=600)
        out = (proc.stdout or "").strip()
        if proc.returncode != 0:
            message = (proc.stderr or out)[-800:]
            kind = classify_error(message)
            raise (kind or RuntimeError)(f"claude CLI 실패({proc.returncode}): {message}")
        envelope = json.loads(out)
        if envelope.get("is_error"):
            message = str(envelope.get("result"))[:800]
            kind = classify_error(message)
            raise (kind or RuntimeError)(f"claude CLI 오류: {message}")
        if isinstance(envelope.get("structured_output"), dict):
            return envelope["structured_output"]
        return parse_json(envelope.get("result") or "")


class ClaudeAPI:
    """Claude API with an API key (pay as you go). Used only when no subscription token is set."""

    def __init__(self):
        import anthropic  # only needed when an API key is used

        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=3)

    def json_call(self, *, model: str, system: str, user: str, schema: dict) -> dict:
        a = self.anthropic
        try:
            try:
                msg = self.client.messages.create(
                    model=model, max_tokens=8000, system=system, messages=[{"role": "user", "content": user}],
                    output_config={"format": {"type": "json_schema", "schema": schema}},
                )
            except a.BadRequestError as exc:  # structured output not supported: ask for plain JSON
                log.warning("structured output rejected (%s); retrying with plain JSON", exc)
                msg = self.client.messages.create(
                    model=model, max_tokens=8000, system=system + "\n\n출력은 JSON 객체 하나만, 다른 글 없이.",
                    messages=[{"role": "user", "content": user + "\n\nJSON 스키마:\n" + json.dumps(schema, ensure_ascii=False)}],
                )
        except a.AuthenticationError as exc:
            raise AuthError(str(exc)) from exc
        except (a.RateLimitError, a.InternalServerError) as exc:
            raise LimitError(str(exc)) from exc
        return parse_json("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))


def llm_available() -> str | None:
    """Which backend can run: "cli" (subscription token, preferred), "api", or None."""
    choice = os.environ.get("ST_LLM", "").lower()
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") and choice != "api":
        return "cli"
    if os.environ.get("ANTHROPIC_API_KEY") and choice != "cli":
        return "api"
    return None


def make_llm():
    return ClaudeCodeCLI() if llm_available() == "cli" else ClaudeAPI()


def article_prompt(item: dict, text: str, author: str, book: tags.TagBook) -> str:
    source = config.SOURCE_BY_KEY[item["source"]]
    kind = config.KIND_LABELS.get(item["kind"], item["kind"])
    lines = [
        "# 글 정보",
        f"- 출처: {source.name} / 채널: {item['channel']} (글 종류: {kind})",
        f"- 원문 제목: {item['title']}",
        f"- 원문 언어: {'영어' if item['lang'] == 'en' else '한국어'}",
        f"- 발행일: {item['date']}",
    ]
    if author and not config.is_company_author(author):
        lines.append(f"- 피드에 적힌 필자: {author} (회사 계정이 아님. 외부 기고일 수 있음)")
    if item.get("categories"):
        lines.append(f"- 원문 카테고리·태그: {', '.join(item['categories'])}")
    lines += ["", "# 표준 태그 목록", book.prompt_lines(), "", "# 원문", text]
    return "\n".join(lines)


def write_card(llm, item: dict, text: str, author: str, book: tags.TagBook, *,
               fix: tuple[dict, list[str]] | None = None) -> dict:
    """One Claude call. With fix=(previous card, unsupported numbers), ask for a corrected card."""
    user = article_prompt(item, text, author, book)
    if fix:
        previous, bad = fix
        user += ("\n\n# 수정 요청\n직전에 쓴 카드:\n" + json.dumps(previous, ensure_ascii=False, indent=1) +
                 "\n\n다음 수치를 원문에서 찾지 못했습니다: " + ", ".join(bad) +
                 "\n원문에 있는 그대로의 수치로 고치거나(단위 자릿수 주의) 그 수치를 빼고 카드를 다시 써라. 나머지 원칙은 같다.")
    return llm.json_call(model=config.SUMMARY_MODEL, system=RULES, user=user, schema=card_schema(book.names))
