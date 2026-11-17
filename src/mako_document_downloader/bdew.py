"""
The publications of bdew-mako.de (EDI@Energy): AHBs, MIGs, EBDs, code lists, XSDs, ... read from its public JSON API.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from mako_document_downloader import fetching
from mako_document_downloader.naming import file_name

BASE_URL = "https://www.bdew-mako.de/api"

EXTENSIONS = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "XSD": "xsd",
}
"""file types of the free files (bdew-mako.de also lists text/xml, but only for files that require a login)"""


@dataclass(frozen=True)
class Publication:
    """one downloadable file on bdew-mako.de"""

    file_id: int
    title: str
    valid_from: date
    valid_to: date | None
    extension: str
    free: bool

    @property
    def url(self) -> str:
        return f"{BASE_URL}/downloadFile/{self.file_id}"

    @property
    def file_name(self) -> str:
        return file_name(self.title, self.valid_from, self.valid_to, self.file_id, self.extension)


def _day(timestamp: str | None) -> date | None:
    """
    the day of an API timestamp; some are given as 22:00 or 23:00 on the day before (midnight German time in UTC)
    """
    if timestamp is None:
        return None
    moment = datetime.fromisoformat(timestamp)
    if (moment.hour, moment.minute, moment.second) in ((22, 0, 0), (23, 0, 0)):
        return moment.date() + timedelta(days=1)
    return moment.date()


def parse_publications(documents: list[dict[str, Any]]) -> list[Publication]:
    """the downloadable files of an /api/documents response (entries that are only links are skipped)"""
    publications = []
    for document in documents:
        extension = EXTENSIONS.get(document.get("fileType") or "")
        valid_from = _day(document.get("validFrom"))
        if document.get("fileId") is None or extension is None or valid_from is None:
            continue
        publications.append(
            Publication(
                file_id=document["fileId"],
                title=" ".join((document.get("title") or "").split()),
                valid_from=valid_from,
                valid_to=_day(document.get("validTo")),
                extension=extension,
                free=bool(document.get("isFree")),
            )
        )
    return publications


def fetch_publications(client: httpx.Client) -> list[Publication]:
    """all files listed on bdew-mako.de, including the ones that require a login (free=False)"""
    return parse_publications(fetching.get(client, f"{BASE_URL}/documents").json()["data"])
