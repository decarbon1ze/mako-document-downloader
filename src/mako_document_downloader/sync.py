"""
Brings an output directory up to date with the selected documents:

    <output>/edi_energy_de/<format version>/<file name>   files of bdew-mako.de, once per format version they belong to
    <output>/bnetza/<file name>                           process rules of the Bundesnetzagentur

Files of bdew-mako.de are never re-downloaded: their name contains the file id, which changes with every new upload.
The Bundesnetzagentur replaces files under the same URL, so its documents are fetched on every run and rewritten when
their content differs.
"""

import logging
import os
import re
import tempfile
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath

import httpx

from mako_document_downloader import fetching
from mako_document_downloader.bdew import EXTENSIONS, Publication
from mako_document_downloader.bnetza import RegulatoryDocument
from mako_document_downloader.format_versions import format_versions_for, start_of
from mako_document_downloader.naming import OPEN_END

BDEW_DIRECTORY = "edi_energy_de"
BNETZA_DIRECTORY = "bnetza"
SOURCES = ("bdew", "bnetza")
DOCUMENT_EXTENSIONS = frozenset(EXTENSIONS.values())
"""the file types the tool writes; pruning never touches other files (README, .gitkeep, ...)"""

_logger = logging.getLogger(__name__)
_FORMAT_VERSION_DIRECTORY = re.compile(r"FV\d{4}")
_BNETZA_FILE = re.compile(r".+_(\d{8})_(\d{8})\.pdf")


@dataclass(frozen=True)
class Selection:
    """which documents to download; None means no restriction"""

    format_versions: frozenset[str] | None = None
    extensions: frozenset[str] | None = None
    """file types of bdew-mako.de (the documents of the Bundesnetzagentur are PDFs and selected via sources)"""
    sources: frozenset[str] = frozenset(SOURCES)

    def covers(self, format_versions: Iterable[str]) -> list[str]:
        return [fv for fv in format_versions if self.format_versions is None or fv in self.format_versions]


@dataclass(frozen=True)
class Download:
    """one file to fetch and the places (relative to the output directory) to store it"""

    source: str
    url: str
    title: str
    paths: tuple[PurePosixPath, ...]
    refresh: bool
    """True: fetch even if all paths exist and overwrite them if the content changed"""


@dataclass
class Report:
    added: list[PurePosixPath] = field(default_factory=list)
    updated: list[PurePosixPath] = field(default_factory=list)
    removed: list[PurePosixPath] = field(default_factory=list)
    unchanged: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    """(title, error) of the downloads that failed"""

    def merge(self, other: "Report") -> None:
        self.added += other.added
        self.updated += other.updated
        self.removed += other.removed
        self.unchanged += other.unchanged
        self.failed += other.failed

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.removed)

    def headline(self) -> str:
        return (
            f"Update MaKo documents: {len(self.added)} added, {len(self.updated)} updated, {len(self.removed)} removed"
        )

    def summary(self, max_lines: int = 200) -> str:
        """a Markdown summary, usable as commit message"""
        lines = [self.headline()]
        for heading, paths in (("Added", self.added), ("Updated", self.updated), ("Removed", self.removed)):
            if paths:
                lines += ["", f"{heading}:"]
                lines += [f"- {path}" for path in sorted(paths)[:max_lines]]
                if len(paths) > max_lines:
                    lines.append(f"- … and {len(paths) - max_lines} more")
        if self.failed:
            lines += ["", "Failed:"] + [f"- {title}: {error}" for title, error in self.failed]
        return "\n".join(lines) + "\n"


def plan(
    publications: Sequence[Publication],
    regulatory: Sequence[RegulatoryDocument],
    selection: Selection,
    today: date | None = None,
) -> list[Download]:
    # open-ended documents also belong to format versions that started since the table was last updated, or that
    # documents have already been published for
    starts = [p.valid_from for p in publications] + [d.valid_from for d in regulatory]
    horizon = max([today or date.today(), *starts])
    downloads = []
    planned: set[PurePosixPath] = set()

    def add(source: str, url: str, title: str, paths: list[PurePosixPath], refresh: bool) -> None:
        new_paths = tuple(path for path in paths if path not in planned)
        if new_paths:
            planned.update(new_paths)
            downloads.append(Download(source, url, title, new_paths, refresh))

    if "bdew" in selection.sources:
        for publication in publications:
            if not publication.free:
                continue
            if selection.extensions is not None and publication.extension not in selection.extensions:
                continue
            versions = selection.covers(format_versions_for(publication.valid_from, publication.valid_to, horizon))
            paths = [PurePosixPath(BDEW_DIRECTORY, fv, publication.file_name) for fv in versions]
            add("bdew", publication.url, publication.title, paths, refresh=False)
    if "bnetza" in selection.sources:
        for document in regulatory:
            if selection.covers(format_versions_for(document.valid_from, document.valid_to, horizon)):
                path = PurePosixPath(BNETZA_DIRECTORY, document.file_name)
                add("bnetza", document.url, document.title, [path], refresh=True)
    return downloads


def _write(target: Path, content: bytes) -> None:
    """writes atomically, so an interrupted run never leaves a truncated file behind"""
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, partial = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".part")
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
        os.replace(partial, target)
    finally:
        Path(partial).unlink(missing_ok=True)


def _apply(client: httpx.Client, root: Path, download: Download, dry_run: bool) -> Report:
    report = Report()
    missing = [path for path in download.paths if not (root / path).exists()]
    if not missing and not download.refresh:
        report.unchanged += len(download.paths)
        return report
    if dry_run:
        report.added += missing
        report.unchanged += len(download.paths) - len(missing)
        return report
    content = fetching.get(client, download.url).content
    for path in download.paths:
        target = root / path
        if path in missing:
            _write(target, content)
            report.added.append(path)
            _logger.info("Added %s", path)
        elif download.refresh and target.read_bytes() != content:
            _write(target, content)
            report.updated.append(path)
            _logger.info("Updated %s", path)
        else:
            report.unchanged += 1
    return report


def _bnetza_file_selected(name: str, selection: Selection) -> bool:
    """whether a file in bnetza/ (<name>_<valid from>_<valid to>.pdf) belongs to the selected format versions"""
    if selection.format_versions is None:
        return True
    match = _BNETZA_FILE.fullmatch(name)
    if match is None:
        return False
    valid_from, valid_to = (datetime.strptime(group, "%Y%m%d").date() for group in match.groups())
    horizon = max(start_of(fv) for fv in selection.format_versions)
    return bool(selection.covers(format_versions_for(valid_from, None if valid_to == OPEN_END else valid_to, horizon)))


def _managed_files(root: Path, selection: Selection, sources: Iterable[str]) -> Iterable[PurePosixPath]:
    """the existing files of the given sources a run with this selection is responsible for (pruning candidates)"""
    sources = set(sources) & selection.sources
    if "bdew" in sources and (root / BDEW_DIRECTORY).is_dir():
        for directory in (root / BDEW_DIRECTORY).iterdir():
            if not directory.is_dir() or not _FORMAT_VERSION_DIRECTORY.fullmatch(directory.name):
                continue
            if selection.format_versions is not None and directory.name not in selection.format_versions:
                continue
            extensions = selection.extensions or DOCUMENT_EXTENSIONS
            for file in directory.iterdir():
                if file.is_file() and not file.name.startswith(".") and file.suffix.removeprefix(".") in extensions:
                    yield PurePosixPath(BDEW_DIRECTORY, directory.name, file.name)
    if "bnetza" in sources and (root / BNETZA_DIRECTORY).is_dir():
        for file in (root / BNETZA_DIRECTORY).glob("[!.]*.pdf"):
            if _bnetza_file_selected(file.name, selection):
                yield PurePosixPath(BNETZA_DIRECTORY, file.name)


def synchronize(
    client: httpx.Client,
    root: Path,
    downloads: Sequence[Download],
    selection: Selection,
    *,
    concurrency: int = 6,
    prune: bool = False,
    dry_run: bool = False,
) -> Report:
    def run(download: Download) -> Report:
        try:
            return _apply(client, root, download, dry_run)
        except (httpx.HTTPError, httpx.InvalidURL, OSError) as error:
            _logger.error("Could not download %s (%s): %s", download.title, download.url, error)
            return Report(failed=[(download.title, str(error))])

    report = Report()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for partial in executor.map(run, downloads):
            report.merge(partial)

    if prune:
        # an empty listing (e.g. a hiccup of the website) must not wipe the output
        planned_sources = {download.source for download in downloads}
        for source in selection.sources - planned_sources:
            _logger.warning("Nothing selected from %s, not pruning its files", source)
        expected = {path for download in downloads for path in download.paths}
        for path in sorted(set(_managed_files(root, selection, planned_sources)) - expected):
            if not dry_run:
                (root / path).unlink()
            report.removed.append(path)
            _logger.info("Removed %s", path)
    return report
