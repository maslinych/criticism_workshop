"""Command line entry point: `uv run ncse <stage>`."""

import argparse

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="ncse", description="NCSE arts-criticism pipeline")
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("acquire", help="stage 1: download NCSE v2.0 files and record checksums")
    sub.add_parser("inspect", help="stage 2: describe the data and test the selection rule")
    sub.add_parser("prepare", help="stage 3: rebuild articles and write the prepared corpus")
    sub.add_parser("sample-raw", help="copy original NCSE rows for a dozen articles into raw_sample/ (test data)")
    sub.add_parser("package", help="package the prepared corpus for publication as a GitHub release")
    fetch = sub.add_parser("fetch", help="download the published corpus instead of building it")
    fetch.add_argument("--force", action="store_true", help="replace a corpus already in place")
    args = parser.parse_args()

    cfg = load_config()
    if args.stage == "acquire":
        from . import acquire as stage
    elif args.stage == "inspect":
        from . import inspection as stage
    elif args.stage == "prepare":
        from . import prepare as stage
    elif args.stage == "sample-raw":
        from . import rawsample as stage
    elif args.stage == "package":
        from . import release as stage
    elif args.stage == "fetch":
        from . import fetch

        return fetch.run(cfg, force=args.force)
    stage.run(cfg)
