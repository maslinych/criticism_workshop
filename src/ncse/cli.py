"""Command line entry point: `uv run ncse <stage>`."""

import argparse

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="ncse", description="NCSE arts-criticism pipeline")
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("acquire", help="download NCSE v2.0 files and record checksums")
    args = parser.parse_args()

    cfg = load_config()
    if args.stage == "acquire":
        from . import acquire

        acquire.run(cfg)
