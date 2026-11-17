from datetime import date

from conftest import FakeSites, api_document

from mako_document_downloader.bdew import fetch_publications


def test_fetch_publications(sites: FakeSites) -> None:
    sites.documents = [
        api_document(11761, "UTILMD  AHB Strom 2.1 ", "2025-06-23T00:00:00", "2025-07-29T00:00:00"),
        # midnight German time given in UTC
        api_document(10155, "UTILTS AHB 1.0", "2025-04-04T00:00:00", "2024-12-11T23:00:00"),
        api_document(10156, "UTILTS MIG 1.0", "2025-04-04T00:00:00", "2025-03-31T22:00:00"),
        # a real time of day stays on its day
        api_document(10157, "UTILTS MIG 1.1", "2025-04-04T00:00:00", "2025-09-30T23:59:59"),
        # only a link, nothing to download
        api_document(None, "API-Webdienste Strom - Release 1.0.0", "2026-01-29T00:00:00", None, fileType=None),
        api_document(5, "INVOIC AHB 1.0", "2026-04-01T00:00:00", None, isFree=False, fileType="application/pdf"),
        # files that require a login can be XML; there is nothing to download for us
        api_document(6, "INVOIC AHB 1.0", "2026-04-01T00:00:00", None, isFree=False, fileType="text/xml"),
    ]
    with sites.client() as client:
        publications = fetch_publications(client)

    assert [p.file_id for p in publications] == [11761, 10155, 10156, 10157, 5]
    first = publications[0]
    assert first.title == "UTILMD AHB Strom 2.1"
    assert first.url == "https://www.bdew-mako.de/api/downloadFile/11761"
    assert [p.valid_to for p in publications[1:4]] == [date(2024, 12, 12), date(2025, 4, 1), date(2025, 9, 30)]
    assert (publications[4].free, publications[4].extension, publications[4].valid_to) == (False, "pdf", None)


def test_the_listing_is_retried(sites: FakeSites) -> None:
    sites.documents = [api_document(1, "UTILTS AHB 1.0", "2025-04-04T00:00:00", None)]
    sites.failures["/api/documents"] = [503, 502]
    with sites.client() as client:
        assert len(fetch_publications(client)) == 1


def test_a_missing_title_does_not_break_the_listing(sites: FakeSites) -> None:
    sites.documents = [api_document(1, None, "2025-04-04T00:00:00", None)]  # type: ignore[arg-type]
    with sites.client() as client:
        [publication] = fetch_publications(client)
    assert publication.file_name == "_0.0_20250404_99991231_20250404_oooo_1.docx"
