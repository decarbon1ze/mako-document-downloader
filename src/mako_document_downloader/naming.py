"""
File names for the documents of bdew-mako.de.

The names follow the convention that existing EDI@Energy tooling (e.g. kohlrahbi, migmose) reads:

    <label>_<valid from>_<valid to>_<publication date>_<flags>_<file id>.<extension>

* label: "AHB_<format>_<version>" or "MIG_<format>_<version>" for the message guides (e.g. AHB_UTILMD_S2.1),
  "EBD_<version>" for the decision trees, otherwise the lower-cased title without spaces and special characters
  followed by the version (e.g. codelistederkonfigurationen_1.3b)
* dates as yyyymmdd, an open end as 99991231; the publication date is the "Stand" date of the title or the start of
  validity if the title has none
* version: as in the title; titles without one (a handful of 2024 corrections carry only a date) get 0.0, because
  the readers of this convention require a version
* flags: four characters, "x" (yes) or "o" (no), for: contains error corrections, extraordinary publication,
  consolidated reading version, informational reading version (the order in which the edi_energy_scraper, and with
  it kohlrahbi, reads them)
"""

import re
from dataclasses import dataclass
from datetime import date

OPEN_END = date(9999, 12, 31)
MISSING_VERSION = "0.0"

EDIFACT_FORMATS = frozenset(
    {
        "APERAK",
        "COMDIS",
        "CONTRL",
        "IFTSTA",
        "INSRPT",
        "INVOIC",
        "MSCONS",
        "ORDCHG",
        "ORDERS",
        "ORDRSP",
        "PARTIN",
        "PRICAT",
        "QUOTES",
        "REMADV",
        "REQOTE",
        "UTILMD",
        "UTILTS",
    }
)

_STAND = re.compile(r"Stand:?\s*(\d{1,2})\.(\d{1,2})\.(\d{4})")
_DATE = re.compile(r"(?<![\w.])\d{1,2}\.\d{1,2}\.\d{4}(?![\w.])")
_VERSION = re.compile(r"(?<![\w.])([SG]?\d+\.\d+(?:\.\d+)?[a-z]?)(?![\w.])")
_WORD = re.compile(r"[\wÄÖÜäöüß]+")
_INFORMATIONAL = "informatorische lesefassung"


@dataclass(frozen=True)
class TitleInfo:
    """what the title of a document on bdew-mako.de tells about it"""

    label: str
    version: str | None
    stand: date | None
    consolidated: bool
    extraordinary: bool
    corrected: bool
    informational: bool

    @property
    def flags(self) -> str:
        marks = (self.corrected, self.extraordinary, self.consolidated, self.informational)
        return "".join("x" if mark else "o" for mark in marks)


def _ascii_slug(text: str) -> str:
    """lower case, only a-z and 0-9 (umlauts and other characters are dropped, not transliterated)"""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _guide_label(kind: str, words: list[str], version: str) -> str:
    """label of an AHB or MIG, e.g. AHB_UTILMD_S2.1"""
    kind_position = words.index(kind)
    formats = [word for word in words[:kind_position] if word in EDIFACT_FORMATS]
    parts = [kind]
    if formats:
        # titles covering several formats ("INVOIC / REMADV AHB") are named after the last one
        parts.append(formats[-1])
    following = words[kind_position + 1] if kind_position + 1 < len(words) else ""
    if formats and formats[-1] == "UTILMD" and version[0].isdigit() and following in ("Strom", "Gas"):
        # the UTILMD guides are versioned per Sparte (S2.1, G1.0a); some titles name the Sparte only in words
        version = following[0] + version
    parts.append(version)
    return "_".join(parts)


def parse_title(title: str) -> TitleInfo:
    stand_match = _STAND.search(title)
    stand = None
    if stand_match:
        day, month, year = (int(group) for group in stand_match.groups())
        try:
            stand = date(year, month, day)
        except ValueError:
            stand = None  # a typo such as "Stand: 31.02.2025"; the start of validity is used instead
    # some titles carry a date in place of a version ("... informatorische Lesefassung 31.07.2024 - ...")
    without_stand = _DATE.sub("", _STAND.sub("", title))
    version_match = _VERSION.search(without_stand)
    version = version_match.group(1) if version_match else None
    before_version = without_stand[: version_match.start()] if version_match else without_stand.split(" - ")[0]
    words = _WORD.findall(before_version)
    lowered = title.lower()

    label_version = version or MISSING_VERSION
    if "AHB" in words or "MIG" in words:
        label = _guide_label("AHB" if "AHB" in words else "MIG", words, label_version)
    elif lowered.startswith("entscheidungsbaum"):
        label = f"EBD_{label_version}"
    else:
        name = re.sub(_INFORMATIONAL, "", before_version, flags=re.IGNORECASE)
        label = f"{_ascii_slug(name)}_{label_version}"

    return TitleInfo(
        label=label,
        version=version,
        stand=stand,
        consolidated="konsolidierte lesefassung" in lowered,
        extraordinary="außerordentliche" in lowered,
        corrected="fehlerkorrektur" in lowered,
        informational=_INFORMATIONAL in lowered,
    )


def file_name(title: str, valid_from: date, valid_to: date | None, file_id: int, extension: str) -> str:
    info = parse_title(title)
    published = info.stand or valid_from
    end = valid_to or OPEN_END
    return f"{info.label}_{valid_from:%Y%m%d}_{end:%Y%m%d}_{published:%Y%m%d}_{info.flags}_{file_id}.{extension}"
