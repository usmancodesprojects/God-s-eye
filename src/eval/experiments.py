"""Benchmark sweep for the report.

1. Depth sweep     : p = 1,2,3 x objective {expectation, cvar} on sector_8 / sector_12
2. Pareto sweep    : coverage weight B on sector_12 -> cost vs weighted coverage, QAOA vs exact vs greedy
3. Plots           : results/plots/*.png

Run:  python -m src.eval.experiments
(sector_16 is solved once by `python -m src.solve sector_16`; its statevector CVaR loop takes ~5 min.)
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.model import ROOT  # noqa: E402
from src.solve import solve  # noqa: E402

RES = ROOT / "results"
PLOTS = RES / "plots"
SOLVED = ROOT / "data" / "results"      # result_<instance>.json written by src.solve


def depth_sweep():
    rows = []
    for name in ["intersections_8", "intersections_12"]:
        for obj in ["expectation", "cvar"]:
            for p in [1, 2, 3]:
                r = solve(name, p=p, objective=obj, save=False)
                q, s = r["quantum"], r["solutions"]
                rows.append({"instance": name, "qubits": q["num_qubits"], "objective": obj, "p": p,
                             "depth": q["depth"], "cx": q["two_qubit_gates"], "evals": q["circuit_evaluations"],
                             "p_optimal": q["p_optimal"], "p_optimal_random": q["p_optimal_random"],
                             "amplification": q["amplification"], "p_feasible": q["p_feasible"],
                             "expected_energy": q["expected_energy"], "energy_min": q["energy_min"],
                             "energy_max": q["energy_max"], "qaoa_best_energy": float(s["qaoa"]["energy"]),
                             "found_optimum": bool(s["qaoa"]["approx_ratio"] == 1.0),
                             "runtime_s": s["qaoa"]["runtime_s"]})
                print(rows[-1])
    (RES / "depth_sweep.json").write_text(json.dumps(rows, indent=1))
    return rows


def pareto_sweep(name="intersections_12", Bs=(0.3, 0.5, 0.75, 1.0, 1.5, 2.0)):
    rows = []
    for B in Bs:
        r = solve(name, p=2, B=B, objective="cvar", save=False)
        for m in ["qaoa", "exact", "greedy"]:
            s = r["solutions"][m]
            rows.append({"B": B, "method": m, "cost": s["cost"], "num_cameras": s["num_cameras"],
                         "weighted_coverage_pct": s["weighted_coverage_pct"], "coverage_pct": s["coverage_pct"],
                         "energy": s["energy"], "approx_ratio": s["approx_ratio"]})
        print(B, [(x["method"], x["cost"], x["weighted_coverage_pct"]) for x in rows[-3:]])
    (RES / "pareto_sweep.json").write_text(json.dumps(rows, indent=1))
    return rows


def plots(depth_rows, pareto_rows):
    PLOTS.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 150, "font.size": 9})

    # 1) P(optimal) vs p, QAOA vs random
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    for ax, name in zip(axes, ["intersections_8", "intersections_12"]):
        for obj, mk in [("expectation", "o-"), ("cvar", "s-")]:
            rr = [r for r in depth_rows if r["instance"] == name and r["objective"] == obj]
            ax.plot([r["p"] for r in rr], [r["p_optimal"] for r in rr], mk, label=f"QAOA ({obj})")
        ax.axhline(rr[0]["p_optimal_random"], color="grey", ls="--", label="random guess")
        ax.set_yscale("log"); ax.set_xticks([1, 2, 3]); ax.set_xlabel("QAOA layers p")
        ax.set_title(f"{name} ({rr[0]['qubits']} qubits)"); ax.set_ylabel("P(optimal) per shot")
    axes[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(PLOTS / "p_optimal_vs_depth.png"); plt.close(fig)

    # 2) amplification across instance sizes (from cached full results)
    sizes = []
    for name in ["intersections_8", "intersections_12", "intersections_16"]:
        f = SOLVED / f"result_{name}.json"
        if f.exists():
            q = json.loads(f.read_text())["quantum"]
            sizes.append((name, q["num_qubits"], q["p_optimal"], q["p_optimal_random"]))
    if sizes:
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        xs = np.arange(len(sizes))
        ax.bar(xs - 0.2, [s[2] for s in sizes], 0.4, label="QAOA p=2 (CVaR)")
        ax.bar(xs + 0.2, [s[3] for s in sizes], 0.4, label="uniform random", color="grey")
        ax.set_yscale("log"); ax.set_xticks(xs, [f"{s[1]} qubits" for s in sizes])
        ax.set_ylabel("P(optimal) per shot"); ax.legend(fontsize=7); ax.set_title("Probability amplification")
        for x, s in zip(xs, sizes):
            ax.text(x - 0.2, s[2] * 1.15, f"x{s[2] / s[3]:.0f}", ha="center", fontsize=7)
        fig.tight_layout(); fig.savefig(PLOTS / "amplification.png"); plt.close(fig)

    # 3) Pareto: cost vs weighted coverage
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    for m, mk, col in [("exact", "o", "black"), ("qaoa", "x", "tab:blue"), ("greedy", "^", "tab:orange")]:
        rr = sorted([r for r in pareto_rows if r["method"] == m], key=lambda r: r["cost"])
        ax.plot([r["cost"] for r in rr], [r["weighted_coverage_pct"] for r in rr], mk + ("-" if m == "exact" else ""),
                color=col, label=m, ms=7 if m != "exact" else 5)
    ax.set_xlabel("total cost (hardware + lifetime energy)"); ax.set_ylabel("priority-weighted coverage %")
    ax.set_title("Cost vs coverage trade-off (sector_12, sweep of B)"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(PLOTS / "pareto.png"); plt.close(fig)

    # 4) distribution + convergence for sector_12
    f = SOLVED / "result_intersections_12.json"
    if f.exists():
        r = json.loads(f.read_text()); q = r["quantum"]
        fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.2))
        tb = q["top_bitstrings"]
        cols = ["tab:green" if t["optimal"] else ("tab:blue" if t["feasible"] else "tab:red") for t in tb]
        axes[0].bar(range(len(tb)), [t["prob"] for t in tb], color=cols)
        axes[0].set_xticks(range(len(tb)), [f"{t['energy']:.1f}" for t in tb], rotation=60, fontsize=7)
        axes[0].set_xlabel("sampled solution (labelled by cost H)"); axes[0].set_ylabel("frequency")
        axes[0].set_title("Top QAOA samples: green=optimal, blue=feasible, red=infeasible", fontsize=8)
        axes[1].plot(q["convergence"]); axes[1].set_xlabel("COBYLA iteration")
        axes[1].set_ylabel(f"objective ({q['objective']})"); axes[1].set_title("Optimizer convergence")
        fig.tight_layout(); fig.savefig(PLOTS / "samples_and_convergence.png"); plt.close(fig)


if __name__ == "__main__":
    d = depth_sweep()
    pr = pareto_sweep()
    plots(d, pr)
    print("plots written to", PLOTS)
