"""Fetch the published corpus instead of building it (decisions D-008, D-019).

`uv run ncse fetch`:
1. downloads the release zip named in config.yaml (`release`) and its checksum file;
2. checks the zip's SHA-256 checksum against `release.sha256` in config.yaml, or,
   if that is not filled in yet, against the published checksum file;
3. unpacks it into the corpus folder (`paths.corpus`, data/corpus/full/), where
   the annotation stages expect it, and records what was fetched in FETCHED.json.

Running it again does nothing if that version is already in place. It will not
overwrite a corpus built locally or a different version unless asked to with
`--force`.
"""

import datetime as dt
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

from .release import check_corpus, release_names, sha256
from .runlog import RunLog


def download(url: str, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url) as response, open(tmp, "wb") as f:
        shutil.copyfileobj(response, f)
    tmp.replace(path)


def unpack(zip_path: Path, folder_name: str, target: Path) -> None:
    """Unpack the zip's single top folder into target, checking every path first."""
    tmp = target.with_name(target.name + ".fetch-tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = Path(name).parts
            if Path(name).is_absolute() or ".." in parts or not parts or parts[0] != folder_name:
                raise SystemExit(f"unexpected path in zip: {name}")
        z.extractall(tmp)
    check_corpus(tmp / folder_name)
    shutil.rmtree(target, ignore_errors=True)
    (tmp / folder_name).rename(target)
    tmp.rmdir()


def fetch(release: dict, names: dict, url: str, target: Path, downloads: Path, force: bool, log: RunLog) -> None:
    record = target / "FETCHED.json"
    if record.exists() and json.loads(record.read_text())["tag"] == names["tag"] and not force:
        log.info(f"{names['tag']} is already in {target}; nothing to do")
        log.count("skipped (already fetched)")
        return
    if (target / "metadata.csv").exists() and not force:
        raise SystemExit(
            f"{target} already holds a corpus (built locally or another version). "
            "Remove it, or run `uv run ncse fetch --force` to replace it."
        )
    downloads.mkdir(parents=True, exist_ok=True)
    zip_path = downloads / names["asset"]
    log.info(f"downloading {url}")
    download(url, zip_path)
    expected = release.get("sha256")
    if expected:
        source = "config.yaml"
    else:
        download(url + ".sha256", downloads / (names["asset"] + ".sha256"))
        expected = (downloads / (names["asset"] + ".sha256")).read_text().split()[0]
        source = "the published checksum file (release.sha256 in config.yaml is not filled in)"
    actual = sha256(zip_path)
    if actual != expected:
        log.count("failed (checksum)")
        raise SystemExit(f"checksum mismatch: expected {expected} from {source}, got {actual}")
    log.info(f"checksum OK ({source})")
    unpack(zip_path, names["folder"], target)
    record.write_text(json.dumps({"tag": names["tag"], "url": url, "sha256": actual,
                                  "fetched": dt.datetime.now().isoformat(timespec="seconds")}, indent=2) + "\n")
    n = len(check_corpus(target))
    log.info(f"{n:,} articles unpacked into {target}")
    log.count("articles fetched", n)


def run(cfg: dict, force: bool = False) -> None:
    log = RunLog("fetch", cfg["paths"]["logs"])
    names = release_names(cfg)
    fetch(cfg["release"], names, names["url"], cfg["paths"]["corpus"], cfg["paths"]["downloads"], force, log)
    log.close()
