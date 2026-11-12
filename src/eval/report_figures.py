"""Figures for the written report (docs/report_assets/).

python -m src.eval.report_figures
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon as MplPoly  # noqa: E402

from src.geo import build_instance as bi  # noqa: E402
from src.model import ROOT  # noqa: E402

OUT = ROOT / "docs" / "report_assets"
RES = ROOT / "data" / "results"
PALETTE = ['#3b6fb6', '#e08a2c', '#8e5cc4', '#2a9d9a', '#c2507a', '#7a9a3a', '#5b6b7a', '#b8860b', '#4f9fd9', '#a0522d']
INK, MUTED, SAGE, VIOLET, BLUE = "#131714", "#5f675f", "#5f8f57", "#8a5cc8", "#3b6fb6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#c9cec5", "figure.dpi": 200})


def architecture():
    fig, ax = plt.subplots(figsize=(11, 6.0))
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")
    # snake layout: lane 1 left->right, lane 2 right->left, lane 3 left->right
    lanes = [
        (42, "1  Spatial data & geometry", "left", "#eef4ea", SAGE, False, [
            "OpenStreetMap\n(Overpass, cached)", "Street sampling\nevery 15 m +\nintersections",
            "Wall mounts ×\n36 aims × 2 lenses", "2.5D line of sight\n(Shapely) →\ncoverage sets S_i"]),
        (24, "2  Quantum optimisation (Qiskit)", "left", "#f2ecfa", VIOLET, True, [
            "Instance\nx_j ∈ {0,1}, c_j, w_i", "Cost Hamiltonian H(x)\nhigher-order Z terms\n(no slack qubits)",
            "Spatial decomposition\n≤ 12-qubit\nsub-problems", "QAOA: QAOAAnsatz ·\nCVaR · COBYLA ·\nStatevectorSampler"]),
        (6, "3  Validation & delivery", "right", "#ecf1f9", BLUE, False, [
            "Exact references\nbrute force · MILP\n(HiGHS) · greedy", "Merge · prune ·\nDSatur colouring",
            "result JSON\n(seeded, reproducible)", "FastAPI → React +\nMapLibre 3D web app"]),
    ]
    for y, title, side, fill, edge, rev, boxes in lanes:
        ax.add_patch(FancyBboxPatch((1, y - 1.5), 98, 15, boxstyle="round,pad=0,rounding_size=2.2", fc=fill, ec="none"))
        ax.text(2.6 if side == "left" else 97.4, y + 11.7, title, fontsize=10, fontweight="bold", color=edge,
                va="center", ha=side)
        for k, label in enumerate(boxes):
            slot = 3 - k if rev else k
            x = 4 + slot * 24
            ax.add_patch(FancyBboxPatch((x, y), 19.5, 9, boxstyle="round,pad=0,rounding_size=1.6",
                                        fc="white", ec=edge, lw=1.3))
            ax.text(x + 9.75, y + 4.5, label, ha="center", va="center", fontsize=8.3, color=INK, linespacing=1.3)
            if k < 3:
                a, b = ((x + 19.6, x + 23.9) if not rev else (x - 0.1, x - 4.4))
                ax.add_patch(FancyArrowPatch((a, y + 4.5), (b, y + 4.5), arrowstyle="-|>",
                                             mutation_scale=11, color=edge, lw=1.3))
    # vertical lane-to-lane links: right end (lane 1 -> 2), left end (lane 2 -> 3)
    for x0, y0, y1 in [(85.75, 42, 33.2), (13.75, 24, 15.2)]:
        ax.add_patch(FancyArrowPatch((x0, y0 - 0.1), (x0, y1), arrowstyle="-|>", mutation_scale=12, color=MUTED, lw=1.4))
    ax.text(50, 58.6, "God’s Eye — system architecture", ha="center", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "architecture.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def area_maps(name="sector_16"):
    r = json.loads((RES / f"result_{name}.json").read_text())
    lon0, lat0 = r["sector"]["center"]
    prev = (bi.LAT0, bi.LON0)
    bi.set_origin(lat0, lon0)
    try:
        buildings, _ = bi.load()
        zones, cands = r["zones"], {c["id"]: c for c in r["candidates"]}
        xs = [z["x"] for z in zones]; ys = [z["y"] for z in zones]
        box = (min(xs) - 60, max(xs) + 60, min(ys) - 60, max(ys) + 60)
        fig, axes = plt.subplots(1, 2, figsize=(11, 5.4))
        for ax, m, title in [(axes[0], "qaoa", "Decomposed QAOA"), (axes[1], "exact", "Exact MILP optimum")]:
            s = r["solutions"][m]
            for b in buildings:
                x0, y0, x1, y1 = b["poly"].bounds
                if x1 < box[0] or x0 > box[1] or y1 < box[2] or y0 > box[3]:
                    continue
                shade = 0.88 - 0.35 * min(b["height"], 200) / 200
                ax.add_patch(MplPoly(list(b["poly"].exterior.coords), closed=True, fc=(shade, shade + .01, shade - .01),
                                     ec="white", lw=0.3))
            for j in s["selected"]:
                c = cands[j]
                col = PALETTE[s["colors"][str(j)] % len(PALETTE)]
                poly = [bi.to_xy(lat, lon) for lon, lat in c["fov_polygon"]]
                ax.add_patch(MplPoly(poly, closed=True, fc=col, alpha=0.22, ec=col, lw=0.8))
                ax.scatter(c["x"], c["y"], s=34, c=col, edgecolors="white", linewidths=0.8, zorder=5, marker="^")
            cov = [z for z in zones if z["covered"][m]]
            unc = [z for z in zones if not z["covered"][m]]
            ax.scatter([z["x"] for z in cov], [z["y"] for z in cov], s=[22 if z["priority"] else 9 for z in cov],
                       c="#3f8f5a", edgecolors="white", linewidths=0.5, zorder=4)
            if unc:
                ax.scatter([z["x"] for z in unc], [z["y"] for z in unc], s=14, c="#d64545", zorder=4)
            ax.set_title(f"{title}\n{s['num_cameras']} cameras · cost {s['cost']} · {s['coverage_pct']}% of "
                         f"{len(zones)} street points · {s['num_colors']} colours", fontsize=9.5, color=INK)
            ax.set_xlim(box[0], box[1]); ax.set_ylim(box[2], box[3]); ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
        fig.tight_layout()
        fig.savefig(OUT / f"area_map_{name}.png", bbox_inches="tight", facecolor="white")
        plt.close(fig)
    finally:
        bi.set_origin(*prev)


def area_comparison():
    names = [("sector_8", "Area S\n32 points"), ("sector_12", "Area M\n103 points"), ("sector_16", "Area L\n230 points")]
    methods = [("exact", "Exact MILP", INK), ("greedy", "Greedy", "#c98a2e"),
               ("decomposed_exact", "Decomposition +\nbrute force", "#9aa59a"), ("qaoa", "Decomposition +\nQAOA", VIOLET)]
    data = {n: json.loads((RES / f"result_{n}.json").read_text())["solutions"] for n, _ in names}
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    x = np.arange(len(names)); w = 0.2
    for ax, key, ylabel in [(axes[0], "num_cameras", "cameras for 100% coverage"), (axes[1], "cost", "total cost (hardware + energy)")]:
        for k, (m, label, col) in enumerate(methods):
            vals = [data[n][m][key] for n, _ in names]
            bars = ax.bar(x + (k - 1.5) * w, vals, w, label=label, color=col)
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v, f"{v:g}", ha="center", va="bottom", fontsize=7, color=INK)
        ax.set_xticks(x, [lab for _, lab in names]); ax.set_ylabel(ylabel)
    axes[0].legend(fontsize=7.5, frameon=False, ncol=2)
    fig.suptitle("Every method reaches 100% street coverage; the exact MILP is the true minimum", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "area_comparison.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def subproblems(name="sector_16"):
    q = json.loads((RES / f"result_{name}.json").read_text())["quantum"]
    subs = q["subproblems"]
    fig, ax = plt.subplots(figsize=(11, 3.4))
    x = np.arange(len(subs))
    ax.bar(x - 0.2, [s["p_optimal"] for s in subs], 0.4, color=VIOLET, label="QAOA (p=2, CVaR): P(optimum) per shot")
    ax.bar(x + 0.2, [s["p_optimal_random"] for s in subs], 0.4, color="#c9cec5", label="uniform random guess")
    ax.set_yscale("log")
    ax.set_xticks(x, [f"#{i + 1}\n{s['qubits']}q" for i, s in enumerate(subs)], fontsize=7.5)
    ax.set_ylabel("probability of sampling\nthe sub-problem optimum")
    for i, s in enumerate(subs):
        ax.text(i - 0.2, s["p_optimal"] * 1.15, f"×{s['p_optimal'] / s['p_optimal_random']:.0f}", ha="center", fontsize=6.5)
    ax.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    ax.set_title(f"Area L: all {len(subs)} QAOA sub-problems solved optimally (verified by brute force)", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "subproblems_sector_16.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    architecture(); area_maps(); area_comparison(); subproblems()
    print("figures written to", OUT)
