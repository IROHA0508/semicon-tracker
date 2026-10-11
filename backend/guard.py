"""Check every number with a unit in a Korean card against the article it was written from.

Claude often converts units (e.g. "$15 billion" → "150억 달러"). A number with a Korean scale word
(만·억·조) must match the source by value, so a slip of one digit ("15억 달러") is caught. A plain
number with a unit ("12단", "263%") must appear in the source as a number, allowing rounding.
Years, dates, quarters, generations and model names (HBM4, DDR5, 1c) are not checked.
"""
from __future__ import annotations

import re

KO_SCALE = {"천": 1e3, "만": 1e4, "억": 1e8, "조": 1e12}
EN_SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "quadrillion": 1e15,
            "k": 1e3, "mn": 1e6, "m": 1e6, "bn": 1e9, "b": 1e9, "tn": 1e12, "t": 1e12}
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
         "ten": 10, "eleven": 11, "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "hundred": 100, "dozen": 12, "double": 2, "twice": 2, "triple": 3, "half": 0.5}

NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# A number in the card is checked only when a scale word, a percent sign or a unit follows it.
UNIT = re.compile(r"\s?(%p?|퍼센트|배|단|개|건|명|곳|톤|장|대|원|달러|유로|엔|위안|GB|TB|Gb|Tb|MB|nm|mm|μm|㎛|℃|°C|"
                  r"kW|MW|GW|W|TWh|GWh|GHz|MHz|Gbps|GT/s|MT/s|나노|EB|PB)(?![A-Za-z])")
SCALE = re.compile(rf"\s?((?:[천만억조]\s?(?:(?:{NUM})\s?)?)*[천만억조])")
SKIP_AFTER = re.compile(r"\s?(년|월|일|분기|세대|차|번째|위|층|시|분|초|주|회|기|번|호)")
CARD_NUM = re.compile(rf"(?<![A-Za-z0-9.,])({NUM})")


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def _decimals(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def korean_value(first: str, scale_part: str) -> float:
    """'1' + '조 3,000억' → 1.3e12; '8' + '천억' → 8e11; '21' + '조 6천억' → 2.16e13."""
    total, current = 0.0, _num(first)
    chunk = ""
    for ch in re.findall(rf"{NUM}|[천만억조]", scale_part.replace(" ", "")):
        if ch in KO_SCALE:
            chunk += ch
            continue
        # A new number starts: close the previous chunk.
        total += current * _scale(chunk)
        current, chunk = _num(ch), ""
    total += current * _scale(chunk)
    return total


def _scale(chunk: str) -> float:
    value = 1.0
    for ch in chunk:
        value *= KO_SCALE[ch]
    return value


def source_numbers(text: str) -> tuple[set[float], set[float]]:
    """(plain numbers in the source, values with scale words applied)."""
    plain, scaled = set(), set()
    for m in re.finditer(rf"(?<![A-Za-z0-9.])({NUM})", text):
        plain.add(_num(m.group(1)))
    for m in re.finditer(rf"({NUM})\s?-?\s?(quadrillion|trillion|billion|million|thousand|bn|mn|tn|[kmbt])\b",
                         text, re.I):
        scaled.add(_num(m.group(1)) * EN_SCALE[m.group(2).lower()])
    for m in re.finditer(rf"({NUM})\s?((?:[천만억조]\s?(?:{NUM})?\s?)*[천만억조])", text):
        scaled.add(korean_value(m.group(1), m.group(2)))
    for word, value in WORDS.items():
        if re.search(rf"(?<![A-Za-z가-힣]){word}(?![A-Za-z])", text, re.I):
            plain.add(float(value))
    return plain, scaled


def card_numbers(text: str) -> list[tuple[str, float, bool, int]]:
    """Numbers to check in card text: (as written, value, has a Korean scale word, decimals)."""
    out, consumed = [], 0
    for m in CARD_NUM.finditer(text):
        if m.start() < consumed:
            continue  # the "6" of "21조 6천억" was read with "21"
        first, pos = m.group(1), m.end()
        dollar = text[max(0, m.start() - 2):m.start()].strip().endswith("$")
        scale = SCALE.match(text, pos)
        if scale:
            consumed = scale.end()
            written = text[m.start():scale.end()]
            unit = UNIT.match(text, scale.end())
            if unit:
                written += unit.group(0)
            out.append((written.strip(), korean_value(first, scale.group(1)), True, 0))
            continue
        if SKIP_AFTER.match(text, pos):
            continue
        unit = UNIT.match(text, pos)
        if unit or dollar:
            written = ("$" if dollar else "") + first + (unit.group(0) if unit else "")
            out.append((written.strip(), _num(first), False, _decimals(first)))
    return out


def _matches(value: float, scaled: bool, decimals: int, plain: set[float], big: set[float]) -> bool:
    if scaled:
        return any(abs(v - value) <= 0.025 * value for v in big | plain if v > 0)
    for v in plain | big:
        if v == value or round(v, decimals) == value:
            return True
    return False


def unsupported(card_text: str, source_text: str) -> list[str]:
    """Numbers in the card text that the source does not support, as written in the card."""
    plain, scaled = source_numbers(source_text)
    bad = []
    for written, value, is_scaled, decimals in card_numbers(card_text):
        if not _matches(value, is_scaled, decimals, plain, scaled) and written not in bad:
            bad.append(written)
    return bad
