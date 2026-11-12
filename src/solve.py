"""End-to-end solve: instance -> Hamiltonian -> QAOA + classical references -> result JSON.

Usage:
    python -m src.solve sector_12              # writes results/result_sector_12.json
    python -m src.solve sector_16 --p 2 --B 2.0 --objective cvar
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from src.classical.baselines import exact_bruteforce, exact_milp, greedy
from src.model import ROOT, bits_to_x, load_problem
from src.quantum.hamiltonian import build_cost_operator, operator_stats
from src.quantum.qaoa import QAOASolver

RESULTS = ROOT / "data" / "results"     # canonical files served to the web app


def _method(prob, x, runtime, e_opt, **extra):
    s = prob.stats(x)
    s["runtime_s"] = round(runtime, 4)
    s["approx_ratio"] = round(e_opt / s["energy"], 4) if s["energy"] > 0 else 1.0
    s.update(extra)
    return s


def solve(name, p=2, B=2.0, objective="cvar", shots=4096, seed=7, restarts=3, maxiter=150, save=True,
          instance=None):
    """name: instance name in data/instances/, or a label when `instance` (dict) is supplied."""
    prob = load_problem(instance if instance is not None else name, B=B)
    t_build = time.perf_counter()
    op = build_cost_operator(prob)
    t_build = time.perf_counter() - t_build

    bf = exact_bruteforce(prob)
    energies, e_opt = bf["energies"], bf["energy"]
    mp = exact_milp(prob)
    gr = greedy(prob)

    # ---------------- quantum ----------------
    t0 = time.perf_counter()
    solver = QAOASolver(op, reps=p, shots=shots, seed=seed, restarts=restarts, maxiter=maxiter, objective=objective)
    # CVaR needs the energy of each basis state; it is read off the (diagonal) cost operator.
    solver.optimize(energies if objective == "cvar" else None)
    counts = solver.sample()
    q_time = time.perf_counter() - t0
    probs = solver.probabilities()

    decoded = []
    for bits, c in counts.items():
        x = bits_to_x(bits, prob.n)
        decoded.append((bits, c, x, prob.energy(x)))
    decoded.sort(key=lambda d: (d[3], -d[1]))
    best_bits, _, best_x, _ = decoded[0]
    most_bits = max(counts, key=counts.get)
    opt_mask = np.isclose(energies, e_opt)

    # Random-guess control with the same shot budget
    rng = np.random.default_rng(seed)
    rand_idx = rng.integers(0, 2 ** prob.n, size=shots)
    rand_best = float(energies[rand_idx].min())

    top = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
    quantum = {
        **solver.circuit_stats(),
        "objective": objective,
        "optimizer": "COBYLA",
        "restarts": restarts,
        "circuit_evaluations": solver.n_evals,
        "shots": shots,
        "operator": operator_stats(op),
        "penalties": {"B_coverage": prob.B, "P_mount": prob.P},
        "optimal_params": {"beta": [round(v, 4) for v in solver.theta[:p]],
                           "gamma_scaled": [round(v, 4) for v in solver.theta[p:]], "op_scale": solver.scale},
        "top_bitstrings": [{"bits": b, "prob": round(c / shots, 4), "energy": round(prob.energy(bits_to_x(b, prob.n)), 3),
                            "feasible": prob.stats(bits_to_x(b, prob.n))["feasible"],
                            "optimal": bool(np.isclose(prob.energy(bits_to_x(b, prob.n)), e_opt))} for b, c in top],
        "convergence": [round(v, 4) for v in solver.history],
        "expected_energy": round(float(probs @ energies), 4),
        "energy_min": round(e_opt, 4),
        "energy_max": round(float(energies.max()), 4),
        "p_optimal": round(float(probs[opt_mask].sum()), 5),
        "p_optimal_sampled": round(sum(d[1] for d in decoded if np.isclose(d[3], e_opt)) / shots, 5),
        "p_optimal_random": round(float(opt_mask.mean()), 6),
        "amplification": round(float(probs[opt_mask].sum() / opt_mask.mean()), 2),
        "p_feasible": round(sum(c for b, c in counts.items() if prob.stats(bits_to_x(b, prob.n))["feasible"]) / shots, 4),
        "random_sampling_best_energy": round(rand_best, 4),
        "hamiltonian_build_s": round(t_build, 4),
    }

    solutions = {
        "qaoa": _method(prob, best_x, q_time, e_opt, bits=best_bits,
                        most_probable=prob.stats(bits_to_x(most_bits, prob.n))),
        "exact": _method(prob, bf["x"], bf["runtime_s"], e_opt, method="brute force 2^n", n_optimal=bf["n_optimal"]),
        "milp": _method(prob, mp["x"], mp["runtime_s"], e_opt, method="scipy HiGHS MILP"),
        "greedy": _method(prob, gr["x"], gr["runtime_s"], e_opt, method="weighted set-cover greedy"),
    }

    inst = prob.raw
    zones = []
    for z in inst["zones"]:
        cb = inst["coverage"][str(z["id"])]
        zones.append({**z, "covered_by": cb,
                      "covered": {m: any(j in s["selected"] for j in cb) for m, s in solutions.items()}})
    result = {
        "instance": name,
        "sector": inst["sector"],
        "params": {**inst["params"], "p": p, "B": B, "objective": objective, "seed": seed},
        "zones": zones,
        "candidates": inst["candidates"],
        "solutions": solutions,
        "quantum": quantum,
    }
    if save:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / f"result_{name}.json").write_text(json.dumps(result, indent=1))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance", nargs="+")
    ap.add_argument("--p", type=int, default=2)
    ap.add_argument("--B", type=float, default=2.0)
    ap.add_argument("--objective", default="cvar", choices=["cvar", "expectation"])
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    for name in a.instance:
        r = solve(name, p=a.p, B=a.B, objective=a.objective, shots=a.shots, seed=a.seed)
        s, q = r["solutions"], r["quantum"]
        print(f"{name}: qubits={q['num_qubits']} depth={q['depth']} cx={q['two_qubit_gates']}")
        for m in ["qaoa", "exact", "milp", "greedy"]:
            print(f"  {m:6s} cams={s[m]['num_cameras']} cov={s[m]['coverage_pct']}% cost={s[m]['cost']} "
                  f"E={s[m]['energy']} ratio={s[m]['approx_ratio']} t={s[m]['runtime_s']}s")
        print(f"  P(opt) QAOA={q['p_optimal']} random={q['p_optimal_random']} (x{q['amplification']})")


if __name__ == "__main__":
    main()
