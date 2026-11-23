"""Stage 9: descriptive statistics, and how stable they are between runs.

`uv run ncse stats` (add `--sample` for sample mode) describes one assembled
dataset (stage 8) and writes reports/05-statistics[-sample].md.

`uv run ncse stats --datasets DIR DIR ... --name NAME` describes several
datasets made from the same articles: repeated runs of the annotation, for
example two pilots, or runs with other prompts or models. Every number is then
given for each run, together with the gap between runs, so that a reader can
see which results are stable and which depend on the run (D-036). Only articles present in every dataset are compared.

Two kinds of uncertainty are reported side by side:

- **between runs**: the same articles annotated again give different numbers,
  because the model's answers vary (the service does not repeat answers at
  temperature 0) and, here, because prompts differ;
- **between samples of articles**: the articles are themselves a sample. The
  "sampling ±" column says how far a share would move, in 95 of 100 cases, if
  another sample of the same number of articles had been drawn. It is computed
  with the usual formula for a share counted over groups (here: articles),
  which allows for the statements of one article being alike. As a check, the
  same interval is also found by resampling ("bootstrap ±"): the articles are
  drawn again at random, with replacement, a few thousand times, and the share
  is recomputed each time; the middle 95% of these shares gives the interval.
  When the two agree, the formula can be trusted at this sample size.

Statements of different runs are also matched one to one, by where their
evaluative expressions sit in the article: two statements of the same article
whose expressions overlap are taken to be the same judgement found twice. This
shows how many judgements each run finds that the other misses, and how often
the runs agree on art, polarity, criterion and the rest.

Everything here is counting and arithmetic done by code; no LLM is used.
"""

import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

from . import figures
from .config import PROJECT_ROOT
from .dataset import CONTROLLED, LEVEL_VALUES, default_folders, read_csv
from .runlog import RunLog

Z95 = 1.96
# A share resting on fewer statements than this in every run is not judged
# stable or unstable: the sampling formula is unreliable for so few.
MIN_FOR_VERDICT = 10


# ---------------------------------------------------------------- loading


def load_dataset(folder: Path) -> dict:
    folder = Path(folder)
    if not (folder / "statements.csv").exists():
        raise SystemExit(f"no assembled dataset in {folder}: run `uv run ncse assemble` first")
    return {"folder": folder, "statements": read_csv(folder / "statements.csv"),
            "articles": read_csv(folder / "articles.csv"), "failed": read_csv(folder / "failed_items.csv"),
            "runs": read_csv(folder / "runs.csv")}


def restrict(ds: dict, ids: set[str]) -> dict:
    """The dataset limited to the given articles."""
    return {**ds, "statements": [s for s in ds["statements"] if s["article_id"] in ids],
            "articles": [a for a in ds["articles"] if a["article_id"] in ids],
            "failed": [f for f in ds["failed"] if f["article_id"] in ids]}


def kept(ds: dict) -> list[dict]:
    return [s for s in ds["statements"] if s["deleted"] == "no"]


def decade(row: dict) -> str:
    return f"{row['year'][:3]}0s"


def filled(s: dict, name: str) -> bool:
    """The field has a value that the reviewer did not delete."""
    return bool(s[name]) and s[f"{name}_review"] != "deleted"


# ---------------------------------------------------------------- arithmetic


def share_halfwidth(per_article: list[tuple[float, float]]) -> float | None:
    """95% sampling half-width of the share Σy/Σx, where each article gives
    (y, x): y statements of one kind among x statements (or x words).

    Ratio estimator for a sample of clusters: var = n/(n-1) · Σ(y - R·x)² / (Σx)²."""
    n = len(per_article)
    total_x = sum(x for _, x in per_article)
    if n < 2 or total_x == 0:
        return None
    r = sum(y for y, _ in per_article) / total_x
    var = n / (n - 1) * sum((y - r * x) ** 2 for y, x in per_article) / total_x ** 2
    return Z95 * math.sqrt(var)


def bootstrap_halfwidth(per_article: list[tuple[float, float]], idx: np.ndarray) -> float | None:
    """95% half-width of the share Σy/Σx found by resampling articles.

    idx holds one row of article positions per resample (drawn with
    replacement); the share is recomputed for each row, and the interval is
    the middle 95% of the results."""
    if len(per_article) < 2 or not sum(x for _, x in per_article):
        return None
    y = np.array([p[0] for p in per_article], dtype=float)
    x = np.array([p[1] for p in per_article], dtype=float)
    ys, xs = y[idx].sum(axis=1), x[idx].sum(axis=1)
    shares = ys[xs > 0] / xs[xs > 0]
    lo, hi = np.percentile(shares, [2.5, 97.5])
    return float(hi - lo) / 2


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa: agreement between two runs beyond what chance would give
    (1 = always the same, 0 = no better than chance)."""
    n = len(pairs)
    if not n:
        return None
    observed = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(ca[k] * cb[k] for k in ca) / n ** 2
    return None if expected == 1 else (observed - expected) / (1 - expected)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx, sy = math.sqrt(sum((x - mx) ** 2 for x in xs)), math.sqrt(sum((y - my) ** 2 for y in ys))
    return None if sx == 0 or sy == 0 else sxy / (sx * sy)


# ---------------------------------------------------------------- matching across runs


def _norm(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def same_target(a: dict, b: dict) -> bool:
    """Both statements name the same creator or the same work, written alike
    (letters and digits compared, capitals ignored)."""
    for name in ("creator", "work_title"):
        if a[name] and b[name] and _norm(a[name]) == _norm(b[name]):
            return True
    return False


def match_statements(run_a: list[dict], run_b: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Pair the statements of two runs one to one.

    Two statements of the same article can be paired when their evaluative
    expressions overlap in the text. Among candidates, pairs whose expressions
    overlap most (as a share of the two together) are taken first; a pair that
    also names the same target, polarity or criterion is preferred, so that two
    statements on one phrase about two different books are paired correctly.
    Returns the pairs, and the statements of each run left without a partner."""
    by_article: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for s in run_a:
        by_article[s["article_id"]][0].append(s)
    for s in run_b:
        by_article[s["article_id"]][1].append(s)
    pairs, only_a, only_b = [], [], []
    for aid in sorted(by_article):
        xs, ys = by_article[aid]
        candidates = []
        for i, a in enumerate(xs):
            a0, a1 = int(a["expression_start"]), int(a["expression_end"])
            for j, b in enumerate(ys):
                b0, b1 = int(b["expression_start"]), int(b["expression_end"])
                overlap = min(a1, b1) - max(a0, b0)
                if overlap <= 0:
                    continue
                score = (overlap / (max(a1, b1) - min(a0, b0)) + 0.5 * same_target(a, b)
                         + 0.25 * (a["polarity"] == b["polarity"]) + 0.25 * (a["criterion"] == b["criterion"]))
                candidates.append((-score, i, j))
        used_a, used_b = set(), set()
        for _, i, j in sorted(candidates):
            if i in used_a or j in used_b:
                continue
            used_a.add(i)
            used_b.add(j)
            pairs.append((xs[i], ys[j]))
        only_a += [s for i, s in enumerate(xs) if i not in used_a]
        only_b += [s for j, s in enumerate(ys) if j not in used_b]
    return pairs, only_a, only_b


# ---------------------------------------------------------------- report helpers


def pct(n: int, total: int) -> str:
    return f"{n} ({100 * n / total:.0f}%)" if total else str(n)


def fmt(x: float | None, digits: int = 2) -> str:
    return "–" if x is None else f"{x:.{digits}f}"


def table(head: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out


class Report:
    def __init__(self, runs: list[dict], labels: list[str], bootstrap: int = 2000, seed: int = 1850):
        self.runs, self.labels = runs, labels
        self.multi = len(runs) > 1
        self.gaps: list[tuple[float, float | None, str]] = []  # (gap in points, sampling ±, what)
        self.intervals: list[tuple[str, str, int, float, float]] = []  # (share, run, n, formula ±, bootstrap ±)
        self.panels: list[dict] = []  # data for the chart of shares
        # One fixed set of resamples per run, so that the report is the same every time.
        self.idx = [np.random.default_rng(seed).integers(0, len(ds["articles"]), (bootstrap, len(ds["articles"])))
                    if ds["articles"] else None for ds in runs]

    # A distribution: for each value, the share of kept statements in each run.
    def distribution(self, title: str, key, values: list[str] | None = None) -> list[str]:
        per_run = []
        for ds in self.runs:
            ks = kept(ds)
            by_article = defaultdict(Counter)
            for s in ks:
                by_article[s["article_id"]][key(s)] += 1
            per_run.append((ks, by_article))
        seen = sorted({key(s) for ks, _ in per_run for s in ks}, key=str)
        values = [v for v in (values or []) if v in seen] + [v for v in seen if v not in (values or [])]
        head = ["value", *self.labels]
        head += ["runs differ by", "sampling ±", "bootstrap ±", "gap vs sampling"] if self.multi \
            else ["sampling ±", "bootstrap ±"]
        rows = []
        panel = {"title": title, "values": [v or "(empty)" for v in values],
                 "shares": [[] for _ in self.runs], "hw": [[] for _ in self.runs]}
        for v in values:
            row, shares, widths, boots, ns = [v or "(empty)"], [], [], [], []
            for r, (ds, (ks, by_article)) in enumerate(zip(self.runs, per_run)):
                n = sum(1 for s in ks if key(s) == v)
                row.append(pct(n, len(ks)))
                ns.append(n)
                shares.append(100 * n / len(ks) if ks else 0)
                per_article = [(by_article[a["article_id"]][v], sum(by_article[a["article_id"]].values()))
                               for a in ds["articles"]]
                hw = share_halfwidth(per_article)
                boot = bootstrap_halfwidth(per_article, self.idx[r]) if self.idx[r] is not None else None
                panel["shares"][r].append(shares[-1])
                panel["hw"][r].append(100 * hw if hw is not None else 0)
                if hw is not None:
                    widths.append(100 * hw)
                if boot is not None:
                    boots.append(100 * boot)
                if hw is not None and boot is not None and n >= MIN_FOR_VERDICT:
                    self.intervals.append((f"{title}: {v or '(empty)'}", self.labels[r], n, 100 * hw, 100 * boot))
            enough = max(ns) >= MIN_FOR_VERDICT
            sampling = sum(widths) / len(widths) if widths and enough else None
            boot = sum(boots) / len(boots) if boots and enough else None
            if self.multi:
                gap = max(shares) - min(shares)
                row += [f"{gap:.0f} points", f"±{sampling:.0f}" if sampling is not None else "–",
                        f"±{boot:.0f}" if boot is not None else "–",
                        "too few to say" if sampling is None else "larger" if gap > sampling else "smaller"]
                self.gaps.append((gap, sampling, f"{title}: {v or '(empty)'}"))
            else:
                row += [f"±{sampling:.0f}" if sampling is not None else "–", f"±{boot:.0f}" if boot is not None else "–"]
            rows.append(row)
        self.panels.append(panel)
        return [f"### {title}", "", *table(head, rows), ""]

    def counts(self, rows: list[tuple[str, callable]]) -> list[str]:
        head = ["", *self.labels] + (["runs differ by"] if self.multi else [])
        out = []
        for name, f in rows:
            vals = [f(ds) for ds in self.runs]
            row = [name, *[fmt(v, 1) if isinstance(v, float) else v for v in vals]]
            if self.multi:
                nums = [v for v in vals if isinstance(v, (int, float))]
                if len(nums) == len(vals) and max(nums) > 0:
                    gap = max(nums) - min(nums)
                    row.append(f"{gap:.1f}" if isinstance(gap, float) else gap)
                    row[-1] = f"{row[-1]} ({100 * gap / max(nums):.0f}%)"
                else:
                    row.append("–")
            out.append(row)
        return table(head, out)


def per_thousand(n: int, words: int) -> float:
    return 1000 * n / words if words else 0.0


def words(ds: dict) -> int:
    return sum(int(a["n_words"]) for a in ds["articles"])


# ---------------------------------------------------------------- the report


def build_report(runs: list[dict], labels: list[str], excluded: dict[str, list[str]], command: str,
                 fig=None, bootstrap: int = 2000, seed: int = 1850) -> str:
    """The report as Markdown. `fig` (a figures.Figures) draws the charts; without it there are none."""
    rep = Report(runs, labels, bootstrap, seed)
    show = (lambda line: [line, ""]) if fig else (lambda line: [])
    multi = rep.multi
    L = ["# Descriptive statistics" + (" — comparison of runs" if multi else ""), "",
         f"Generated by `{command}` (`src/ncse/stats.py`) from the assembled tables (stage 8). "
         "No LLM requests were made. *Kept* statements are those the reviewer did not delete; unless said "
         "otherwise, shares are shares of kept statements.", ""]

    # 1. what is described
    L += ["## 1. What is described", ""]
    rows = []
    for ds, label in zip(runs, labels):
        st = ds["statements"]
        prov = lambda col: ", ".join(sorted({s[col] for s in st if s[col]})) or "–"  # noqa: E731
        try:
            where = ds["folder"].resolve().relative_to(PROJECT_ROOT)
        except ValueError:
            where = ds["folder"]
        rows.append([label, f"`{where}`", prov("analyst_model"),
                     f"{prov('analyst_prompt_version')} ({prov('analyst_prompt_sha256')})",
                     f"{prov('reviewer_prompt_version')} ({prov('reviewer_prompt_sha256')})",
                     ", ".join(sorted({s["analyst_answered_at"][:10] for s in st if s["analyst_answered_at"]}))])
    L += table(["run", "dataset", "model", "analyst prompt", "reviewer prompt", "analysed on"], rows) + [""]
    if multi:
        L += [f"Only the {len(runs[0]['articles'])} articles present in every run are compared."]
        for label, ids in excluded.items():
            if ids:
                L.append(f"Left out of {label}: {', '.join(f'`{i}`' for i in ids)} (not in every run).")
        L += ["", "**How to read the comparison columns.** *Runs differ by* is the gap between the highest "
              "and the lowest run. *Sampling ±* is the uncertainty that comes from having only these articles: "
              "another sample of the same size would give a share within about this many percentage points "
              "of the one found, 95 times in 100 (averaged over the runs). *Gap vs sampling* says whether the "
              f"runs differ by more than that; for a value with fewer than {MIN_FOR_VERDICT} statements in "
              "every run it says *too few to say*. A gap smaller than the sampling uncertainty means that, at this "
              "sample size, the choice of articles matters more than the run; a larger gap means that the "
              "result depends on the run itself.", ""]

    glance_at = len(L)

    # 2. overview
    L += ["## 2. Overview", ""]
    L += rep.counts([
        ("articles", lambda d: len(d["articles"])),
        ("words", lambda d: words(d)),
        ("articles with at least one kept statement", lambda d: len({s["article_id"] for s in kept(d)})),
        ("passages (quotations)", lambda d: len({s["passage_id"] for s in d["statements"]})),
        ("statements proposed by the analyst", lambda d: len(d["statements"])),
        ("statements deleted by the reviewer", lambda d: len(d["statements"]) - len(kept(d))),
        ("statements kept", lambda d: len(kept(d))),
        ("kept statements per 1,000 words", lambda d: per_thousand(len(kept(d)), words(d))),
        ("items set aside by the checks (failed_items.csv)", lambda d: len(d["failed"])),
    ]) + [""]

    # 3. periodical and decade
    L += ["## 3. Statements by periodical and decade", "",
          "Kept statements, and kept statements per 1,000 words of the articles in that group.", ""]
    for title, key in (("Periodical", lambda r: r["periodical"]), ("Decade", decade)):
        groups = sorted({key(a) for ds in runs for a in ds["articles"]})
        rows = []
        for g in groups:
            row = [g]
            for ds in runs:
                n = sum(1 for s in kept(ds) if key(s) == g)
                w = sum(int(a["n_words"]) for a in ds["articles"] if key(a) == g)
                arts = sum(1 for a in ds["articles"] if key(a) == g)
                row.append(f"{n} in {arts} art. · {per_thousand(n, w):.1f}")
            rows.append(row)
        L += [f"### {title}", "", *table([title.lower(), *labels], rows), ""]
    if fig:
        groups, rates, hws, breaks = [], [[] for _ in runs], [[] for _ in runs], []
        for key in (lambda r: r["periodical"], decade):
            if groups:
                breaks.append(len(groups) - 1)
            for g in sorted({key(a) for ds in runs for a in ds["articles"]}):
                groups.append(f"{g} ({sum(1 for a in runs[0]['articles'] if key(a) == g)} art.)")
                for r, ds in enumerate(runs):
                    counts = Counter(s["article_id"] for s in kept(ds))
                    arts = [a for a in ds["articles"] if key(a) == g]
                    w = sum(int(a["n_words"]) for a in arts)
                    rates[r].append(per_thousand(sum(counts[a["article_id"]] for a in arts), w))
                    hw = share_halfwidth([(counts[a["article_id"]], int(a["n_words"])) for a in arts])
                    hws[r].append(1000 * hw if hw is not None else None)
        L += show(fig.rates(groups, rates, hws, labels, breaks=breaks))
    if multi:
        rows = []
        for ds, label in zip(runs, labels):
            counts = Counter(s["article_id"] for s in kept(ds))
            hw = share_halfwidth([(counts[a["article_id"]], int(a["n_words"])) for a in ds["articles"]])
            rows.append([label, f"{per_thousand(len(kept(ds)), words(ds)):.1f}",
                         f"±{1000 * hw:.1f}" if hw is not None else "–"])
        L += ["Rate of kept statements per 1,000 words with its sampling uncertainty:", "",
              *table(["run", "per 1,000 words", "sampling ±"], rows), ""]

    # 4. distributions
    L += ["## 4. What the kept statements say", ""]
    blocks = []
    blocks += rep.distribution("Art", lambda s: s["art"], CONTROLLED["art"])
    blocks += rep.distribution("Polarity", lambda s: s["polarity"], CONTROLLED["polarity"])
    blocks += rep.distribution("Criterion", lambda s: s["criterion"], CONTROLLED["criterion"])
    blocks += rep.distribution("Sarcastic", lambda s: s["sarcastic"], CONTROLLED["sarcastic"])
    blocks += rep.distribution("Quoted (someone else's opinion reported)",
                               lambda s: "yes" if filled(s, "quoted_source") else "no", ["yes", "no"])
    blocks += rep.distribution("Target named",
                          lambda s: ("creator and title" if filled(s, "creator") and filled(s, "work_title")
                                     else "creator only" if filled(s, "creator")
                                     else "title only" if filled(s, "work_title") else "genre only"),
                          ["creator and title", "creator only", "title only", "genre only"])
    blocks += rep.distribution("Evidence level (after review)", lambda s: s["evidence"], LEVEL_VALUES)
    blocks += rep.distribution("Periodical", lambda s: s["periodical"])
    if fig:
        L += show(fig.shares([p for p in rep.panels if p["title"] in
                              ("Art", "Polarity", "Criterion", "Target named", "Evidence level (after review)")],
                             labels))
    L += blocks

    # 5. cross-tabulations
    L += ["## 5. Combinations", "", "### Share of positive judgements, by criterion and by art", "",
          "Kept statements; *n* is the number of statements in the row.", ""]
    if fig:
        panels = []
        for title, key, values in (("Art", lambda s: s["art"], CONTROLLED["art"]),
                                   ("Criterion", lambda s: s["criterion"], CONTROLLED["criterion"])):
            vals = [v for v in values if any(key(s) == v for ds in runs for s in kept(ds))]
            panels.append({"title": title, "values": vals,
                           "pos": [[sum(1 for s in kept(ds) if key(s) == v and s["polarity"] == "positive")
                                    for v in vals] for ds in runs],
                           "neg": [[sum(1 for s in kept(ds) if key(s) == v and s["polarity"] == "negative")
                                    for v in vals] for ds in runs]})
        L += show(fig.polarity(panels, labels))
    for title, key, values in (("criterion", lambda s: s["criterion"], CONTROLLED["criterion"]),
                               ("art", lambda s: s["art"], CONTROLLED["art"]),
                               ("periodical", lambda s: s["periodical"], None)):
        vals = values or sorted({key(s) for ds in runs for s in kept(ds)})
        rows = []
        for v in vals:
            row = [v]
            for ds in runs:
                group = [s for s in kept(ds) if key(s) == v]
                pos = sum(s["polarity"] == "positive" for s in group)
                row.append(f"{100 * pos / len(group):.0f}% of {len(group)}" if group else "–")
            rows.append(row)
        L += table([title, *labels], rows) + [""]
    L += ["### Criterion by art (kept statements)", ""]
    for ds, label in zip(runs, labels):
        c = Counter((s["art"], s["criterion"]) for s in kept(ds))
        arts = [a for a in CONTROLLED["art"] if any(k[0] == a for k in c)]
        rows = [[a, *[c[(a, k)] or "" for k in CONTROLLED["criterion"]], sum(c[(a, k)] for k in
                                                                              CONTROLLED["criterion"])]
                for a in arts]
        L += [f"{label}:", "", *table(["art", *CONTROLLED["criterion"], "total"], rows), ""]

    # 6. reviewer
    L += ["## 6. The reviewer", "",
          "What the reviewer did with the analyst's statements: deleted whole statements, deleted single "
          "fields (creator, work title, genre), or lowered evidence levels (D-005).", ""]
    from .dataset import FIELDS
    rv = [("statements deleted", lambda d: len(d["statements"]) - len(kept(d))),
          ("share of statements deleted (%)",
           lambda d: 100 * (len(d["statements"]) - len(kept(d))) / len(d["statements"]) if d["statements"] else 0.0)]
    for name in FIELDS:
        for action in ("deleted", "downgraded"):
            if any(s[f"{name}_review"] == action for ds in runs for s in ds["statements"]):
                rv.append((f"{name}: {action}",
                           lambda d, n=name, a=action: sum(s[f"{n}_review"] == a for s in d["statements"])))
    L += rep.counts(rv) + [""]
    L += ["Evidence level of all statements, as the analyst gave it and after review:", ""]
    rows = []
    for lvl in LEVEL_VALUES:
        row = [lvl]
        for ds in runs:
            st = ds["statements"]
            row.append(f"{pct(sum(s['evidence_analyst'] == lvl for s in st), len(st))} → "
                       f"{pct(sum(s['evidence'] == lvl for s in st), len(st))}")
        rows.append(row)
    L += table(["level", *labels], rows) + [""]
    if multi:
        hws = []
        for ds in runs:
            per = Counter(s["article_id"] for s in ds["statements"])
            dele = Counter(s["article_id"] for s in ds["statements"] if s["deleted"] == "yes")
            hw = share_halfwidth([(dele[a["article_id"]], per[a["article_id"]]) for a in ds["articles"]])
            if hw is not None:
                hws.append(100 * hw)
        shares = [100 * (len(d["statements"]) - len(kept(d))) / len(d["statements"]) for d in runs
                  if d["statements"]]
        if shares and hws:
            rep.gaps.append((max(shares) - min(shares), sum(hws) / len(hws), "reviewer: share of statements deleted"))
            L += [f"Share deleted: runs differ by {max(shares) - min(shares):.0f} points; "
                  f"sampling ±{sum(hws) / len(hws):.0f}.", ""]

    # 7. per article
    if multi:
        L += ["## 7. The same articles in different runs", "",
              "Kept statements per article in each run (deleted ones in brackets). Articles sent in parts are "
              "marked with the number of parts in each run.", ""]
        by_run = [(Counter(s["article_id"] for s in kept(ds)),
                   Counter(s["article_id"] for s in ds["statements"] if s["deleted"] == "yes"),
                   {a["article_id"]: a for a in ds["articles"]}) for ds in runs]
        ids = [a["article_id"] for a in runs[0]["articles"]]
        if len(ids) <= 60:
            rows = []
            for aid in ids:
                art = by_run[0][2][aid]
                row = [f"`{aid}`", art["n_words"]]
                for k, d, arts in by_run:
                    parts = int(arts[aid]["n_parts"])
                    row.append(f"{k[aid]} ({d[aid]})" + (f" · {parts} parts" if parts > 1 else ""))
                rows.append(row)
            L += table(["article", "words", *labels], rows) + [""]
        for (i, a), (j, b) in combinations(enumerate(labels), 2):
            xs = [by_run[i][0][aid] for aid in ids]
            ys = [by_run[j][0][aid] for aid in ids]
            mad = sum(abs(x - y) for x, y in zip(xs, ys)) / len(ids) if ids else 0
            L += [f"{a} vs {b}: correlation of kept statements per article {fmt(pearson(xs, ys))}; "
                  f"on average an article's count differs by {mad:.1f} statements.", ""]
            if fig:
                split = [int(by_run[i][2][aid]["n_parts"]) > 1 or int(by_run[j][2][aid]["n_parts"]) > 1
                         for aid in ids]
                suffix = "" if len(labels) == 2 else f"-{a}-{b}"
                L += show(fig.per_article(list(zip(ids, xs, ys, split)), a, b, name="per-article" + suffix))

        # 8. matching
        L += ["## 8. Do the runs find the same judgements?", "",
              "Statements of two runs are paired when their evaluative expressions overlap in the same "
              "article (see `src/ncse/stats.py`, `match_statements`). A statement without a partner is a "
              "judgement that only one run found, or one that the two runs cut differently. All statements "
              "are paired, deleted ones included; the reviewer's decisions are compared afterwards.", ""]
        for (i, a), (j, b) in combinations(enumerate(labels), 2):
            pairs, only_a, only_b = match_statements(runs[i]["statements"], runs[j]["statements"])
            split = {x["article_id"] for ds in (runs[i], runs[j]) for x in ds["articles"] if int(x["n_parts"]) > 1}
            L += pair_section(a, b, pairs, only_a, only_b, split, fig=fig,
                              suffix="" if len(labels) == 2 else f"-{a}-{b}")

    # 9. stability summary
    if multi and rep.gaps:
        judged = [g for g in rep.gaps if g[1] is not None]
        larger = sorted([g for g in judged if g[0] > g[1]], key=lambda g: -g[0])
        L += ["## 9. Summary: what is stable and what varies between runs", "",
              f"Of {len(rep.gaps)} shares compared in sections 4 and 6, {len(rep.gaps) - len(judged)} rest on "
              f"too few statements to judge. Of the other {len(judged)}, {len(judged) - len(larger)} differ "
              f"between runs by less than their sampling uncertainty, and {len(larger)} by more.", ""]
        if larger:
            L += ["Shares whose run-to-run gap exceeds the sampling uncertainty:", "",
                  *table(["share", "runs differ by", "sampling ±"],
                         [[w, f"{g:.0f} points", f"±{s:.0f}"] for g, s, w in larger]), ""]
        big = sorted(rep.gaps, key=lambda g: -g[0])[:8]
        L += ["The largest gaps between runs, whatever their sampling uncertainty:", "",
              *table(["share", "runs differ by", "sampling ±"],
                     [[w, f"{g:.0f} points", f"±{s:.0f}" if s is not None else "–"] for g, s, w in big]), ""]

    # 10. formula against resampling
    if rep.intervals:
        ratios = [b / f for _, _, _, f, b in rep.intervals if f > 0]
        n_boot = len(rep.idx[0]) if rep.idx and rep.idx[0] is not None else 0
        L += [f"## {10 if multi else 7}. Checking the sampling intervals by resampling", "",
              "The *sampling ±* above comes from a formula. As a check, each share was also recomputed on "
              f"{n_boot:,} random samples of the same articles, drawn with replacement (a *bootstrap*; "
              "fixed random seed, so the numbers are the same on every run); the middle 95% of the results "
              "gives the *bootstrap ±*. Compared here for every share with at least "
              f"{MIN_FOR_VERDICT} statements, in each run.", "",
              f"Bootstrap ± divided by formula ±: median {statistics.median(ratios):.2f}, "
              f"from {min(ratios):.2f} to {max(ratios):.2f} ({len(ratios)} shares). A value near 1 means "
              "the formula is trustworthy at this sample size; well below 1 means the formula is too "
              "cautious, well above 1 that it is too confident.", ""]
        if fig:
            L += show(fig.intervals([(f, b) for _, _, _, f, b in rep.intervals]))
        L += table(["share", "run", "statements", "formula ±", "bootstrap ±"],
                   [[w, r, n, f"{f:.1f}", f"{b:.1f}"] for w, r, n, f, b in rep.intervals]) + [""]
    L[glance_at:glance_at] = at_a_glance(rep, runs, labels)
    return "\n".join(L)


def at_a_glance(rep: "Report", runs: list[dict], labels: list[str]) -> list[str]:
    """The main numbers of the report in a few lines, all computed (no interpretation)."""
    out = ["## At a glance", ""]
    for ds, label in zip(runs, labels):
        k = kept(ds)
        pos = sum(s["polarity"] == "positive" for s in k)
        out.append(f"- **{label}**: {len(ds['statements'])} statements in {len(ds['articles'])} articles, "
                   f"{len(k)} kept by the reviewer ({per_thousand(len(k), words(ds)):.1f} per 1,000 words); "
                   f"{pct(pos, len(k))} positive.")
    if rep.multi:
        judged = [g for g in rep.gaps if g[1] is not None]
        larger = [g for g in judged if g[0] > g[1]]
        if judged:
            big = max(judged, key=lambda g: g[0])
            out.append(f"- **Shares** (sections 4, 6, 9): of {len(judged)} shares with enough statements, "
                       f"{len(judged) - len(larger)} differ between runs by less than their sampling uncertainty; "
                       f"the largest gap is {big[0]:.0f} points ({big[2]}, sampling ±{big[1]:.0f}).")
        for (i, a), (j, b) in combinations(enumerate(labels), 2):
            pairs, only_a, only_b = match_statements(runs[i]["statements"], runs[j]["statements"])
            distinct = len(pairs) + len(only_a) + len(only_b)
            if not pairs:
                continue
            agree = []
            for name, key in AGREEMENT_FIELDS:
                if name in ("polarity", "criterion", "statement evidence level (analyst)"):
                    pp = [(key(x), key(y)) for x, y in pairs]
                    agree.append(f"{name.replace(' (analyst)', '')} {100 * sum(x == y for x, y in pp) / len(pp):.0f}%"
                                 f" (kappa {fmt(kappa(pp))})")
            out.append(f"- **Single judgements** (section 8): of {distinct} distinct judgements, "
                       f"{pct(len(pairs), distinct)} were found by both {a} and {b}, {pct(len(only_a), distinct)} "
                       f"only by {a}, {pct(len(only_b), distinct)} only by {b}. Where both found a judgement, "
                       f"they agree on " + ", ".join(agree) + ".")
    if rep.intervals:
        ratios = [b / f for _, _, _, f, b in rep.intervals if f > 0]
        out.append(f"- **Sampling intervals** (section {10 if rep.multi else 7}): resampling the articles gives "
                   f"intervals {statistics.median(ratios):.2f} times as wide as the formula (median).")
    return out + [""]


AGREEMENT_FIELDS = [
    ("art", lambda s: s["art"]),
    ("polarity", lambda s: s["polarity"]),
    ("criterion", lambda s: s["criterion"]),
    ("sarcastic", lambda s: s["sarcastic"]),
    ("quoted (yes/no)", lambda s: "yes" if s["quoted_source"] else "no"),
    ("statement evidence level (analyst)", lambda s: s["evidence_analyst"]),
    ("deleted by the reviewer", lambda s: s["deleted"]),
]


def one_line(text: str) -> str:
    return " ".join(text.split())


def pair_section(a: str, b: str, pairs, only_a, only_b, split: set[str] | None = None,
                 examples: int = 8, fig=None, suffix: str = "") -> list[str]:
    n_a, n_b = len(pairs) + len(only_a), len(pairs) + len(only_b)
    distinct = len(pairs) + len(only_a) + len(only_b)
    L = [f"### {a} and {b}", "",
         *table(["", "statements"], [
             [f"in {a}", n_a], [f"in {b}", n_b],
             ["found by both (pairs)", pct(len(pairs), distinct)],
             [f"found only by {a}", pct(len(only_a), distinct)],
             [f"found only by {b}", pct(len(only_b), distinct)],
             ["distinct judgements in all", distinct]]), "",
         f"Of the statements of {a}, {pct(len(pairs), n_a)} have a partner in {b}; "
         f"of those of {b}, {pct(len(pairs), n_b)} have one in {a}.", ""]
    groups = [("all articles", len(pairs), len(only_a), len(only_b))]
    if split:
        rows = []
        for title, test in ((f"sent in parts in at least one run ({len(split)} articles)", lambda s: s in split),
                            ("sent whole in every run", lambda s: s not in split)):
            pp = sum(1 for x, _ in pairs if test(x["article_id"]))
            oa = sum(1 for s in only_a if test(s["article_id"]))
            ob = sum(1 for s in only_b if test(s["article_id"]))
            rows.append([title, pct(pp, pp + oa + ob), pct(oa, pp + oa + ob), pct(ob, pp + oa + ob)])
            groups.append((title.split(" (")[0].replace("sent in parts in at least one run", "sent in parts"),
                           pp, oa, ob))
        L += ["The same, separately for articles annotated in parts (D-034) and articles sent whole:", "",
              *table(["articles", "found by both", f"only {a}", f"only {b}"], rows), ""]
    if fig:
        L += [fig.matching(groups, a, b, name="matching" + suffix), ""]
    # kept statements and the reviewer
    ka = [p for p in pairs if p[0]["deleted"] == "no"]
    kb = [p for p in pairs if p[1]["deleted"] == "no"]
    both = sum(1 for x, y in pairs if x["deleted"] == y["deleted"] == "no")
    kept_a = len(ka) + sum(s["deleted"] == "no" for s in only_a)
    kept_b = len(kb) + sum(s["deleted"] == "no" for s in only_b)
    L += ["Kept statements (after review):", "",
          *table(["", a, b], [
              ["kept", kept_a, kept_b],
              ["… and kept in the other run too", pct(both, kept_a), pct(both, kept_b)],
              ["… found in the other run but deleted there", pct(len(ka) - both, kept_a), pct(len(kb) - both, kept_b)],
              ["… not found in the other run", pct(sum(s['deleted'] == 'no' for s in only_a), kept_a),
               pct(sum(s['deleted'] == 'no' for s in only_b), kept_b)]]), ""]
    # field agreement
    rows = []
    for name, key in AGREEMENT_FIELDS:
        pp = [(key(x), key(y)) for x, y in pairs]
        same = sum(x == y for x, y in pp)
        rows.append([name, pct(same, len(pp)), fmt(kappa(pp))])
    tgt = sum(same_target(x, y) or (not (x["creator"] or x["work_title"] or y["creator"] or y["work_title"]))
              for x, y in pairs)
    rows.append(["target (same creator or title, written alike)", pct(tgt, len(pairs)), "–"])
    chart = []
    if fig and pairs:
        data = []
        for name, key in AGREEMENT_FIELDS:
            pp = [(key(x), key(y)) for x, y in pairs]
            data.append((name, 100 * sum(x == y for x, y in pp) / len(pp), kappa(pp)))
        data.append(("target (same name or title)", 100 * tgt / len(pairs), None))
        chart = [fig.agreement(data, a, b, name="agreement" + suffix), ""]
    L += ["Agreement on the paired statements. *Same* is the share of pairs with the same value; *kappa* "
          "corrects it for the agreement two runs would reach by chance with these proportions (1 = always "
          "the same, 0 = no better than chance; above about 0.6 is usually called substantial, below 0.4 "
          "weak).", "", *chart, *table(["field", "same", "kappa"], rows), ""]
    # criterion confusion
    crit = CONTROLLED["criterion"]
    c = Counter((x["criterion"], y["criterion"]) for x, y in pairs)
    L += [f"Criterion in the paired statements (rows: {a}; columns: {b}):", "",
          *table([f"{a} \\ {b}", *crit], [[k, *[c[(k, m)] or "" for m in crit]] for k in crit]), ""]
    # examples
    def ex(s):
        return (f"`{s['statement_id']}` “{one_line(s['evaluative_expression'])}” — {s['polarity']}, {s['criterion']}"
                + (" (deleted)" if s["deleted"] == "yes" else ""))
    L += [f"Examples of judgements found only by {a} (first {examples} kept ones, in article order):", ""]
    L += [f"- {ex(s)}" for s in [s for s in only_a if s["deleted"] == "no"][:examples]] or ["- (none)"]
    L += ["", f"Examples found only by {b}:", ""]
    L += [f"- {ex(s)}" for s in [s for s in only_b if s["deleted"] == "no"][:examples]] or ["- (none)"]
    diff = [(x, y) for x, y in pairs if x["criterion"] != y["criterion"]][:examples]
    L += ["", "Examples of paired statements with different criteria:", ""]
    L += [f"- “{one_line(x['evaluative_expression'])}” / “{one_line(y['evaluative_expression'])}” (`{x['article_id']}`): "
          f"{x['criterion']} / {y['criterion']}" for x, y in diff] or ["- (none)"]
    return L + [""]


# ---------------------------------------------------------------- command


def run(cfg: dict, sample: bool = False, datasets: list[str] | None = None, labels: list[str] | None = None,
        name: str | None = None) -> Path:
    folders = [Path(d) for d in datasets] if datasets else [default_folders(cfg, sample)[1]]
    labels = labels or [f.name for f in folders]
    if len(labels) != len(folders):
        raise SystemExit("give one label per dataset")
    name = name or ("sample" if sample else None)
    log = RunLog("stats" + (f"-{name}" if name else ""), cfg["paths"]["logs"])
    runs = [load_dataset(f) for f in folders]
    excluded: dict[str, list[str]] = {}
    if len(runs) > 1:
        common = set.intersection(*[{a["article_id"] for a in ds["articles"] if a["in_dataset"] == "yes"}
                                    for ds in runs])
        for ds, label in zip(runs, labels):
            excluded[label] = sorted({a["article_id"] for a in ds["articles"] if a["in_dataset"] == "yes"} - common)
        runs = [restrict(ds, common) for ds in runs]
    else:
        ids = {a["article_id"] for a in runs[0]["articles"] if a["in_dataset"] == "yes"}
        runs = [restrict(runs[0], ids)]
    command = "uv run ncse stats" + (" --sample" if sample and not datasets else "")
    if datasets:
        command += " --datasets " + " ".join(datasets)
        if labels and labels != [f.name for f in folders]:
            command += " --labels " + " ".join(labels)
        if name:
            command += f" --name {name}"
    stem = "05-statistics" + (f"-{name}" if name else "")
    report = cfg["paths"]["reports"] / f"{stem}.md"
    # Charts go to reports/figures/<report name>/; old ones are removed first, so none is left stale.
    folder = cfg["paths"]["reports"] / "figures" / stem
    for old in folder.glob("*.svg") if folder.exists() else []:
        old.unlink()
    fig = figures.Figures(folder, f"figures/{stem}")
    settings = cfg.get("stats", {})
    text = build_report(runs, labels, excluded, command, fig=fig,
                        bootstrap=settings.get("bootstrap", 2000), seed=settings.get("seed", 1850))
    report.write_text(text + "\n", encoding="utf-8")
    log.count("charts", len(fig.written))
    for ds, label in zip(runs, labels):
        log.count(f"{label}: articles", len(ds["articles"]))
        log.count(f"{label}: statements kept", len(kept(ds)))
    log.info(f"report written to {report}")
    log.close()
    return report
