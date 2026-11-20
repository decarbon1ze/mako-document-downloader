from datetime import date

import pytest

from mako_document_downloader.naming import file_name, parse_title

# titles from bdew-mako.de and the names existing EDI@Energy tooling expects for them
CASES = [
    (
        (
            "UTILMD AHB Strom 2.1 - informatorische Lesefassung - konsolidierte Lesefassung mit Fehlerkorrekturen "
            "Stand: 18.02.2025"
        ),
        "AHB_UTILMD_S2.1",
        "xoxx",
        date(2025, 2, 18),
    ),
    ("UTILMD AHB Gas 1.0a - informatorische Lesefassung ", "AHB_UTILMD_G1.0a", "ooox", None),
    ("UTILMD AHB MaBiS 4.1 - informatorische Lesefassung", "AHB_UTILMD_4.1", "ooox", None),
    (
        (
            "UTILMD MIG Strom - informatorische Lesefassung S1.1 - konsolidierte Lesefassung mit Fehlerkorrekturen "
            "Stand: 23.10.2023"
        ),
        "MIG_UTILMD_S1.1",
        "xoxx",
        date(2023, 10, 23),
    ),
    (
        (
            "APERAK / CONTRL AHB 2.4a - informatorische Lesefassung - konsolidierte Lesefassung mit Fehlerkorrekturen "
            "Stand: 25.02.2025"
        ),
        "AHB_CONTRL_2.4a",
        "xoxx",
        date(2025, 2, 25),
    ),
    (
        (
            "REQOTE / QUOTES / ORDERS / ORDRSP / ORDCHG AHB 2.2 - informatorische Lesefassung -  außerordentliche "
            "Veröffentlichung "
        ),
        "AHB_ORDCHG_2.2",
        "oxox",
        None,
    ),
    (
        (
            "Herkunftsnachweisregister AHB 2.3c - informatorische Lesefassung - konsolidierte Lesefassung mit "
            "Fehlerkorrekturen Stand: 19.06.2023"
        ),
        "AHB_2.3c",
        "xoxx",
        date(2023, 6, 19),
    ),
    (
        "QUOTES MIG - informatorische Lesefassung 1.3 -  außerordentliche Veröffentlichung Stand: 26.07.2024",
        "MIG_QUOTES_1.3",
        "oxox",
        date(2024, 7, 26),
    ),
    (
        (
            "Entscheidungsbaum-Diagramme und Codelisten - informatorische Lesefassung 3.5 -  außerordentliche "
            "Veröffentlichung Stand: 08.01.2025"
        ),
        "EBD_3.5",
        "oxox",
        date(2025, 1, 8),
    ),
    (
        "Entscheidungsbaum-Diagramme und Codelisten 4.0b mit Fehlerkorrekturen Stand: 7.11.2024",
        "EBD_4.0b",
        "xooo",
        date(2024, 11, 7),
    ),
    ("Allgemeine Festlegungen 6.1a - informatorische Lesefassung", "allgemeinefestlegungen_6.1a", "ooox", None),
    ("API-Guideline 1.0b - informatorische Lesefassung", "apiguideline_1.0b", "ooox", None),
    (
        (
            "Codeliste der Lokationsbündelstrukturen 1.0 - informatorische Lesefassung  - konsolidierte Lesefassung mit "
            "Fehlerkorrekturen Stand: 13.12.2024"
        ),
        "codelistederlokationsbndelstrukturen_1.0",
        "xoxx",
        date(2024, 12, 13),
    ),
    ("Kaskade XSD 1.0 ", "kaskadexsd_1.0", "oooo", None),
    # no version in the title, only a date
    (
        (
            "Entscheidungsbaum-Diagramme und Codelisten - informatorische Lesefassung 31.07.2024 - konsolidierte "
            "Lesefassung mit Fehlerkorrekturen Stand: 31.07.2024"
        ),
        "EBD_0.0",
        "xoxx",
        date(2024, 7, 31),
    ),
    (
        (
            "UTILMD MIG Strom v- informatorische Lesefassung - konsolidierte Lesefassung mit Fehlerkorrekturen "
            "Stand: 12.07.2024"
        ),
        "MIG_UTILMD_S0.0",
        "xoxx",
        date(2024, 7, 12),
    ),
]


@pytest.mark.parametrize(("title", "label", "flags", "stand"), CASES)
def test_parse_title(title: str, label: str, flags: str, stand: date | None) -> None:
    info = parse_title(title)
    assert (info.label, info.flags, info.stand) == (label, flags, stand)


def test_file_name_uses_stand_as_publication_date() -> None:
    title = (
        "UTILMD AHB Strom 2.1 - informatorische Lesefassung - konsolidierte Lesefassung mit Fehlerkorrekturen "
        "Stand: 23.06.2025"
    )
    name = file_name(title, date(2025, 6, 23), date(2025, 7, 29), 11761, "docx")
    assert name == "AHB_UTILMD_S2.1_20250623_20250729_20250623_xoxx_11761.docx"


def test_file_name_falls_back_to_valid_from_and_open_end() -> None:
    name = file_name("MSCONS MIG 2.5 - informatorische Lesefassung", date(2026, 10, 1), None, 12345, "docx")
    assert name == "MIG_MSCONS_2.5_20261001_99991231_20261001_ooox_12345.docx"


def test_an_impossible_stand_date_is_ignored() -> None:
    info = parse_title("MSCONS AHB 3.1f - konsolidierte Lesefassung mit Fehlerkorrekturen Stand: 31.02.2025")
    assert (info.label, info.stand) == ("AHB_MSCONS_3.1f", None)
