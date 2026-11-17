from datetime import date
from pathlib import Path, PurePosixPath

from conftest import FakeSites

from mako_document_downloader.bdew import Publication
from mako_document_downloader.bnetza import RegulatoryDocument
from mako_document_downloader.sync import Report, Selection, plan, synchronize

TODAY = date(2026, 11, 16)

AHB = Publication(
    file_id=11761,
    title="UTILMD AHB Strom 2.1 - informatorische Lesefassung",
    valid_from=date(2025, 6, 6),
    valid_to=date(2026, 3, 31),
    extension="docx",
    free=True,
)
AHB_PATHS = [
    PurePosixPath("edi_energy_de/FV2504/AHB_UTILMD_S2.1_20250606_20260331_20250606_ooox_11761.docx"),
    PurePosixPath("edi_energy_de/FV2510/AHB_UTILMD_S2.1_20250606_20260331_20250606_ooox_11761.docx"),
]
PDF = Publication(11762, "UTILMD AHB Strom 2.1", date(2025, 6, 6), None, "pdf", True)
LOCKED = Publication(11763, "UTILMD AHB Strom 2.1", date(2025, 6, 6), None, "pdf", False)
WIM = RegulatoryDocument("WiM_Teil1", "WiM Teil 1", date(2025, 6, 6), None, "https://bnetza.example/wim.pdf")
WIM_PATH = PurePosixPath("bnetza/WiM_Teil1_20250606_99991231.pdf")


def test_plan_applies_the_selection() -> None:
    everything = plan([AHB, PDF, LOCKED], [WIM], Selection(), TODAY)
    assert [d.url.rsplit("/", 1)[1] for d in everything] == ["11761", "11762", "wim.pdf"]
    assert list(everything[0].paths) == AHB_PATHS

    selection = Selection(
        format_versions=frozenset({"FV2510"}), extensions=frozenset({"docx"}), sources=frozenset({"bdew"})
    )
    [only] = plan([AHB, PDF, LOCKED], [WIM], selection, TODAY)
    assert list(only.paths) == AHB_PATHS[1:]


def test_downloads_once_and_skips_existing_files(sites: FakeSites, tmp_path: Path) -> None:
    sites.files["/api/downloadFile/11761"] = b"ahb"
    downloads = plan([AHB], [], Selection())
    with sites.client() as client:
        first = synchronize(client, tmp_path, downloads, Selection())
        second = synchronize(client, tmp_path, downloads, Selection())

    assert sorted(first.added) == AHB_PATHS
    assert all((tmp_path / path).read_bytes() == b"ahb" for path in AHB_PATHS)
    assert sites.requests == ["/api/downloadFile/11761"]
    assert (second.changed, second.unchanged) == (False, 2)
    assert not list(tmp_path.rglob(".*.part"))


def test_bnetza_documents_are_rewritten_when_their_content_changes(sites: FakeSites, tmp_path: Path) -> None:
    downloads = plan([], [WIM], Selection())
    with sites.client() as client:
        sites.files["/wim.pdf"] = b"v1"
        assert synchronize(client, tmp_path, downloads, Selection()).added == [WIM_PATH]
        assert synchronize(client, tmp_path, downloads, Selection()).unchanged == 1
        sites.files["/wim.pdf"] = b"v2"
        assert synchronize(client, tmp_path, downloads, Selection()).updated == [WIM_PATH]
    assert (tmp_path / WIM_PATH).read_bytes() == b"v2"


def test_prune_only_touches_selected_document_files(sites: FakeSites, tmp_path: Path) -> None:
    stale = tmp_path / "edi_energy_de/FV2510/AHB_UTILMD_S2.0_20250606_20260331_20250606_ooox_1.docx"
    other_version = tmp_path / "edi_energy_de/FV2404/AHB_UTILMD_S1.0_20240403_20250605_20240403_ooox_2.docx"
    keep = [tmp_path / "edi_energy_de/FV2510/README.md", tmp_path / "edi_energy_de/FV2510/.gitkeep", other_version]
    for file in [stale, *keep]:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"")
    sites.files["/api/downloadFile/11761"] = b"ahb"
    selection = Selection(format_versions=frozenset({"FV2510"}))

    with sites.client() as client:
        dry = synchronize(client, tmp_path, plan([AHB], [], selection), selection, prune=True, dry_run=True)
        assert stale.exists()
        report = synchronize(client, tmp_path, plan([AHB], [], selection), selection, prune=True)

    assert dry.removed == report.removed == [PurePosixPath("edi_energy_de/FV2510", stale.name)]
    assert dry.added == report.added == AHB_PATHS[1:]
    assert not stale.exists()
    assert all(file.exists() for file in keep)


def test_retries_transient_errors_and_reports_failures(sites: FakeSites, tmp_path: Path) -> None:
    sites.files["/api/downloadFile/11761"] = b"ahb"
    sites.failures["/api/downloadFile/11761"] = [503, 502]
    sites.failures["/api/downloadFile/11762"] = [404]
    with sites.client() as client:
        report = synchronize(client, tmp_path, plan([AHB, PDF], [], Selection()), Selection())

    assert sorted(report.added) == AHB_PATHS
    assert [title for title, _ in report.failed] == [PDF.title]
    assert sites.requests.count("/api/downloadFile/11762") == 1
    assert "Failed:" in report.summary()


def test_summary_is_a_commit_message() -> None:
    report = Report(added=AHB_PATHS * 3)
    summary = report.summary(max_lines=4)
    assert summary.splitlines()[0] == "Update MaKo documents: 6 added, 0 updated, 0 removed"
    assert "- … and 2 more" in summary


def test_open_ended_documents_join_format_versions_that_have_documents_or_started() -> None:
    new = Publication(20000, "MSCONS MIG 2.6", date(2027, 4, 1), None, "docx", True)
    folders = {path.parts[1] for download in plan([PDF, new], [], Selection(), TODAY) for path in download.paths}
    assert folders == {"FV2504", "FV2510", "FV2604", "FV2610", "FV2704"}

    [later] = plan([PDF], [], Selection(), today=date(2027, 10, 1))
    assert [path.parts[1] for path in later.paths][-2:] == ["FV2704", "FV2710"]


def test_a_path_is_planned_only_once() -> None:
    downloads = plan([AHB, AHB], [], Selection(), TODAY)
    assert len(downloads) == 1


def test_prune_keeps_bnetza_documents_outside_the_selected_format_versions(sites: FakeSites, tmp_path: Path) -> None:
    current = tmp_path / WIM_PATH
    previous = tmp_path / "bnetza/WiM_Teil1_20231001_20250605.pdf"  # FV2310 to FV2410
    replaced = tmp_path / "bnetza/WiM_Teil1_20250606_20260930.pdf"  # FV2504 to FV2604, no longer listed
    for file in (current, previous, replaced):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"%PDF")
    sites.files["/wim.pdf"] = b"%PDF"
    sites.files["/api/downloadFile/11762"] = b"pdf"

    with sites.client() as client:
        for fv, removed in (("FV2404", []), ("FV2504", [replaced])):
            selection = Selection(format_versions=frozenset({fv}))
            report = synchronize(client, tmp_path, plan([PDF], [WIM], selection, TODAY), selection, prune=True)
            assert report.removed == [PurePosixPath("bnetza", file.name) for file in removed], fv
    assert current.exists() and previous.exists()


def test_an_empty_listing_prunes_nothing(sites: FakeSites, tmp_path: Path) -> None:
    existing = tmp_path / AHB_PATHS[0]
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"ahb")
    sites.files["/wim.pdf"] = b"%PDF"

    with sites.client() as client:
        report = synchronize(client, tmp_path, plan([], [WIM], Selection(), TODAY), Selection(), prune=True)

    assert report.removed == []
    assert existing.exists()


def test_an_invalid_url_is_reported_as_failure(sites: FakeSites, tmp_path: Path) -> None:
    broken = RegulatoryDocument("Broken", "Broken", date(2025, 6, 6), None, "https://bnetza.example:abc/x.pdf")
    sites.files["/wim.pdf"] = b"%PDF"
    with sites.client() as client:
        report = synchronize(client, tmp_path, plan([], [broken, WIM], Selection(), TODAY), Selection())
    assert [title for title, _ in report.failed] == ["Broken"]
    assert report.added == [WIM_PATH]


def test_permanent_client_errors_are_not_retried(sites: FakeSites, tmp_path: Path) -> None:
    sites.failures["/api/downloadFile/11762"] = [451]
    with sites.client() as client:
        report = synchronize(client, tmp_path, plan([PDF], [], Selection(), TODAY), Selection())
    assert len(report.failed) == 1
    assert sites.requests == ["/api/downloadFile/11762"]
