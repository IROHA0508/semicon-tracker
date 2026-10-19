"""Find the text of a queued article for the summary step. Nothing found here is written to disk.

1. The source's RSS feed: walk its pages (each page read at most once per run) until the article
   turns up or the pages get older than the article. WordPress feeds carry the full article.
2. The article's own web page, when the feed no longer has it.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from . import config, feeds

log = logging.getLogger(__name__)


@dataclass
class Body:
    text: str
    author: str   # feed author ("" when unknown)
    via: str      # feed | page
    html: str = field(default="", repr=False)   # article HTML, in memory only (pictures for the long summary)


class BodyFinder:
    def __init__(self, fetch=feeds.fetch_page, fetch_page_text: Callable[[str], str] = feeds.fetch_article_page,
                 sleep: Callable[[float], None] | None = time.sleep,
                 fetch_page_html: Callable[[str], str] | None = None):
        self.fetch = fetch
        self.fetch_page_text = fetch_page_text
        self.fetch_page_html = fetch_page_html
        self.sleep = sleep
        self.pages: dict[tuple[str, int], list[feeds.Item] | None] = {}
        self.broken: set[str] = set()   # sources whose feed failed in this run

    def _page(self, source: config.Source, page: int) -> list[feeds.Item] | None:
        key = (source.key, page)
        if key not in self.pages:
            if self.pages and self.sleep:
                self.sleep(config.PAGE_DELAY)
            self.pages[key] = self.fetch(source, page)
        return self.pages[key]

    def from_feed(self, item: dict) -> Body | None:
        source = config.SOURCE_BY_KEY.get(item["source"])
        if source is None or source.key in self.broken:
            return None
        target = feeds.normalize_url(item["url"])
        oldest_useful = date.fromisoformat(item["date"]) - timedelta(days=1)
        for page in range(1, config.MAX_PAGES + 1):
            try:
                items = self._page(source, page)
            except Exception as exc:  # noqa: BLE001 - fall back to the article page
                log.warning("%s feed page %d failed: %s", source.key, page, exc)
                self.broken.add(source.key)
                return None
            if not items:
                return None
            for it in items:
                if it.key == target:
                    text = feeds.html_to_text(it.body, config.BODY_CHAR_LIMIT)
                    return Body(text, it.author, "feed", it.body) if len(text) >= config.MIN_BODY_CHARS else None
            if min(i.published.date() for i in items) < oldest_useful:
                return None
        return None

    def find(self, item: dict) -> Body | None:
        body = self.from_feed(item)
        if body:
            return body
        try:
            if self.fetch_page_html:   # the long summary also needs the pictures
                html = self.fetch_page_html(item["url"])
                text = feeds.html_to_text(html, config.BODY_CHAR_LIMIT)
            else:
                html, text = "", self.fetch_page_text(item["url"])[: config.BODY_CHAR_LIMIT]
        except Exception as exc:  # noqa: BLE001
            log.warning("article page failed: %s (%s)", item["url"], exc)
            return None
        return Body(text, "", "page", html) if len(text) >= config.MIN_BODY_CHARS else None
