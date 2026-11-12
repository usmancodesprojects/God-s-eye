"""Static map figure of a solved instance (for the report / video).

python -m src.eval.map_plot sector_16   -> results/plots/map_sector_16.png
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon as MplPoly  # noqa: E402

from src.geo.build_instance import load, to_xy  # noqa: E402
from src.model import ROOT  # noqa: E402

RES = ROOT / "results"


def draw(ax, result, method, buildings, title):
    sel = set(result["solutions"][method]["selected"])
    zones, cands = result["zones"], result["candidates"]
    xs = [z["x"] for z in zones] + [c["x"] for c in cands]
    ys = [z["y"] for z in zones] + [c["y"] for c in cands]
    pad = 70
    box = (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)
    hmax = 200.0
    for b in buildings:
        x0, y0, x1, y1 = b["poly"].bounds
        if x1 < box[0] or x0 > box[1] or y1 < box[2] or y0 > box[3]:
            continue
        shade = 0.85 - 0.5 * min(b["height"], hmax) / hmax
        ax.add_patch(MplPoly(list(b["poly"].exterior.coords), closed=True, fc=(shade, shade, shade + 0.03),
                             ec="white", lw=0.3))
    for c in cands:
        if c["id"] in sel:
            wedge = [to_xy(lat, lon) for lon, lat in c["fov_polygon"]]
            ax.add_patch(MplPoly(wedge, closed=True, fc="tab:blue", alpha=0.18, ec="tab:blue", lw=0.8))
    ax.scatter([c["x"] for c in cands if c["id"] not in sel], [c["y"] for c in cands if c["id"] not in sel],
               s=10, c="grey", marker="o", label="candidate mount", zorder=3)
    ax.scatter([c["x"] for c in cands if c["id"] in sel], [c["y"] for c in cands if c["id"] in sel],
               s=60, c="tab:blue", marker="^", edgecolors="k", label="selected camera", zorder=4)
    for z in zones:
        cov = z["covered"][method]
        ax.scatter(z["x"], z["y"], s=40 + 40 * z["weight"], c="tab:green" if cov else "tab:red",
                   edgecolors="k", zorder=5, marker="o")
    s = result["solutions"][method]
    ax.set_title(f"{title}\n{s['num_cameras']} cameras, cost {s['cost']}, coverage {s['coverage_pct']}%", fontsize=9)
    ax.set_xlim(box[0], box[1]); ax.set_ylim(box[2], box[3]); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])


def main(name):
    result = json.loads((ROOT / "data" / "results" / f"result_{name}.json").read_text())
    buildings, _ = load()
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.2), dpi=150)
    draw(axes[0], result, "qaoa", buildings, "QAOA (matches exact optimum)" if
         result["solutions"]["qaoa"]["approx_ratio"] == 1.0 else "QAOA")
    draw(axes[1], result, "greedy", buildings, "Greedy set-cover baseline")
    axes[0].legend(loc="lower left", fontsize=7)
    fig.suptitle(f"Midtown Manhattan (Bryant Park) - {name}: green = covered intersection, red = uncovered, "
                 f"size = priority", fontsize=9)
    fig.tight_layout()
    out = RES / "plots" / f"map_{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print("wrote", out)


if __name__ == "__main__":
    for n in sys.argv[1:] or ["intersections_16"]:
        main(n)
