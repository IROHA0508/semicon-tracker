"""The standard tag dictionary (data/tags.json) and the theory unit index (data/units.json).

Articles carry 1-4 standard tags. A card's related units are the units that share the most tags
with the article, then the ones asked most in interviews, then the more advanced ones.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from . import config

MAX_TAGS = 4
MAX_RELATED = 2


def _fold(text: str) -> str:
    """Compare tag names without case, spaces or punctuation: 'High-NA' == 'high na' == 'HighNA'."""
    return re.sub(r"[\s\-_·.,/()]+", "", text).lower()


@dataclass(frozen=True)
class TagBook:
    names: tuple[str, ...]          # standard tags in dictionary order
    group_of: dict[str, str]        # standard tag -> group
    lookup: dict[str, str]          # folded name / synonym / keyword -> standard tag
    entries: tuple[dict, ...]       # raw entries, for the prompt

    def normalize(self, raw: list[str]) -> tuple[list[str], list[str]]:
        """(standard tags in the order given, deduplicated, at most 4; strings that matched nothing)."""
        kept, dropped = [], []
        for value in raw or []:
            name = self.lookup.get(_fold(str(value)))
            if name is None:
                dropped.append(str(value))
            elif name not in kept:
                kept.append(name)
        return kept[:MAX_TAGS], dropped

    def prompt_lines(self) -> str:
        out = []
        for e in self.entries:
            hints = []
            if e["synonyms"]:
                hints.append("동의어: " + ", ".join(e["synonyms"]))
            if e["keywords"]:
                hints.append("영문: " + ", ".join(e["keywords"]))
            out.append(f"- {e['name']} [{e['group']}]" + (" — " + "; ".join(hints) if hints else ""))
        return "\n".join(out)


@lru_cache(maxsize=None)
def _load_tagbook(path: str) -> TagBook:
    data = json.loads(open(path, encoding="utf-8").read())
    names, group_of, lookup, entries = [], {}, {}, []
    for group in data["groups"]:
        for tag in group["tags"]:
            name = tag["name"]
            names.append(name)
            group_of[name] = group["name"]
            entries.append({"name": name, "group": group["name"],
                            "synonyms": tag.get("synonyms", []), "keywords": tag.get("keywords", [])})
    # Exact names first, then synonyms and keywords. A synonym never overrides another tag's name,
    # and the first tag that lists a synonym keeps it.
    for name in names:
        lookup[_fold(name)] = name
    for e in entries:
        for alias in [*e["synonyms"], *e["keywords"]]:
            lookup.setdefault(_fold(alias), e["name"])
    return TagBook(tuple(names), group_of, lookup, tuple(entries))


def tagbook() -> TagBook:
    return _load_tagbook(str(config.TAGS_FILE))


@lru_cache(maxsize=None)
def _load_units(path: str) -> tuple[dict, ...]:
    return tuple(json.loads(open(path, encoding="utf-8").read())["units"])


def units() -> tuple[dict, ...]:
    return _load_units(str(config.UNITS_FILE))


def _unit_number(code: str) -> tuple[int, int]:
    floor, num = code.split("-")
    return int(floor), int(num)


def related_units(tags: list[str], unit_index=None, limit: int = MAX_RELATED) -> list[str]:
    """Unit codes for an article's tags: most shared tags → most stars → higher unit number."""
    wanted = set(tags)
    scored = []
    for unit in unit_index if unit_index is not None else units():
        shared = len(wanted & set(unit["tags"]))
        if shared:
            scored.append((shared, unit["stars"], _unit_number(unit["code"]), unit["code"]))
    scored.sort(reverse=True)
    return [s[3] for s in scored[:limit]]
