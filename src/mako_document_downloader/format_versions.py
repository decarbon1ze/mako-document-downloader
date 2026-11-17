"""
The EDI@Energy format versions ("Formatversionen") and the days they take effect.

A format version is named FVyymm after its start month: regularly 1 April and 1 October. The table holds the format
versions up to now with their actual start (some were moved, e.g. FV2504 to 06.06.2025); later ones are assumed to
follow the regular schedule. A format version lasts until the next one starts.
"""

import re
from datetime import date

FORMAT_VERSION_STARTS: dict[str, date] = {
    "FV2104": date(2021, 4, 1),
    "FV2110": date(2021, 10, 1),
    "FV2210": date(2022, 10, 1),
    "FV2304": date(2023, 4, 1),
    "FV2310": date(2023, 10, 1),
    "FV2404": date(2024, 4, 3),
    "FV2410": date(2024, 10, 1),
    "FV2504": date(2025, 6, 6),
    "FV2510": date(2025, 10, 1),
    "FV2604": date(2026, 4, 1),
    "FV2610": date(2026, 10, 1),
}

_KNOWN = sorted(FORMAT_VERSION_STARTS.items(), key=lambda item: item[1])
_REGULAR_NAME = re.compile(r"FV\d\d(04|10)")


def _next_regular_start(after: date) -> date:
    if after.month < 4:
        return date(after.year, 4, 1)
    if after.month < 10:
        return date(after.year, 10, 1)
    return date(after.year + 1, 4, 1)


def _starts_until(day: date) -> list[tuple[str, date]]:
    """the known format versions, extended by regular ones up to the given day"""
    starts = list(_KNOWN)
    while (start := _next_regular_start(starts[-1][1])) <= day:
        starts.append((f"FV{start:%y%m}", start))
    return starts


def format_version_on(day: date) -> str:
    """the format version in effect on the given day (the oldest known one for days before it)"""
    current = _KNOWN[0][0]
    for name, start in _starts_until(day):
        if start > day:
            break
        current = name
    return current


def format_versions_for(valid_from: date, valid_to: date | None, horizon: date | None = None) -> list[str]:
    """
    all format versions a document valid from valid_from to valid_to (inclusive, None: open-ended) belongs to.
    Open-ended documents belong to all format versions up to the newest one in the table or started by the horizon
    (callers pass e.g. today or the latest start of any published document).
    bdew-mako.de sometimes lists an end before the start; such documents belong to the format version of their start.
    """
    end = max(valid_from, valid_to or max(_KNOWN[-1][1], horizon or _KNOWN[-1][1]))
    names = [name for name, _ in _starts_until(end)]
    first = names.index(format_version_on(valid_from))
    last = names.index(format_version_on(end))
    return names[first : last + 1]


def start_of(name: str) -> date:
    """the first day of a known or regular future format version"""
    if name in FORMAT_VERSION_STARTS:
        return FORMAT_VERSION_STARTS[name]
    if not is_valid_name(name):
        raise ValueError(f"unknown format version {name!r}")
    return date(2000 + int(name[2:4]), int(name[4:6]), 1)


def is_valid_name(name: str) -> bool:
    """a known format version or a regular future one (FVyy04, FVyy10)"""
    return name in FORMAT_VERSION_STARTS or (bool(_REGULAR_NAME.fullmatch(name)) and name > _KNOWN[-1][0])
