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

TIMEZONE = "Asia/Seoul"

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

# Required pages that cannot be collected automatically (the article list is drawn by JavaScript).
# The site shows them as "원문 보기" links only.
LINK_ONLY = (
    ("삼성반도체 뉴스", "https://semiconductor.samsung.com/kr/news-events/news/"),
    ("삼성반도체 테크 블로그", "https://semiconductor.samsung.com/kr/news-events/tech-blog/"),
)
