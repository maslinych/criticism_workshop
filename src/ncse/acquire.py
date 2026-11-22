"""Stage 1: download the NCSE v2.0 files and record where they came from.

For every file listed in config.yaml the script
  1. skips it if it is already downloaded and its checksum is correct;
  2. otherwise downloads it (continuing a partial download if there is one);
  3. checks the md5 checksum against the value published on figshare;
  4. unpacks the zip archive into its own folder.

A manifest (data/raw/MANIFEST.json, copied to reports/acquire-manifest.json)
records the source URL, download date, size and checksums of every file.
"""

import datetime as dt
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

from .runlog import RunLog

CHUNK = 1 << 20  # read and write 1 MB at a time


def file_hashes(path: Path) -> tuple[str, str]:
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()


def download(url: str, target: Path, log: RunLog) -> None:
    """Download url to target, continuing from target.part if it exists."""
    part = target.with_name(target.name + ".part")
    done = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": "ncse-pipeline"})
    if done:
        request.add_header("Range", f"bytes={done}-")
        log.info(f"  continuing download at {done:,} bytes")
    with urllib.request.urlopen(request) as response:
        # 206 = the server agreed to send only the rest; otherwise start over.
        mode = "ab" if done and response.status == 206 else "wb"
        with open(part, mode) as out:
            shutil.copyfileobj(response, out, CHUNK)
    part.rename(target)


def unpack(archive: Path, log: RunLog) -> list[str]:
    folder = archive.with_suffix("")
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        for name in names:
            # Refuse paths that would land outside the target folder.
            dest = (folder / name).resolve()
            if not dest.is_relative_to(folder.resolve()):
                raise ValueError(f"unsafe path in {archive.name}: {name}")
        if not folder.exists():
            # Unpack into a temporary folder first, so an interrupted unpack
            # never leaves a half-filled folder that looks finished.
            tmp = folder.with_name(folder.name + ".tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            z.extractall(tmp)
            tmp.rename(folder)
            log.info(f"  unpacked {len(names)} files into {folder.name}/")
    return names


def run(cfg: dict) -> None:
    raw: Path = cfg["paths"]["raw"]
    raw.mkdir(parents=True, exist_ok=True)
    log = RunLog("acquire", cfg["paths"]["logs"])
    manifest_path = raw / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for spec in cfg["source"]["files"]:
        name, target = spec["name"], raw / spec["name"]
        log.info(f"{name}")
        try:
            if target.exists() and name in manifest and manifest[name]["md5"] == spec["md5"]:
                log.info("  already downloaded and checked, skipping")
                log.count("skipped")
            else:
                if not target.exists():
                    download(spec["url"], target, log)
                md5, sha256 = file_hashes(target)
                if md5 != spec["md5"]:
                    target.unlink()
                    raise ValueError(f"checksum mismatch (got {md5}, expected {spec['md5']}); file deleted")
                manifest[name] = {
                    "url": spec["url"],
                    "doi": cfg["source"]["doi"],
                    "figshare_version": cfg["source"]["figshare_version"],
                    "downloaded": dt.datetime.now().isoformat(timespec="seconds"),
                    "size": target.stat().st_size,
                    "md5": md5,
                    "sha256": sha256,
                }
                log.info("  downloaded, checksum OK")
                log.count("downloaded")
            manifest[name]["contents"] = unpack(target, log)
        except Exception as e:  # report, keep going with the other files
            log.info(f"  FAILED: {e}")
            log.count("failed")

    manifest_path.write_text(json.dumps(manifest, indent=2))
    reports: Path = cfg["paths"]["reports"]
    reports.mkdir(parents=True, exist_ok=True)
    shutil.copy(manifest_path, reports / "acquire-manifest.json")
    log.close()
