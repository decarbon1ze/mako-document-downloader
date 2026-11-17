"""command line interface: mako-document-downloader {download,list}"""

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

import httpx

from mako_document_downloader import bdew, bnetza
from mako_document_downloader.format_versions import FORMAT_VERSION_STARTS, is_valid_name
from mako_document_downloader.sync import DOCUMENT_EXTENSIONS, SOURCES, Download, Selection, plan, synchronize

DEFAULT_OUTPUT = Path("mako-documents")
_logger = logging.getLogger("mako_document_downloader")
FILE_TYPES = sorted(DOCUMENT_EXTENSIONS)


def _format_version(value: str) -> str:
    name = value.upper()
    if not is_valid_name(name):
        known = ", ".join(FORMAT_VERSION_STARTS)
        raise argparse.ArgumentTypeError(f"unknown format version {value!r} (known: {known} and later FVyy04/FVyy10)")
    return name


def _add_selection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-f",
        "--format-version",
        type=_format_version,
        action="append",
        metavar="FV",
        help="only documents of this format version, e.g. FV2604 (repeatable; default: all)",
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=FILE_TYPES,
        action="append",
        help="only bdew-mako.de files of this type (repeatable; default: all)",
    )
    parser.add_argument(
        "-s",
        "--source",
        choices=SOURCES,
        action="append",
        help="bdew: EDI@Energy documents of bdew-mako.de, bnetza: process rules of the Bundesnetzagentur "
        "(GPKE, WiM, MaBiS) (repeatable; default: both)",
    )
    parser.add_argument(
        "--bnetza-list",
        type=Path,
        metavar="FILE",
        help="JSON file with additional Bundesnetzagentur documents (same format as the bundled list; "
        "entries with the same name replace bundled ones)",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mako-document-downloader",
        description="Downloads the documents of the German energy market communication into a local folder.",
    )
    parser.add_argument("--version", action="version", version=version("mako-document-downloader"))
    parser.add_argument("-v", "--verbose", action="store_true", help="log every request")
    commands = parser.add_subparsers(dest="command", required=True)

    download = commands.add_parser("download", help="download new documents into the output folder")
    download.add_argument(
        "-o", "--output", type=Path, default=DEFAULT_OUTPUT, help=f"output folder (default: ./{DEFAULT_OUTPUT})"
    )
    _add_selection_arguments(download)
    download.add_argument("-j", "--concurrency", type=int, default=6, help="parallel downloads (default: 6)")
    download.add_argument(
        "--prune",
        action="store_true",
        help="delete files in the output folder that are no longer published (only within the selection)",
    )
    download.add_argument("--dry-run", action="store_true", help="only report what would change")
    download.add_argument(
        "--summary-file", type=Path, metavar="FILE", help="write a summary of the changes (usable as commit message)"
    )

    listing = commands.add_parser("list", help="list the available documents without downloading them")
    _add_selection_arguments(listing)
    listing.add_argument("--json", action="store_true", help="print JSON instead of a table")
    return parser


def _selection(arguments: argparse.Namespace) -> Selection:
    return Selection(
        format_versions=frozenset(arguments.format_version) if arguments.format_version else None,
        extensions=frozenset(arguments.type) if arguments.type else None,
        sources=frozenset(arguments.source or SOURCES),
    )


def _client(concurrency: int = 6) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": f"mako-document-downloader/{version('mako-document-downloader')}"},
        timeout=httpx.Timeout(60, connect=15),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=concurrency),
    )


def _plan(client: httpx.Client, selection: Selection, bnetza_list: Path | None) -> list[Download]:
    publications = bdew.fetch_publications(client) if "bdew" in selection.sources else []
    return plan(publications, bnetza.load_documents(bnetza_list), selection)


def _download(arguments: argparse.Namespace) -> int:
    selection = _selection(arguments)
    with _client(arguments.concurrency) as client:
        downloads = _plan(client, selection, arguments.bnetza_list)
        _logger.info("%i documents selected, writing to %s", len(downloads), arguments.output)
        report = synchronize(
            client,
            arguments.output,
            downloads,
            selection,
            concurrency=arguments.concurrency,
            prune=arguments.prune,
            dry_run=arguments.dry_run,
        )
    _logger.info("%s, %i unchanged, %i failed", report.headline(), report.unchanged, len(report.failed))
    if arguments.summary_file:
        arguments.summary_file.write_text(report.summary(), encoding="utf-8")
    return 1 if report.failed else 0


def _list(arguments: argparse.Namespace) -> int:
    with _client() as client:
        downloads = _plan(client, _selection(arguments), arguments.bnetza_list)
    if arguments.json:
        rows = [{"title": d.title, "url": d.url, "paths": [str(path) for path in d.paths]} for d in downloads]
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        for download in downloads:
            for path in download.paths:
                print(path)
        _logger.info("%i documents, %i files", len(downloads), sum(len(d.paths) for d in downloads))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if arguments.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if not arguments.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        return _download(arguments) if arguments.command == "download" else _list(arguments)
    except httpx.HTTPError as error:
        _logger.error("Could not read the list of documents: %s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
