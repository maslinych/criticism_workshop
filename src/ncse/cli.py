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
    for name, help_text in [("analyse", "stage 4: send articles to the analyst LLM (answers checked at once)"),
                            ("review", "stage 6: send analysed articles to the reviewer LLM (answers checked at once)")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--sample", action="store_true", help="sample mode: use corpus_sample/")
        p.add_argument("--limit", type=int, help="process at most this many articles in this run")
        p.add_argument("--articles", nargs="+", metavar="ID", help="process only these articles")
        p.add_argument("--retry-failed", action="store_true",
                       help="give articles that failed earlier a new round of attempts")
    check = sub.add_parser("check", help="stages 5 and 7: re-check stored answers and write a report (no LLM requests)")
    check.add_argument("step", choices=["analyst", "reviewer"])
    check.add_argument("--sample", action="store_true", help="sample mode: use corpus_sample/")
    est = sub.add_parser("estimate", help="estimate requests and tokens before a run")
    est.add_argument("--sample", action="store_true", help="sample mode: use corpus_sample/")
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
    elif args.stage in ("analyse", "review"):
        from . import annotate

        return annotate.run(cfg, "analyst" if args.stage == "analyse" else "reviewer", sample=args.sample,
                            limit=args.limit, articles=args.articles, retry_failed=args.retry_failed)
    elif args.stage == "check":
        from . import checkreport

        return checkreport.run(cfg, args.step, sample=args.sample)
    elif args.stage == "estimate":
        from . import estimate

        return estimate.run(cfg, sample=args.sample)
    stage.run(cfg)
