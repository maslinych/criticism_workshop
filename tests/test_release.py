"""Package the sample corpus and fetch it back (src/ncse/release.py, src/ncse/fetch.py), without network."""

import json
import shutil
import zipfile

import pytest

from ncse.config import load_config
from ncse.fetch import fetch, unpack
from ncse.release import package, release_names, sha256
from ncse.runlog import RunLog

CFG = load_config()
NAMES = release_names(CFG)


@pytest.fixture
def built(tmp_path):
    """A copy of the sample corpus with a BUILD.json, as `ncse prepare` writes it."""
    corpus = tmp_path / "built"
    shutil.copytree(CFG["paths"]["corpus_sample"], corpus)
    (corpus / "README.md").unlink()
    (corpus / "BUILD.json").write_text(json.dumps({"commit": "0" * 40, "dirty": False, "built": "2026-11-22T00:00:00"}))
    return corpus


def make_package(built, out):
    return package(CFG, built, out, require_clean=False, date="2026-11-22")


def test_package_contents_and_checksum(built, tmp_path):
    zip_path = make_package(built, tmp_path / "dist")
    assert zip_path.name == NAMES["asset"]
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
    folder = NAMES["folder"]
    assert {f"{folder}/metadata.csv", f"{folder}/excluded_boxes.csv", f"{folder}/BUILD.json", f"{folder}/CORPUS_README.md"} <= names
    assert sum(n.startswith(f"{folder}/texts/") for n in names) == len(list((built / "texts").iterdir()))
    line = (tmp_path / "dist" / (NAMES["asset"] + ".sha256")).read_text()
    assert line == f"{sha256(zip_path)}  {NAMES['asset']}\n"
    readme = (tmp_path / "dist" / "CORPUS_README.md").read_text()
    assert "10.5522/04/28381610" in readme and "CC BY 4.0" in readme and "ncse.ac.uk" in readme


def test_package_is_reproducible(built, tmp_path):
    a = sha256(make_package(built, tmp_path / "a"))
    b = sha256(make_package(built, tmp_path / "b"))
    assert a == b


def test_fetch_gives_back_the_same_files(built, tmp_path):
    zip_path = make_package(built, tmp_path / "dist")
    target = tmp_path / "corpus"
    log = RunLog("test-fetch", tmp_path / "logs")
    release = {"sha256": sha256(zip_path)}
    fetch(release, NAMES, zip_path.as_uri(), target, tmp_path / "downloads", False, log)
    for path in built.rglob("*"):
        if path.is_file():
            assert (target / path.relative_to(built)).read_bytes() == path.read_bytes(), path.name
    assert json.loads((target / "FETCHED.json").read_text())["tag"] == NAMES["tag"]
    # Running again does nothing.
    fetch(release, NAMES, "file:///does/not/exist", target, tmp_path / "downloads", False, log)
    log.close()


def test_fetch_rejects_wrong_checksum(built, tmp_path):
    zip_path = make_package(built, tmp_path / "dist")
    log = RunLog("test-fetch", tmp_path / "logs")
    with pytest.raises(SystemExit, match="checksum mismatch"):
        fetch({"sha256": "0" * 64}, NAMES, zip_path.as_uri(), tmp_path / "corpus", tmp_path / "downloads", False, log)
    assert not (tmp_path / "corpus").exists()
    log.close()


def test_fetch_does_not_overwrite_a_built_corpus(built, tmp_path):
    zip_path = make_package(built, tmp_path / "dist")
    log = RunLog("test-fetch", tmp_path / "logs")
    with pytest.raises(SystemExit, match="already holds a corpus"):
        fetch({"sha256": sha256(zip_path)}, NAMES, zip_path.as_uri(), built, tmp_path / "downloads", False, log)
    log.close()


def test_unpack_rejects_paths_outside_the_folder(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.txt", "x")
    with pytest.raises(SystemExit, match="unexpected path"):
        unpack(bad, NAMES["folder"], tmp_path / "corpus")
