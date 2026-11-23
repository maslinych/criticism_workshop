"""Charts for the statistics report (stage 9, D-036).

Each function draws one chart from numbers that stats.py has already computed,
saves it as an SVG file next to the report and returns the Markdown line that
shows it. SVG images in a Markdown file are displayed by GitHub and GitLab
without any extra setup, so the report can be read directly on the web.

The charts are drawn with matplotlib on a white background (readable in light
and dark page themes). Run colours follow a fixed order (first run blue, second
orange, third green), chosen to stay distinguishable for colour-blind readers;
every chart also has a legend or direct labels, so colour is never the only
clue. The files are written so that the same numbers give the same file
(no date inside, fixed internal identifiers), which keeps git diffs quiet.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt  # noqa: E402

RUN_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BOTH = "#8a8984"       # neutral: judgements found by both runs
SURFACE = "#ffffff"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "svg.hashsalt": "ncse", "svg.fonttype": "none", "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"], "font.size": 9.5,
    "axes.edgecolor": INK_2, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "legend.frameon": False,
})


def clipped(values: list[float], hw: list[float | None]) -> list[list[float]]:
    """Error bar lengths below and above each value; a share or rate cannot go below 0."""
    hw = [h or 0 for h in hw]
    return [[min(h, v) for v, h in zip(values, hw)], hw]


def colour(i: int) -> str:
    return RUN_COLOURS[i % len(RUN_COLOURS)]


class Figures:
    """Saves charts into `folder`; the report refers to them as `prefix/<name>.svg`."""

    def __init__(self, folder: Path, prefix: str):
        self.folder, self.prefix = Path(folder), prefix
        self.folder.mkdir(parents=True, exist_ok=True)
        self.written: list[str] = []

    def save(self, fig, name: str, alt: str) -> str:
        fig.savefig(self.folder / f"{name}.svg", format="svg", bbox_inches="tight", metadata={"Date": None})
        plt.close(fig)
        self.written.append(name)
        return f"![{alt}]({self.prefix}/{name}.svg)"

    # ------------------------------------------------------------ shares with intervals

    def shares(self, panels: list[dict], labels: list[str], name: str = "shares") -> str:
        """Small multiples: one panel per variable, a bar per run and value with
        its 95% sampling interval. panels: [{title, values, shares[run][i], hw[run][i]}] in %."""
        heights = [len(p["values"]) * (0.22 * len(labels) + 0.18) + 0.5 for p in panels]
        fig, axes = plt.subplots(len(panels), 1, figsize=(7.2, sum(heights)),
                                 gridspec_kw={"height_ratios": heights}, sharex=True)
        axes = [axes] if len(panels) == 1 else list(axes)
        bar = 0.8 / len(labels)
        for ax, p in zip(axes, panels):
            n = len(p["values"])
            for r, label in enumerate(labels):
                ys = [i + (r - (len(labels) - 1) / 2) * bar for i in range(n)]
                ax.barh(ys, p["shares"][r], height=bar * 0.9, color=colour(r), label=label,
                        edgecolor=SURFACE, linewidth=1)
                ax.errorbar(p["shares"][r], ys, xerr=clipped(p["shares"][r], p["hw"][r]), fmt="none", ecolor=INK_2, elinewidth=1,
                            capsize=2)
            ax.set_yticks(range(n), p["values"])
            ax.invert_yaxis()
            ax.set_title(p["title"], loc="left", fontsize=10, color=INK, fontweight="bold")
            ax.grid(axis="x", color=GRID, linewidth=0.8)
            ax.set_axisbelow(True)
            ax.tick_params(axis="y", length=0)
        axes[-1].set_xlabel("share of kept statements, % (lines: 95% sampling interval)")
        axes[-1].set_xlim(0, 100)
        handles, names = axes[0].get_legend_handles_labels()
        fig.legend(handles, names, loc="upper right", ncols=len(labels), bbox_to_anchor=(0.98, 1.0))
        fig.tight_layout(rect=(0, 0, 1, 0.98))
        return self.save(fig, name, "Shares of kept statements by art, polarity, criterion, target and evidence, "
                                    "per run, with sampling intervals")

    # ------------------------------------------------------------ polarity by art and criterion

    def polarity(self, panels: list[dict], labels: list[str], name: str = "polarity") -> str:
        """Diverging bars: negative statements to the left of zero, positive to the right, one bar
        per run; the share positive is written beside each bar.
        panels: [{title, values, pos[run][i], neg[run][i]}] (numbers of kept statements)."""
        heights = [len(p["values"]) * (0.24 * len(labels) + 0.2) + 0.55 for p in panels]
        fig, axes = plt.subplots(len(panels), 1, figsize=(7.2, sum(heights)),
                                 gridspec_kw={"height_ratios": heights}, sharex=True)
        axes = [axes] if len(panels) == 1 else list(axes)
        bar = 0.8 / len(labels)
        top = max([v for p in panels for run in p["pos"] for v in run] + [1])
        low = max([v for p in panels for run in p["neg"] for v in run] + [1])
        for ax, p in zip(axes, panels):
            n = len(p["values"])
            for r, label in enumerate(labels):
                ys = [i + (r - (len(labels) - 1) / 2) * bar for i in range(n)]
                ax.barh(ys, [-v for v in p["neg"][r]], height=bar * 0.9, color=colour(r), label=label,
                        edgecolor=SURFACE, linewidth=1)
                ax.barh(ys, p["pos"][r], height=bar * 0.9, color=colour(r), edgecolor=SURFACE, linewidth=1)
                for y, pos, neg in zip(ys, p["pos"][r], p["neg"][r]):
                    if pos + neg:
                        ax.text(pos + top * 0.015, y, f"{100 * pos / (pos + neg):.0f}% positive (n={pos + neg})",
                                va="center", fontsize=7.5, color=INK_2)
            ax.axvline(0, color=INK, linewidth=1)
            ax.set_yticks(range(n), p["values"])
            ax.invert_yaxis()
            ax.tick_params(axis="y", length=0)
            ax.set_title(p["title"], loc="left", fontsize=10, color=INK, fontweight="bold")
            ax.grid(axis="x", color=GRID, linewidth=0.8)
            ax.set_axisbelow(True)
        axes[-1].set_xlim(-low * 1.15, top * 1.55)
        ticks = [t for t in axes[-1].get_xticks() if -low * 1.15 <= t <= top * 1.55]
        axes[-1].set_xticks(ticks, [f"{abs(t):.0f}" for t in ticks])
        axes[-1].set_xlabel("kept statements:  ← negative  |  positive →")
        handles, names = axes[0].get_legend_handles_labels()
        fig.legend(handles, names, loc="upper right", ncols=len(labels), bbox_to_anchor=(0.98, 1.0))
        fig.tight_layout(rect=(0, 0, 1, 0.98))
        return self.save(fig, name, "Negative and positive kept statements by art and by criterion, per run")

    # ------------------------------------------------------------ rates by group

    def rates(self, groups: list[str], rates: list[list[float]], hw: list[list[float | None]],
              labels: list[str], name: str = "rates", breaks: list[int] = ()) -> str:
        """breaks: positions after which a thin line separates two kinds of group."""
        fig, ax = plt.subplots(figsize=(7.2, 0.45 * len(groups) * max(1, len(labels) / 1.5) + 0.8))
        bar = 0.8 / len(labels)
        for r, label in enumerate(labels):
            ys = [i + (r - (len(labels) - 1) / 2) * bar for i in range(len(groups))]
            ax.barh(ys, rates[r], height=bar * 0.9, color=colour(r), label=label, edgecolor=SURFACE)
            ax.errorbar(rates[r], ys, xerr=clipped(rates[r], hw[r]), fmt="none", ecolor=INK_2, elinewidth=1,
                        capsize=2)
        ax.set_yticks(range(len(groups)), groups)
        for b in breaks:
            ax.axhline(b + 0.5, color=INK_2, linewidth=0.8)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(left=0)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel("kept statements per 1,000 words (lines: 95% sampling interval)")
        ax.legend(loc="lower right")
        return self.save(fig, name, "Kept statements per 1,000 words by periodical and decade, per run")

    # ------------------------------------------------------------ per article

    def per_article(self, rows: list[tuple[str, int, int, bool]], a: str, b: str, name: str = "per-article") -> str:
        """rows: (article, count in a, count in b, split in parts in either run)."""
        fig, ax = plt.subplots(figsize=(5.2, 5.0))
        top = max([max(x, y) for _, x, y, _ in rows] + [1]) * 1.08
        ax.plot([0, top], [0, top], color=INK_2, linewidth=1, linestyle=(0, (4, 3)), label="same in both runs")
        for split, marker, text in ((False, "o", "article sent whole"), (True, "^", "sent in parts in a run")):
            pts = [(x, y) for _, x, y, s in rows if s == split]
            if pts:
                ax.scatter(*zip(*pts), s=48 if split else 40, marker=marker, color=colour(0), edgecolor=SURFACE, linewidth=1.5,
                           label=text, zorder=3)
        for aid, x, y, _ in rows:
            if abs(x - y) >= 4:
                ax.annotate(aid, (x, y), xytext=(5, -3), textcoords="offset points", fontsize=8, color=INK_2)
        ax.set_xlim(0, top)
        ax.set_ylim(0, top)
        ax.set_aspect("equal")
        ax.set_xlabel(f"kept statements in {a}")
        ax.set_ylabel(f"kept statements in {b}")
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.legend(loc="upper left", fontsize=8.5)
        return self.save(fig, name, f"Kept statements per article, {a} against {b}")

    # ------------------------------------------------------------ matching

    def matching(self, rows: list[tuple[str, int, int, int]], a: str, b: str, name: str = "matching") -> str:
        """rows: (group, found by both, only a, only b). 100% stacked bars."""
        fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(rows) + 1.1))
        segments = [("found by both runs", BOTH), (f"only {a}", colour(0)), (f"only {b}", colour(1))]
        for i, (group, *counts) in enumerate(rows):
            total = sum(counts) or 1
            left = 0
            for (seg, col), n in zip(segments, counts):
                width = 100 * n / total
                ax.barh(i, width, left=left, height=0.62, color=col, edgecolor=SURFACE, linewidth=2,
                        label=seg if i == 0 else None)
                if width >= 7:
                    ax.text(left + width / 2, i, f"{width:.0f}%", ha="center", va="center", fontsize=8.5,
                            color=SURFACE, fontweight="bold")
                left += width
        ax.set_yticks(range(len(rows)), [f"{g} ({sum(c)})" for g, *c in rows])
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 100)
        ax.set_xlabel("share of distinct judgements, % (in brackets: number of judgements)")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncols=3)
        return self.save(fig, name, f"Judgements found by both runs or by only one, {a} and {b}")

    def agreement(self, rows: list[tuple[str, float, float | None]], a: str, b: str, name: str = "agreement") -> str:
        """rows: (field, % same, kappa)."""
        fig, ax = plt.subplots(figsize=(7.2, 0.38 * len(rows) + 0.9))
        ys = range(len(rows))
        ax.barh(ys, [r[1] for r in rows], height=0.6, color=colour(0), edgecolor=SURFACE)
        for y, (_, same, k) in zip(ys, rows):
            text = f"{same:.0f}%" + (f"   kappa {k:.2f}" if k is not None else "")
            ax.text(min(same, 100) + 1.5, y, text, va="center", fontsize=8.5, color=INK)
        ax.set_yticks(list(ys), [r[0] for r in rows])
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 125)
        ax.set_xticks(range(0, 101, 20))
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel(f"paired judgements with the same value in {a} and {b}, %")
        return self.save(fig, name, f"Agreement between {a} and {b} on each field of the paired judgements")

    # ------------------------------------------------------------ formula against bootstrap

    def intervals(self, points: list[tuple[float, float]], name: str = "intervals") -> str:
        """points: (formula ±, bootstrap ±) in percentage points."""
        fig, ax = plt.subplots(figsize=(4.8, 4.6))
        top = max([max(p) for p in points] + [1]) * 1.1
        ax.plot([0, top], [0, top], color=INK_2, linewidth=1, linestyle=(0, (4, 3)), label="the two agree")
        ax.scatter(*zip(*points), s=36, color=colour(0), edgecolor=SURFACE, linewidth=1.5, zorder=3,
                   label="one share in one run")
        ax.set_xlim(0, top)
        ax.set_ylim(0, top)
        ax.set_aspect("equal")
        ax.set_xlabel("sampling ± by formula (points)")
        ax.set_ylabel("sampling ± by resampling articles (points)")
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.legend(loc="upper left", fontsize=8.5)
        return self.save(fig, name, "Sampling intervals: formula against resampling of articles")
