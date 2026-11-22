"""Package the prepared corpus for publication as a GitHub release (decisions D-008, D-019).

`uv run ncse package` writes to dist/:
  ncse-arts-corpus-v<version>.zip         the corpus: one folder holding texts/, metadata.csv,
                                          excluded_boxes.csv, BUILD.json and CORPUS_README.md
  ncse-arts-corpus-v<version>.zip.sha256  its SHA-256 checksum, in the format `sha256sum -c` reads
  CORPUS_README.md                        a copy of the description, used as the release notes

It refuses to package a corpus that was not built from committed code at the
current commit, so that the release tag always points to the code that made it.
Publishing itself (tag, push, upload) is done by hand; README.md, "Publishing
the corpus", gives the commands.
"""

import csv
import datetime as dt
import hashlib
import json
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

from .config import PROJECT_ROOT
from .prepare import EXCLUDED_COLUMNS, METADATA_COLUMNS
from .runlog import RunLog

# Fixed date and time stamped on every file in the zip, so that packaging the
# same corpus twice gives a byte-identical zip with the same checksum.
ZIP_TIME = (2000, 1, 1, 0, 0, 0)


def git_state() -> dict:
    """The current commit and whether tracked files have uncommitted changes."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


def release_names(cfg: dict) -> dict:
    r = cfg["release"]
    asset = f"ncse-arts-corpus-v{r['version']}.zip"
    return {
        "tag": f"corpus-v{r['version']}",
        "asset": asset,
        "folder": asset.removesuffix(".zip"),
        "url": f"https://github.com/{r['repository']}/releases/download/corpus-v{r['version']}/{asset}",
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_corpus(folder: Path) -> list[dict]:
    """Basic integrity checks before packaging; returns the metadata rows."""
    with open(folder / "metadata.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    files = {p.name for p in (folder / "texts").iterdir()}
    if files != {r["file_name"] for r in rows}:
        raise SystemExit(f"{folder}: text files and metadata.csv rows do not match one to one")
    if len({r["article_id"] for r in rows}) != len(rows):
        raise SystemExit(f"{folder}: article identifiers are not unique")
    if not (folder / "excluded_boxes.csv").exists():
        raise SystemExit(f"{folder}: excluded_boxes.csv is missing")
    return rows


def corpus_readme(cfg: dict, rows: list[dict], n_excluded: int, build: dict, names: dict, date: str) -> str:
    src = cfg["source"]
    by_per: dict[str, list[dict]] = {}
    for r in rows:
        by_per.setdefault(r["periodical"], []).append(r)
    counts = "\n".join(
        f"| {per} | {min(r['issue_date'] for r in rs)[:4]}–{max(r['issue_date'] for r in rs)[:4]} | {len(rs):,} "
        f"| {sum(int(r['n_words']) for r in rs):,} | {sum(r['whole_unit'] == 'yes' for r in rs):,} |"
        for per, rs in sorted(by_per.items())
    )
    meta = "\n".join(f"| `{k}` | {v} |" for k, v in METADATA_COLUMNS.items())
    excl = "\n".join(f"| `{k}` | {v} |" for k, v in EXCLUDED_COLUMNS.items())
    sel = cfg["selection"]
    return f"""# NCSE arts criticism corpus, version {cfg['release']['version']}

Articles on the arts from two nineteenth-century British periodicals, *The Monthly Repository* (1806–1837) and *The Leader* (1850–1860), rebuilt from the OCR edition NCSE v2.0. The texts are left exactly as the OCR model read them, errors included. They are prepared as the input to an annotation of evaluative statements about creators and their works.

- **Version:** {cfg['release']['version']} (release tag `{names['tag']}`), packaged {date}
- **Built by:** commit `{build['commit']}` of <https://github.com/{cfg['release']['repository']}>, on {build['built']}
- **Licence:** {src['licence']} (inherited from NCSE v2.0)

## Source and attribution

The texts come from **NCSE v2.0**: {src['author']} ({src['year']}), *{src['title']}*, University College London, <https://doi.org/{src['doi']}>, licensed under {src['licence']}. That edition is based on the **Nineteenth-Century Serials Edition (NCSE, 2008; <https://ncse.ac.uk>)**, whose page images are held at King's College London. Please credit both when you use this corpus. Accompanying paper: Bourne, *Reading the unreadable: Creating a dataset of 19th century English newspapers using image-to-text language models* (arXiv:2502.14901).

## Contents

| Periodical | Years | Articles | Words | Whole units |
|---|---|---:|---:|---:|
{counts}

- `texts/<article_id>.txt`: one article per file, rebuilt from NCSE boxes in reading order, boxes separated by a blank line. No header; text only.
- `metadata.csv`: one row per article (UTF-8, comma-separated; columns below).
- `excluded_boxes.csv`: {n_excluded:,} NCSE boxes left out because their text was invented by the OCR model, with the reason.
- `BUILD.json`: when and from which code commit the corpus was built.

## How the articles were selected and rebuilt

An NCSE entry is one box on a printed page, not an article. Each box carries a machine-assigned text type and topic labels.

1. **Issues:** regular issues only, MRP for the *Monthly Repository* and LDR (town edition) for *The Leader*.
2. **Selection:** a box is *selected* when its text type is `{sel['text_type']}` and its topics include `{sel['topic']}`.
3. **Invented text:** boxes where the OCR model reached its output limit of {cfg['invented']['token_limit']:,} tokens, or where at least {cfg['invented']['repeat_share']:.0%} of the {cfg['invented']['repeat_ngram']}-word sequences repeat, are left out and listed in `excluded_boxes.csv`. Short invented passages without loops are not detected; articles mentioning a year later than their issue are flagged in `rebuild_notes`.
4. **Rebuilding:** each issue is cut into units at headings (title boxes, and headings at the start of text boxes). A unit with a selected box is taken whole if it spans at most {cfg['rebuild']['max_pages']} pages and opens with an arts-labelled box or is mostly selected text. Otherwise only its selected boxes are taken, with gaps of up to {cfg['rebuild']['max_gap']} boxes bridged. Figure and table boxes are left out.

The full reasoning is in `docs/decisions.md` of the repository (D-002, D-010, D-011, D-013, D-015 to D-018). Known weaknesses: some articles are fragments, especially in the *Monthly Repository*. Some whole units run on into the next item where a heading was missed. Some selected texts are not criticism (for example, book lists).

## Columns of `metadata.csv`

| Column | Meaning |
|---|---|
{meta}

## Columns of `excluded_boxes.csv`

| Column | Meaning |
|---|---|
{excl}
"""


def write_zip(folder: Path, files: dict[str, bytes | Path], path: Path) -> None:
    """Write files (name inside the folder -> bytes or a file on disk) into a reproducible zip."""
    tmp = path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(f"{folder}/{name}", date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            data = files[name]
            z.writestr(info, data if isinstance(data, bytes) else data.read_bytes(), compresslevel=9)
    tmp.replace(path)


def package(cfg: dict, corpus: Path, out_dir: Path, require_clean: bool = True, date: str | None = None) -> Path:
    """Build the release zip, checksum and readme. Returns the path of the zip."""
    names = release_names(cfg)
    build_file = corpus / "BUILD.json"
    if not build_file.exists():
        raise SystemExit(f"{build_file} is missing: run `uv run ncse prepare` first")
    build = json.loads(build_file.read_text())
    if require_clean:
        now = git_state()
        if now["dirty"] or build["dirty"]:
            raise SystemExit("uncommitted changes: commit them, run `uv run ncse prepare` again, then package")
        if build["commit"] != now["commit"]:
            raise SystemExit(
                f"the corpus was built at commit {build['commit'][:10]}, but the current commit is {now['commit'][:10]}: "
                "run `uv run ncse prepare` again, then package"
            )
    rows = check_corpus(corpus)
    with open(corpus / "excluded_boxes.csv", encoding="utf-8", newline="") as f:
        n_excluded = sum(1 for _ in csv.DictReader(f))
    date = date or dt.date.today().isoformat()
    readme = corpus_readme(cfg, rows, n_excluded, build, names, date)

    files: dict[str, bytes | Path] = {f"texts/{r['file_name']}": corpus / "texts" / r["file_name"] for r in rows}
    for name in ("metadata.csv", "excluded_boxes.csv", "BUILD.json"):
        files[name] = corpus / name
    files["CORPUS_README.md"] = readme.encode("utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / names["asset"]
    write_zip(names["folder"], files, zip_path)
    (out_dir / (names["asset"] + ".sha256")).write_text(f"{sha256(zip_path)}  {names['asset']}\n")
    (out_dir / "CORPUS_README.md").write_text(readme, encoding="utf-8")
    return zip_path


def run(cfg: dict) -> None:
    log = RunLog("package", cfg["paths"]["logs"])
    names = release_names(cfg)
    zip_path = package(cfg, cfg["paths"]["corpus"], cfg["paths"]["dist"])
    build = json.loads((cfg["paths"]["corpus"] / "BUILD.json").read_text())
    digest = sha256(zip_path)
    log.count("articles packaged", len(check_corpus(cfg["paths"]["corpus"])))
    log.info(f"written {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")
    log.info(f"sha256 {digest}")
    log.info(f"release tag {names['tag']} must point to commit {build['commit']}")
    log.info(f"download address after publishing: {names['url']}")
    log.info("publish with the commands in README.md, 'Publishing the corpus'")
    log.close()
