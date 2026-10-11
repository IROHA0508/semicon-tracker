"""Read WordPress RSS feed pages and turn their items into article metadata.

Only the title, link, publish time and feed categories are stored. The article body in the feed
(content:encoded) is kept in memory for the summary step of the same run and never written out.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import feedparser
import requests

from . import config

log = logging.getLogger(__name__)
KST = ZoneInfo(config.TIMEZONE)


class FeedError(Exception):
    """The response was not a feed we can read."""


@dataclass
class Item:
    source: str           # Source.key
    company: str
    lang: str
    title: str
    url: str              # canonical link without query string or fragment
    published: datetime   # timezone-aware, Korean time
    categories: list[str] = field(default_factory=list)
    author: str = ""
    # Article HTML from the feed. In memory only: the summary step reads it, nothing stores it.
    body: str = field(default="", repr=False)

    @property
    def key(self) -> str:
        return normalize_url(self.url)


def clean_url(url: str) -> str:
    """Drop the query string (utm_*) and fragment; always https."""
    parts = urlsplit(url.strip())
    return urlunsplit(("https", parts.netloc.lower(), parts.path or "/", "", ""))


def normalize_url(url: str) -> str:
    """Key for comparing links: https, no www., decoded path, no trailing slash, no query or fragment."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = unquote(parts.path).rstrip("/") or "/"
    return f"https://{host}{path}"


def make_id(company: str, url: str) -> str:
    """skhynix-fact-11 for readable ASCII slugs; samsung-<hash> for Korean (percent-encoded) slugs."""
    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].lower()
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{2,59}", slug):
        return f"{company}-{slug}"
    return f"{company}-{hashlib.sha1(normalize_url(url).encode('utf-8')).hexdigest()[:10]}"


def classify(source: config.Source, categories: list[str]) -> tuple[str, str] | None:
    """(channel, kind) for an item, or None when the source's category rules say to skip it."""
    if not source.categories:
        return source.channel, source.kind
    have = {c.strip() for c in categories}
    for category, channel, kind in source.categories:
        if category in have:
            return channel, kind
    return None


def page_url(source: config.Source, page: int) -> str:
    return source.feed if page == 1 else f"{source.feed}?paged={page}"


def parse_feed(xml: bytes | str, source: config.Source) -> list[Item]:
    feed = feedparser.parse(xml)
    if not feed.entries and (feed.bozo or not feed.get("feed", {}).get("title")):
        raise FeedError(f"not an RSS feed ({feed.get('bozo_exception') or 'no channel title'})")
    items = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not title or not link or not stamp:
            log.warning("%s: skipped an item without title, link or date (%r)", source.key, title or link)
            continue
        published = datetime(*stamp[:6], tzinfo=timezone.utc).astimezone(KST)
        categories = [t.get("term", "").strip() for t in entry.get("tags", []) if t.get("term")]
        content = entry.get("content") or []
        body = (content[0].get("value") if content else "") or entry.get("summary") or ""
        items.append(Item(source.key, source.company, source.lang, title, clean_url(link), published, categories,
                          (entry.get("author") or "").strip(), body))
    return items


# Feed footers and slider controls that are not part of the article.
_NOISE_LINE = re.compile(r"^(The post .* first appeared on .*|previous arrow|next arrow|Choose slide to display\.?)$")
_BLOCKS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "td", "th", "figcaption", "blockquote", "br", "div", "tr")


def html_to_text(html: str, limit: int | None = None) -> str:
    """Readable plain text from article HTML: one block per line, no scripts, styles or image data."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "img", "form", "button"]):
        tag.decompose()
    for tag in soup.find_all(_BLOCKS):
        tag.insert_before("\n")
    lines = []
    for raw in soup.get_text().splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line and not _NOISE_LINE.match(line) and (not lines or lines[-1] != line):
            lines.append(line)
    text = "\n".join(lines)
    return text[:limit] if limit else text


def page_text(html: str) -> str:
    """Main text of an article web page (fallback when the feed no longer carries the article)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["nav", "header", "footer", "aside"]):
        tag.decompose()
    node = (soup.select_one(".entry-content") or soup.select_one(".post-content") or soup.find("article")
            or soup.find("main") or soup.body or soup)
    return html_to_text(str(node))


def fetch_article_page(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": config.USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
                        timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    return page_text(resp.text)


def fetch_page(source: config.Source, page: int) -> list[Item] | None:
    """Items on one feed page, or None when the page does not exist (past the last page)."""
    resp = requests.get(
        page_url(source, page),
        headers={"User-Agent": config.USER_AGENT,
                 "Accept": "application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.5"},
        timeout=config.HTTP_TIMEOUT,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    items = parse_feed(resp.content, source)
    log.info("%s page %d: %d items", source.key, page, len(items))
    return items
