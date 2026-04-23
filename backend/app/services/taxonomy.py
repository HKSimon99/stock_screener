from __future__ import annotations

import re
from typing import Iterable, Optional

from sqlalchemy import func, or_

_WHITESPACE_RE = re.compile(r"\s+")
_HANGUL_RE = re.compile(r"[\u3131-\u318E\uAC00-\uD7A3]")

_EXCHANGE_CANONICAL = {
    "NASDAQ": "NASDAQ",
    "NYSE": "NYSE",
    "NYSEAMER": "NYSE American",
    "NYSE AMERICAN": "NYSE American",
    "AMEX": "NYSE American",
    "NYSEARCA": "NYSE Arca",
    "NYSE ARCA": "NYSE Arca",
    "ARCA": "NYSE Arca",
    "CBOEBZX": "Cboe BZX",
    "CBOE BZX": "Cboe BZX",
    "BZX": "Cboe BZX",
    "IEX": "IEX",
    "KOSPI": "KOSPI",
    "KOSDAQ": "KOSDAQ",
    "KONEX": "KONEX",
    "ETF": "ETF",
}

_EXCHANGE_ALIASES = {
    "NASDAQ": {"NASDAQ"},
    "NYSE": {"NYSE"},
    "NYSE American": {"NYSEAMER", "NYSE AMERICAN", "AMEX"},
    "NYSE Arca": {"NYSEARCA", "NYSE ARCA", "ARCA"},
    "Cboe BZX": {"CBOEBZX", "CBOE BZX", "BZX"},
    "IEX": {"IEX"},
    "KOSPI": {"KOSPI"},
    "KOSDAQ": {"KOSDAQ"},
    "KONEX": {"KONEX"},
    "ETF": {"ETF"},
}

_SECTOR_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Semiconductors", ("semiconductor", "반도체")),
    ("Shipbuilding & Marine", ("shipbuilding", "marine", "조선")),
    ("Batteries & EV Materials", ("battery", "secondary cell", "2차전지", "cathode", "anode")),
    ("Biotech & Pharma", ("biotech", "pharma", "pharmaceutical", "bio", "제약", "바이오", "헬스케어")),
    ("Software & IT Services", ("software", "internet", "platform", "it service", "게임", "소프트웨어", "인터넷")),
    ("Automobiles", ("automobile", "auto", "자동차")),
    ("Banks", ("bank", "은행")),
    ("Insurance", ("insurance", "보험")),
    ("Financials", ("financial", "capital market", "증권", "금융")),
    ("Chemicals", ("chemical", "화학")),
    ("Retail & Consumer", ("retail", "consumer", "유통", "소매", "fashion", "apparel")),
    ("Construction & Materials", ("construction", "cement", "materials", "건설", "건자재")),
    ("Steel & Metals", ("steel", "metals", "철강", "금속")),
    ("Telecommunications", ("telecom", "communication", "통신")),
    ("Energy", ("energy", "oil", "gas", "정유", "에너지")),
    ("Utilities", ("utility", "utilities", "전력", "가스")),
    ("Transportation & Logistics", ("transport", "logistics", "shipping", "항공", "해운", "물류")),
    ("Media & Entertainment", ("media", "entertainment", "broadcast", "방송", "엔터", "콘텐츠")),
]


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def normalize_exchange(value: Optional[str]) -> Optional[str]:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    return _EXCHANGE_CANONICAL.get(cleaned.upper(), cleaned)


def normalize_sector(value: Optional[str]) -> Optional[str]:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    lowered = cleaned.lower()
    for canonical, keywords in _SECTOR_RULES:
        if any(keyword in lowered for keyword in keywords):
            return canonical
    if _HANGUL_RE.search(cleaned):
        return cleaned
    return cleaned.title() if cleaned.islower() else cleaned


def exchange_filter_condition(column, values: Iterable[str]):
    normalized_values = [normalize_exchange(value) for value in values]
    clauses = []
    for normalized in normalized_values:
        if not normalized:
            continue
        aliases = _EXCHANGE_ALIASES.get(normalized, {normalized.upper()})
        clauses.append(func.upper(column).in_(sorted(aliases)))
    if not clauses:
        return None
    return or_(*clauses)


def sector_filter_condition(column, values: Iterable[str]):
    clauses = []
    for value in values:
        normalized = normalize_sector(value)
        cleaned = _clean(value)
        if not normalized and not cleaned:
            continue
        matchers: set[str] = set()
        if normalized:
            matchers.add(normalized)
        if cleaned:
            matchers.add(cleaned)
        keyword_set: set[str] = set()
        if normalized:
            for canonical, keywords in _SECTOR_RULES:
                if canonical == normalized:
                    keyword_set.update(keywords)
                    break
        local_clauses = [func.lower(column) == matcher.lower() for matcher in matchers]
        for keyword in keyword_set:
            local_clauses.append(column.ilike(f"%{keyword}%"))
        clauses.append(or_(*local_clauses))
    if not clauses:
        return None
    return or_(*clauses)
