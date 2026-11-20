# mako-document-downloader

A command line tool that downloads the documents of the German energy market communication (Marktkommunikation,
MaKo) into a local folder and keeps that folder up to date:

* the EDI@Energy documents of [bdew-mako.de](https://www.bdew-mako.de): AHBs, MIGs, EBDs, code lists, Allgemeine
  Festlegungen, XSDs, … (all files that are freely available, as docx, pdf, xlsx and xsd)
* process rules of the [Bundesnetzagentur](https://www.bundesnetzagentur.de): GPKE (Teil 1–4), WiM Strom (Teil 1
  and 2) and MaBiS

This repository contains only the tool, never the documents. Everyone downloads the documents from the publishers
themselves, into a folder or repository of their own, by hand or with a scheduled pipeline (see
[Keeping a repository up to date](#keeping-a-repository-up-to-date)).

This project is not affiliated with BDEW, EDI@Energy or the Bundesnetzagentur. Their terms of use apply to the
documents.

## Usage

Requires [uv](https://docs.astral.sh/uv/) (or Python ≥ 3.12 and pip).

```sh
# run without installing
uvx --from "git+https://github.com/decarbon1ze/mako-document-downloader" mako-document-downloader download --output mako-documents

# or install the command
uv tool install "git+https://github.com/decarbon1ze/mako-document-downloader"
mako-document-downloader download --output mako-documents --format-version FV2604 --format-version FV2610
```

The first run downloads everything selected; later runs only fetch what is new. `list` shows what `download` would
write without downloading anything.

| Option | Meaning |
|--------|---------|
| `-o`, `--output DIR` | output folder (default: `./mako-documents`) |
| `-f`, `--format-version FV` | only documents valid in this format version, e.g. `FV2604` (repeatable; default: all) |
| `-t`, `--type TYPE` | only bdew-mako.de files of this type: `docx`, `pdf`, `xlsx`, `xsd` (repeatable; default: all) |
| `-s`, `--source SOURCE` | `bdew` (bdew-mako.de) or `bnetza` (Bundesnetzagentur) (repeatable; default: both) |
| `--bnetza-list FILE` | additional Bundesnetzagentur documents, see [below](#bundesnetzagentur-documents) |
| `-j`, `--concurrency N` | parallel downloads (default: 6) |
| `--prune` | delete files that are no longer published (only within the selection, only document files; a source that lists nothing is left alone) |
| `--dry-run` | only report what would change |
| `--summary-file FILE` | write a summary of the changes, e.g. as commit message |
| `-v`, `--verbose` | log every request |

Exit codes: `0` success, `1` some files could not be downloaded (the others are stored), `2` the list of documents
could not be read.

Examples:

```sh
# only the Word files (the machine-readable basis for AHB/MIG tooling) of the current format versions
mako-document-downloader download -t docx -f FV2604 -f FV2610

# only the process rules of the Bundesnetzagentur
mako-document-downloader download -s bnetza

# everything available for FV2610, as JSON
mako-document-downloader list -f FV2610 --json
```

## Output

```
mako-documents/
├── edi_energy_de/
│   ├── FV2604/
│   │   ├── AHB_UTILMD_S2.1_20260302_20260326_20260302_xoxx_12345.docx
│   │   ├── EBD_4.2_20260401_20260930_20260401_ooox_12346.docx
│   │   └── codelistederkonfigurationen_1.4_20260401_99991231_20260401_ooox_12347.pdf
│   └── FV2610/
│       └── …
└── bnetza/
    ├── GPKE_Teil1_20250606_99991231.pdf
    ├── WiM_Teil1_20250606_99991231.pdf
    └── …
```

A file of bdew-mako.de is stored in the folder of every format version it is valid in. Its name is

```
<label>_<valid from>_<valid to>_<publication date>_<flags>_<file id>.<extension>
```

* `label`: `AHB_<format>_<version>` or `MIG_<format>_<version>` for the message guides (`AHB_UTILMD_S2.1`),
  `EBD_<version>` for the decision trees, otherwise the title in lower case without spaces and special characters plus
  the version (`codelistederkonfigurationen_1.4`). Titles without a version get `0.0`.
* dates as `yyyymmdd`, an open end as `99991231`; the publication date is the "Stand" of the title, or the start of
  validity if the title has none
* `flags`: four characters, `x` for yes and `o` for no: contains error corrections, extraordinary publication,
  consolidated reading version, informational reading version (the Word/Excel version next to the official PDF).
  This is the order in which kohlrahbi reads them.
* `file id`: the id on bdew-mako.de. A new upload gets a new id, so existing files never change.

This is the layout existing open source tooling for EDI@Energy documents, e.g.
[kohlrahbi](https://github.com/Hochfrequenz/kohlrahbi) and [migmose](https://github.com/Hochfrequenz/migmose),
reads: pass the output folder as their input directory.

## Keeping a repository up to date

Create a repository of your own for the documents and run the tool there, by hand

```sh
mako-document-downloader download --output mako-documents --summary-file /tmp/summary.md
git add --all mako-documents && git commit --file /tmp/summary.md
```

or with a scheduled pipeline that commits the changes:

* GitHub: [examples/github-actions.yml](examples/github-actions.yml)
* GitLab: [examples/gitlab-ci.yml](examples/gitlab-ci.yml)

Mind the size: all files of all format versions are several GB. Restrict the selection with `--format-version` and
`--type` (e.g. `-t docx` for tooling) and consider [Git LFS](https://git-lfs.com) for large repositories.

## Bundesnetzagentur documents

The Bundesnetzagentur offers no API, so the tool ships a list of its documents
([bnetza_documents.json](src/mako_document_downloader/bnetza_documents.json)). They are fetched on every run and
rewritten when the Bundesnetzagentur has replaced the file. To add documents, or to use a newer version before the
bundled list is updated, pass a file of the same format with `--bnetza-list`; an entry with the name of a bundled one
replaces it:

```json
[
  {
    "name": "WiM_Teil1",
    "title": "WiM Teil 1 – Fokus Basis Prozesse (Lesefassung)",
    "valid_from": "2025-06-06",
    "valid_to": null,
    "url": "https://www.bundesnetzagentur.de/…/BK6-24-174_WiM_Teil1_Lesefassung_korr.pdf?__blob=publicationFile"
  }
]
```

`name` is the start of the file name, `valid_from`/`valid_to` (ISO dates, `null` for open-ended) decide the format
versions the document belongs to.

## Format versions

Format versions regularly start on 1 April and 1 October. The tool knows the actual start of all format versions up
to FV2610 ([format_versions.py](src/mako_document_downloader/format_versions.py)), including moved ones such as FV2504
(06.06.2025), and assumes the regular schedule for later ones. If a future start is moved, it has to be added there.

Documents without an end of validity are filed under every format version from their start up to the newest one that
has started or for which documents have been published.

## Development

```sh
uv sync
uv run pytest
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src tests
```

The tests use a fake of bdew-mako.de and the Bundesnetzagentur and need no network.
