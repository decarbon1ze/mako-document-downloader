from datetime import date

from mako_document_downloader.format_versions import format_version_on, format_versions_for, is_valid_name


def test_format_version_on_uses_actual_start_dates() -> None:
    assert format_version_on(date(2025, 6, 5)) == "FV2410"
    assert format_version_on(date(2025, 6, 6)) == "FV2504"
    assert format_version_on(date(2030, 1, 1)) == "FV2910"


def test_days_before_the_first_known_version_belong_to_it() -> None:
    assert format_version_on(date(2015, 10, 1)) == "FV2104"


def test_span() -> None:
    assert format_versions_for(date(2025, 6, 6), date(2026, 3, 31)) == ["FV2504", "FV2510"]
    assert format_versions_for(date(2026, 4, 1), None) == ["FV2604", "FV2610"]


def test_end_before_start_belongs_to_the_version_of_the_start() -> None:
    assert format_versions_for(date(2025, 6, 6), date(2025, 2, 24)) == ["FV2504"]


def test_later_format_versions_follow_the_regular_schedule() -> None:
    assert format_version_on(date(2027, 3, 31)) == "FV2610"
    assert format_version_on(date(2027, 4, 1)) == "FV2704"
    assert format_versions_for(date(2027, 4, 1), date(2028, 4, 1)) == ["FV2704", "FV2710", "FV2804"]
    assert format_versions_for(date(2027, 10, 1), None) == ["FV2710"]


def test_valid_names() -> None:
    assert is_valid_name("FV2504")
    assert is_valid_name("FV2704")
    assert not is_valid_name("FV2204")  # never existed
    assert not is_valid_name("FV2705")
