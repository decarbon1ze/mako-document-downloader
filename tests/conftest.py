"""a fake of bdew-mako.de and the Bundesnetzagentur, served through httpx.MockTransport"""

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def api_document(
    file_id: int | None, title: str, valid_from: str, valid_to: str | None, **extra: Any
) -> dict[str, Any]:
    return {
        "id": 1,
        "fileId": file_id,
        "title": title,
        "isFree": True,
        "validFrom": valid_from,
        "validTo": valid_to,
        "fileType": DOCX,
        "link": None,
        **extra,
    }


@dataclass
class FakeSites:
    documents: list[dict[str, Any]] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)
    """path or URL -> content"""
    failures: dict[str, list[int]] = field(default_factory=dict)
    """path -> status codes to answer with before succeeding"""
    requests: list[str] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        pending = self.failures.get(request.url.path)
        if pending:
            return httpx.Response(pending.pop(0))
        if request.url.path == "/api/documents":
            return httpx.Response(200, json={"data": self.documents})
        content = self.files.get(request.url.path)
        if content is None and request.url.host == "www.bundesnetzagentur.de":
            content = b"%PDF bundled"
        return httpx.Response(200, content=content) if content is not None else httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))


@pytest.fixture
def sites(monkeypatch: pytest.MonkeyPatch) -> FakeSites:
    monkeypatch.setattr("time.sleep", lambda _: None)
    return FakeSites()
