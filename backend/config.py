"""Settings for the article collector. Everything can be overridden with environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("ST_ROOT", Path(__file__).resolve().parent.parent))
STATE_DIR = ROOT / "backend" / "state"
SEEN_FILE = STATE_DIR / "seen.json"        # every article URL the collector has looked at
QUEUE_FILE = STATE_DIR / "queue.json"      # collected articles waiting for the summary step
REPORT_FILE = STATE_DIR / "last-run.json"  # what the latest run did
DETAIL_STATE = STATE_DIR / "details.json"  # long summaries that failed (attempts, last error)

DATA = ROOT / "data"
NEWS_DIR = DATA / "news"                   # one summarized article = one JSON file
MANIFEST = DATA / "manifest.json"          # card list for the site, rebuilt after every change
DETAIL_DIR = DATA / "detail"                # long summary of one article = one JSON file (+ figs/)
TAGS_FILE = DATA / "tags.json"             # standard tag dictionary (55 tags, 9 groups)
UNITS_FILE = DATA / "units.json"           # theory units with their standard tags

TIMEZONE = "Asia/Seoul"

# Summary step. Runs share the Claude subscription with release-radar, so each run summarizes at
# most SUMMARY_LIMIT queued articles (newest first) and the backlog is worked off over several runs.
SUMMARY_MODEL = os.environ.get("ST_MODEL", "claude-sonnet-5-5")
SUMMARY_LIMIT = int(os.environ.get("ST_SUMMARY_LIMIT", "10"))
MAX_ATTEMPTS = 3                           # failed runs before an article is given up on
BODY_CHAR_LIMIT = 15_000                   # article text sent to Claude (two sentences need no more)
MIN_BODY_CHARS = 200                       # shorter text means the body was not found
# Stop starting new summaries after this many seconds so the workflow can still commit its work.
SUMMARY_TIME_BUDGET = int(os.environ.get("ST_TIME_BUDGET", "1500"))
# Long summaries (article page): at most DETAIL_LIMIT articles per run, newest first, and no new one
# after DETAIL_TIME_BUDGET seconds of the run (summary step included).
DETAIL_LIMIT = int(os.environ.get("ST_DETAIL_LIMIT", "10"))
DETAIL_TIME_BUDGET = int(os.environ.get("ST_DETAIL_TIME_BUDGET", "2400"))
DETAIL_CHAR_LIMIT = 30_000                 # article text sent to Claude for the long summary

# Keep articles published on or after this date (Korean time). Older pages are not walked.
START_DATE = date.fromisoformat(os.environ.get("ST_START_DATE", "2026-01-01"))

# Per source and run: how many feed pages to read at most, and the pause between page requests.
MAX_PAGES = int(os.environ.get("ST_MAX_PAGES", "25"))
PAGE_DELAY = float(os.environ.get("ST_PAGE_DELAY", "1.0"))

HTTP_TIMEOUT = 30
USER_AGENT = os.environ.get(
    "ST_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 SemiconTrackerBot/1.0 (personal study site)",
)


@dataclass(frozen=True)
class Source:
    key: str            # short stable id, stored in seen.json and queue.json
    name: str           # shown in reports
    company: str        # skhynix | samsung
    lang: str           # language of titles in the feed: en | ko
    feed: str           # WordPress RSS feed; page N is feed + "?paged=N"
    page: str           # the human page for this channel (the link users open)
    channel: str = ""   # fixed channel name; empty means it comes from the item's categories
    kind: str = ""      # fixed kind (press | fact | tech); empty means it comes from the categories
    # (category, channel, kind) for feeds that mix channels. Items whose categories match none of
    # these are skipped. Order matters: the first matching rule wins.
    categories: tuple[tuple[str, str, str], ...] = ()


SOURCES = (
    Source("sk-fact", "SK하이닉스 뉴스룸 FACT", "skhynix", "en",
           "https://news.skhynix.com/en/category/fact/feed/",
           "https://news.skhynix.co.kr/category/fact/", channel="FACT", kind="fact"),
    Source("sk-tech", "SK하이닉스 뉴스룸 TECH&AI", "skhynix", "en",
           "https://news.skhynix.com/en/category/tech-and-ai/feed/",
           "https://news.skhynix.co.kr/category/tech-and-ai/", channel="TECH&AI", kind="tech"),
    Source("sk-press", "SK하이닉스 뉴스룸 PRESS", "skhynix", "en",
           "https://news.skhynix.com/en/category/press/feed/",
           "https://news.skhynix.co.kr/category/press/", channel="PRESS", kind="press"),
    # Samsung's newsroom feed mixes press releases, tech articles, culture and ESG posts.
    # Only press releases and tech articles are collected (decision of 2026-10-06).
    Source("samsung-newsroom", "삼성전자 반도체 뉴스룸", "samsung", "ko",
           "https://news.samsungsemiconductor.com/kr/feed/",
           "https://news.samsungsemiconductor.com/kr/",
           categories=(("보도자료", "보도자료", "press"), ("기술", "기술", "tech"))),
)

SOURCE_BY_KEY = {s.key: s for s in SOURCES}

# Feed authors that are the company itself; any other author may be an outside contributor.
COMPANY_AUTHORS = {"SK hynix", "SK하이닉스", "삼성전자 반도체", "Samsung Semiconductor"}
_COMPANY_WORDS = ("sk hynix", "skhynix", "하이닉스", "samsung", "삼성", "newsroom", "뉴스룸", "admin")


def is_company_author(name: str) -> bool:
    low = name.strip().lower()
    return not low or name.strip() in COMPANY_AUTHORS or any(w in low for w in _COMPANY_WORDS)

KIND_LABELS = {"press": "보도자료", "fact": "공식 해명", "tech": "기술 해설"}

# Required pages that cannot be collected automatically (the article list is drawn by JavaScript).
# The site shows them as "원문 보기" links only.
LINK_ONLY = (
    ("삼성반도체 뉴스", "https://semiconductor.samsung.com/kr/news-events/news/"),
    ("삼성반도체 테크 블로그", "https://semiconductor.samsung.com/kr/news-events/tech-blog/"),
)
