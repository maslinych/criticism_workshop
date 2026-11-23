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
    asm = sub.add_parser("assemble", help="stage 8: build the statements table and data dictionary (no LLM requests)")
    asm.add_argument("--sample", action="store_true", help="sample mode: use corpus_sample/")
    asm.add_argument("--annotation", metavar="DIR",
                     help="read the records from this folder instead of data/annotation/<mode>/ "
                          "(e.g. an earlier pilot kept by scripts/pilot.sh)")
    asm.add_argument("--out", metavar="DIR", help="write the tables here instead of data/dataset/<mode>/")
    st = sub.add_parser("stats", help="stage 9: descriptive statistics of one or more assembled datasets")
    st.add_argument("--sample", action="store_true", help="sample mode: use data/dataset/sample/")
    st.add_argument("--datasets", nargs="+", metavar="DIR",
                    help="assembled datasets to describe; two or more are compared as repeated runs")
    st.add_argument("--labels", nargs="+", metavar="NAME", help="short names of the datasets in the report")
    st.add_argument("--name", help="report name: reports/05-statistics-<name>.md")
    sub.add_parser("models", help="list the model names the LiteLLM service offers")
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

        summary = annotate.run(cfg, "analyst" if args.stage == "analyse" else "reviewer", sample=args.sample,
                               limit=args.limit, articles=args.articles, retry_failed=args.retry_failed)
        if summary["counts"].get("stopped early"):
            raise SystemExit(1)
        return None
    elif args.stage == "models":
        from .llm import LLMClient

        for name in LLMClient.from_config(cfg).models():
            print(name)
        return None
    elif args.stage == "check":
        from . import checkreport

        return checkreport.run(cfg, args.step, sample=args.sample)
    elif args.stage == "assemble":
        from . import dataset

        dataset.run(cfg, sample=args.sample, annotation=args.annotation, out=args.out)
        return None
    elif args.stage == "stats":
        from . import stats

        stats.run(cfg, sample=args.sample, datasets=args.datasets, labels=args.labels, name=args.name)
        return None
    elif args.stage == "estimate":
        from . import estimate

        return estimate.run(cfg, sample=args.sample)
    stage.run(cfg)
