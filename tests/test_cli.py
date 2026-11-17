import json
from pathlib import Path

import httpx
import pytest
from conftest import FakeSites, api_document

from mako_document_downloader import cli


@pytest.fixture
def fake_sites(sites: FakeSites, monkeypatch: pytest.MonkeyPatch) -> FakeSites:
    monkeypatch.setattr(cli, "_client", lambda *_: sites.client())
    sites.documents = [api_document(12306, "MSCONS MIG 2.5 - informatorische Lesefassung", "2026-10-01T00:00:00", None)]
    sites.files["/api/downloadFile/12306"] = b"mig"
    sites.files["/wim.pdf"] = b"%PDF custom"
    return sites


def _bnetza_list(tmp_path: Path) -> Path:
    entries = [
        {
            "name": "WiM_Teil1",
            "title": "WiM Teil 1",
            "valid_from": "2025-06-06",
            "valid_to": None,
            "url": "https://bnetza.example/wim.pdf",
        }
    ]
    path = tmp_path / "bnetza.json"
    path.write_text(json.dumps(entries))
    return path


def test_download(fake_sites: FakeSites, tmp_path: Path) -> None:
    output, summary = tmp_path / "out", tmp_path / "summary.md"
    exit_code = cli.main(
        [
            "download",
            "-o",
            str(output),
            "-f",
            "fv2610",
            "--bnetza-list",
            str(_bnetza_list(tmp_path)),
            "--summary-file",
            str(summary),
        ]
    )

    assert exit_code == 0
    assert (
        output / "edi_energy_de/FV2610/MIG_MSCONS_2.5_20261001_99991231_20261001_ooox_12306.docx"
    ).read_bytes() == b"mig"
    # the own list replaces the bundled WiM_Teil1 and keeps the other bundled documents
    assert (output / "bnetza/WiM_Teil1_20250606_99991231.pdf").read_bytes() == b"%PDF custom"
    assert (output / "bnetza/MaBiS_20250606_99991231.pdf").read_bytes() == b"%PDF bundled"
    assert summary.read_text().startswith("Update MaKo documents: 8 added")


def test_download_fails_when_a_file_fails(fake_sites: FakeSites, tmp_path: Path) -> None:
    del fake_sites.files["/api/downloadFile/12306"]
    assert cli.main(["download", "-o", str(tmp_path), "-s", "bdew"]) == 1


def test_download_fails_when_the_listing_is_unavailable(fake_sites: FakeSites, tmp_path: Path) -> None:
    fake_sites.failures["/api/documents"] = [404]
    assert cli.main(["download", "-o", str(tmp_path), "-s", "bdew"]) == 2


def test_list_json(fake_sites: FakeSites, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["list", "--json", "-s", "bdew"]) == 0
    [row] = json.loads(capsys.readouterr().out)
    assert row["paths"] == ["edi_energy_de/FV2610/MIG_MSCONS_2.5_20261001_99991231_20261001_ooox_12306.docx"]


def test_unknown_format_version_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["list", "-f", "FV1999"])
    assert "unknown format version" in capsys.readouterr().err


def test_real_client_identifies_the_tool() -> None:
    with cli._client() as client:
        assert isinstance(client, httpx.Client)
        assert client.headers["User-Agent"].startswith("mako-document-downloader/")
