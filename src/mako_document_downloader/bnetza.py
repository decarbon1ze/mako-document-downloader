"""
Process rules of the Bundesnetzagentur (GPKE, WiM, MaBiS, ...). They are not offered by an API, so the package ships a
list of them (bnetza_documents.json) which users can extend or override with their own file.
"""

import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

from mako_document_downloader.naming import OPEN_END


@dataclass(frozen=True)
class RegulatoryDocument:
    name: str
    """short unique name, the start of the file name, e.g. WiM_Teil1"""
    title: str
    valid_from: date
    valid_to: date | None
    url: str

    @property
    def file_name(self) -> str:
        end = self.valid_to or OPEN_END
        return f"{self.name}_{self.valid_from:%Y%m%d}_{end:%Y%m%d}.pdf"


def _parse(entries: list[dict[str, Any]]) -> list[RegulatoryDocument]:
    return [
        RegulatoryDocument(
            name=entry["name"],
            title=entry["title"],
            valid_from=date.fromisoformat(entry["valid_from"]),
            valid_to=date.fromisoformat(entry["valid_to"]) if entry.get("valid_to") else None,
            url=entry["url"],
        )
        for entry in entries
    ]


def load_documents(extra_list: Path | None = None) -> list[RegulatoryDocument]:
    """the bundled list, extended by the entries of extra_list (an entry with the same name replaces the bundled one)"""
    bundled = resources.files(__package__).joinpath("bnetza_documents.json").read_text(encoding="utf-8")
    documents = {document.name: document for document in _parse(json.loads(bundled))}
    if extra_list is not None:
        documents |= {document.name: document for document in _parse(json.loads(extra_list.read_text("utf-8")))}
    return list(documents.values())
