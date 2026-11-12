"""Full-area coverage with decomposed QAOA (v2 solver used by the web app).

A whole street area needs hundreds of candidate configurations, far more qubits than
can be simulated, so the problem is solved by spatial decomposition:

  1. Exact set-cover reductions: zone dominance (if S_a is a subset of S_b, covering a covers b).
  2. Repeat until every street point is covered:
       - seed = the hardest uncovered point (fewest available cameras)
       - cluster = up to CLUSTER_ZONES nearby uncovered points
       - pick <= MAX_QUBITS candidate configs for the cluster (cover-first, zone degree <= 4,
         mounts already used elsewhere are excluded)
       - build the higher-order cost Hamiltonian of that sub-problem and run QAOA
         (CVaR, p layers); keep the cheapest feasible sampled bitstring
       - every point seen by the chosen cameras is marked covered
  3. References on the WHOLE area: exact MILP (HiGHS), greedy set cover, and the same
     decomposition with an exact brute-force sub-solver (isolates decomposition loss
     from QAOA loss).
  4. Selected cameras are coloured (DSatur) so cameras whose views touch never share a colour.

    python -m src.solve_area sector_8 sector_12 sector_16
"""
import argparse
import json
import math
import time

import numpy as np
from shapely.geometry import Polygon

from src.classical.baselines import exact_bruteforce, exact_milp
from src.model import ROOT, bits_to_x, load_problem
from src.quantum.hamiltonian import build_cost_operator, operator_stats
from src.quantum.qaoa import QAOASolver

RESULTS = ROOT / "data" / "results"
INSTANCES = ROOT / "data" / "instances"
MAX_QUBITS = 12
CLUSTER_ZONES = 6
MAX_SUB_ZONES = 24      # cluster + other uncovered points the chosen cameras can see
MAX_DEGREE = 4


# ---------------------------------------------------------------- helpers
def reduce_zones(cover_sets):
    """Row dominance for set cover: keep only zones whose cover set has no subset among kept zones."""
    sets = [frozenset(s) for s in cover_sets]
    keep = []
    for i in sorted(range(len(sets)), key=lambda i: (len(sets[i]), i)):
        if not any(sets[k] <= sets[i] for k in keep):
            keep.append(i)
    return sorted(keep)


def pick_candidates(cluster, covers_of, cand_covers, cost, available, uncovered):
    """Choose <= MAX_QUBITS configs that can cover every cluster zone with degree <= MAX_DEGREE.
    Candidates are ranked by how much still-uncovered street they see per unit cost, so the
    sub-problem favours cameras that are useful for the whole area, not just this cluster."""
    cset = set(cluster)
    pool = [j for z in cluster for j in covers_of[z] if j in available]
    pool = sorted(set(pool), key=lambda j: (-len(cand_covers[j] & uncovered) / cost[j], j))
    chosen, deg = [], {z: 0 for z in cluster}

    def ok(j):
        return all(deg[z] < MAX_DEGREE for z in cand_covers[j] & cset)

    def add(j):
        chosen.append(j)
        for z in cand_covers[j] & cset:
            deg[z] += 1

    for z in sorted(cluster, key=lambda z: len([j for j in covers_of[z] if j in available])):
        if deg[z] > 0 or len(chosen) >= MAX_QUBITS:
            continue
        opts = [j for j in pool if z in cand_covers[j] and j not in chosen]
        if not opts:
            continue
        good = [j for j in opts if ok(j)]
        add((good or opts)[0])
    for j in pool:                                   # alternatives -> genuine trade-offs
        if len(chosen) >= MAX_QUBITS:
            break
        if j not in chosen and ok(j):
            add(j)
    return sorted(chosen)


def subinstance(cluster, chosen, inst):
    cands = inst["candidates"]
    cset = set(cluster)
    zmap = {z: k for k, z in enumerate(cluster)}
    jmap = {j: k for k, j in enumerate(chosen)}
    mmap = {}
    sub_c = []
    for j in chosen:
        c = cands[j]
        mmap.setdefault(c["mount_id"], len(mmap))
        sub_c.append({"id": jmap[j], "mount_id": mmap[c["mount_id"]], "cost": c["cost"], "power_w": c["power_w"]})
    zones = [{"id": zmap[z], "weight": inst["zones"][z]["weight"]} for z in cluster]
    coverage = {str(zmap[z]): [jmap[j] for j in chosen if z in set(cands[j]["covers"])] for z in cluster}
    return {"name": "sub", "zones": zones, "candidates": sub_c, "coverage": coverage}


def color_cameras(selected, cands):
    """DSatur colouring of the 'views touch' graph (FOV polygons intersect or mounts < 20 m)."""
    polys = {j: Polygon(cands[j]["fov_polygon"]).buffer(0) for j in selected}
    adj = {j: set() for j in selected}
    for a in selected:
        for b in selected:
            if a < b and (polys[a].intersects(polys[b]) or
                          math.dist((cands[a]["x"], cands[a]["y"]), (cands[b]["x"], cands[b]["y"])) < 20):
                adj[a].add(b)
                adj[b].add(a)
    colors = {}
    while len(colors) < len(selected):
        j = max((v for v in selected if v not in colors),
                key=lambda v: (len({colors[u] for u in adj[v] if u in colors}), len(adj[v]), -v))
        used = {colors[u] for u in adj[j] if u in colors}
        colors[j] = next(k for k in range(len(selected) + 1) if k not in used)
    return {str(j): c for j, c in colors.items()}, sum(len(v) for v in adj.values()) // 2


def area_greedy(cand_covers, cost, n_zones, mount_of):
    covered, x, used = set(), [], set()
    while len(covered) < n_zones:
        best, score = None, 0.0
        for j, cv in enumerate(cand_covers):
            if mount_of[j] in used:
                continue
            g = len(cv - covered)
            if g and g / cost[j] > score:
                best, score = j, g / cost[j]
        if best is None:
            break
        x.append(best)
        used.add(mount_of[best])
        covered |= cand_covers[best]
    return sorted(x)


# ---------------------------------------------------------------- decomposition
def decompose(inst, B, p, subsolver, seed, shots, restarts, maxiter):
    cands, zones = inst["candidates"], inst["zones"]
    cand_covers = [set(c["covers"]) for c in cands]
    cost = [c["cost"] for c in cands]
    mount_of = [c["mount_id"] for c in cands]
    covers_of = [inst["coverage"][str(z["id"])] for z in zones]
    key_zones = reduce_zones(covers_of)
    uncovered = set(key_zones)
    selected, used_mounts, subs = [], set(), []
    xy = [(z["x"], z["y"]) for z in zones]
    while uncovered:
        available = {j for j in range(len(cands)) if mount_of[j] not in used_mounts}
        seed_z = min(uncovered, key=lambda z: (sum(1 for j in covers_of[z] if j in available), z))
        cluster = sorted(uncovered, key=lambda z: (math.dist(xy[z], xy[seed_z]), z))[:CLUSTER_ZONES]
        chosen = pick_candidates(cluster, covers_of, cand_covers, cost, available, uncovered)
        reachable = [z for z in cluster if any(z in cand_covers[j] for j in chosen)]
        if not reachable:                      # nothing left that can see these points
            uncovered -= set(cluster)
            continue
        # also reward every other uncovered point these candidates can see (degree-capped)
        extra = sorted(z for z in uncovered - set(reachable)
                       if 1 <= sum(1 for j in chosen if z in cand_covers[j]) <= MAX_DEGREE)
        cluster = reachable + extra[:MAX_SUB_ZONES - len(reachable)]
        sub = subinstance(cluster, chosen, inst)
        prob = load_problem(sub, B=B)
        t0 = time.perf_counter()
        bf = exact_bruteforce(prob)
        info = {"qubits": prob.n, "zones": len(cluster), "exact_energy": round(bf["energy"], 4)}
        if subsolver == "qaoa":
            op = build_cost_operator(prob)
            solver = QAOASolver(op, reps=p, shots=shots, seed=seed, restarts=restarts, maxiter=maxiter,
                                objective="cvar")
            solver.optimize(bf["energies"])
            counts = solver.sample()
            probs = solver.probabilities()
            ranked = sorted(counts, key=lambda b: (prob.energy(bits_to_x(b, prob.n)), -counts[b]))
            feas = [b for b in ranked if prob.stats(bits_to_x(b, prob.n))["feasible"]]
            pick = (feas or ranked)[0]
            x = bits_to_x(pick, prob.n)
            opt_mask = np.isclose(bf["energies"], bf["energy"])
            info.update({
                **solver.circuit_stats(), "operator": operator_stats(op),
                "qaoa_energy": round(prob.energy(x), 4), "optimal": bool(np.isclose(prob.energy(x), bf["energy"])),
                "feasible_sample": bool(feas), "p_optimal": round(float(probs[opt_mask].sum()), 5),
                "p_optimal_random": round(float(opt_mask.mean()), 6), "evals": solver.n_evals,
                "convergence": [round(v, 4) for v in solver.history],
                "top_bitstrings": [{"bits": b, "prob": round(c / shots, 4),
                                    "energy": round(prob.energy(bits_to_x(b, prob.n)), 3),
                                    "feasible": prob.stats(bits_to_x(b, prob.n))["feasible"],
                                    "optimal": bool(np.isclose(prob.energy(bits_to_x(b, prob.n)), bf["energy"]))}
                                   for b, c in sorted(counts.items(), key=lambda kv: -kv[1])[:12]],
            })
        else:
            x = bf["x"]
        pick_global = [chosen[k] for k in range(prob.n) if x[k]]
        # repair (classical, reported): any cluster point the sub-solution leaves unseen
        repaired = 0
        for z in reachable:
            if not any(z in cand_covers[j] for j in pick_global):
                opts = [j for j in chosen if z in cand_covers[j] and mount_of[j] not in
                        {mount_of[q] for q in pick_global}]
                if opts:
                    pick_global.append(min(opts, key=lambda j: cost[j]))
                    repaired += 1
        info["repaired"] = repaired
        info["runtime_s"] = round(time.perf_counter() - t0, 3)
        subs.append(info)
        before = len(uncovered)
        for j in pick_global:
            selected.append(j)
            used_mounts.add(mount_of[j])
            uncovered -= cand_covers[j]
        if len(uncovered) == before:           # no progress possible here: give these points up
            uncovered -= set(reachable)
    # redundancy pruning (classical clean-up): drop cameras whose points are all seen by others
    sel = sorted(set(selected), key=lambda j: (-cost[j], j))
    pruned = []
    for j in sel:
        others = set().union(*(cand_covers[k] for k in sel if k != j and k not in pruned))
        if cand_covers[j] & set(key_zones) <= others:
            pruned.append(j)
    final = sorted(j for j in sel if j not in pruned)
    if subs:
        subs[-1]["pruned_after_merge"] = len(pruned)
    return final, subs, len(key_zones)


# ---------------------------------------------------------------- main entry
def solve_area(name, p=2, B=2.0, seed=7, shots=2048, restarts=2, maxiter=100, save=True, instance=None):
    inst = instance if instance is not None else json.loads((INSTANCES / f"{name}.json").read_text())
    cands = inst["candidates"]
    full = load_problem(inst, B=B)
    n = len(cands)
    cand_covers = [set(c["covers"]) for c in cands]
    mount_of = [c["mount_id"] for c in cands]

    def as_x(sel):
        x = np.zeros(n, dtype=int)
        x[list(sel)] = 1
        return x

    t = time.perf_counter(); mp = exact_milp(full); t_milp = time.perf_counter() - t
    t = time.perf_counter(); gr = area_greedy(cand_covers, full.cost, len(inst["zones"]), mount_of); t_gr = time.perf_counter() - t
    t = time.perf_counter(); dx, dsubs, n_key = decompose(inst, B, p, "exact", seed, shots, restarts, maxiter)
    t_dx = time.perf_counter() - t
    t = time.perf_counter(); qx, qsubs, _ = decompose(inst, B, p, "qaoa", seed, shots, restarts, maxiter)
    t_q = time.perf_counter() - t

    e_opt = full.energy(mp["x"])

    def method(sel, runtime, **extra):
        x = as_x(sel)
        s = full.stats(x)
        s["runtime_s"] = round(runtime, 3)
        s["approx_ratio"] = round(e_opt / s["energy"], 4) if s["energy"] > 0 else 1.0
        colors, edges = color_cameras(s["selected"], cands)
        s["colors"] = colors
        s["num_colors"] = (max(colors.values()) + 1) if colors else 0
        s["adjacent_pairs"] = edges
        s.update(extra)
        return s

    solutions = {
        "qaoa": method(qx, t_q, method="decomposed QAOA (CVaR) on <=12-qubit sub-problems",
                       subproblems=len(qsubs), repaired=sum(s["repaired"] for s in qsubs),
                       pruned_after_merge=sum(s.get("pruned_after_merge", 0) for s in qsubs)),
        "exact": method(np.flatnonzero(mp["x"]).tolist(), t_milp, method="exact MILP (HiGHS) on the whole area"),
        "greedy": method(gr, t_gr, method="greedy set cover on the whole area"),
        "decomposed_exact": method(dx, t_dx, method="same decomposition, brute-force sub-solver",
                                   subproblems=len(dsubs)),
    }
    rep = max(qsubs, key=lambda s: (s["qubits"], s["zones"]))      # representative circuit
    opt_subs = sum(1 for s in qsubs if s["optimal"])
    amp = [s["p_optimal"] / s["p_optimal_random"] for s in qsubs if s["p_optimal_random"] > 0]
    quantum = {
        "num_qubits": rep["qubits"], "p": p, "depth": rep["depth"], "two_qubit_gates": rep["two_qubit_gates"],
        "gate_counts": rep["gate_counts"], "objective": "cvar", "optimizer": "COBYLA", "restarts": restarts,
        "shots": shots, "operator": rep["operator"],
        "circuit_evaluations": sum(s["evals"] for s in qsubs),     # across all QAOA sub-problems
        "top_bitstrings": rep["top_bitstrings"], "convergence": rep["convergence"],
        "p_optimal": rep["p_optimal"], "p_optimal_random": rep["p_optimal_random"],
        "amplification": round(rep["p_optimal"] / rep["p_optimal_random"], 2) if rep["p_optimal_random"] else None,
        "decomposition": {
            "subproblems": len(qsubs), "max_qubits": MAX_QUBITS, "cluster_zones": CLUSTER_ZONES,
            "subproblems_solved_optimally": opt_subs,
            "mean_amplification": round(float(np.mean(amp)), 2) if amp else None,
            "circuit_evaluations": sum(s["evals"] for s in qsubs),
            "repaired_points": sum(s["repaired"] for s in qsubs),
            "key_points_after_dominance": n_key, "street_points": len(inst["zones"]),
            "candidates": n,
        },
        "subproblems": [{k: v for k, v in s.items() if k not in ("convergence", "top_bitstrings")} for s in qsubs],
        "penalties": {"B_coverage": full.B, "P_mount": full.P},
    }
    zones = []
    for z in inst["zones"]:
        cb = inst["coverage"][str(z["id"])]
        zones.append({**z, "covered_by": cb,
                      "covered": {m: any(j in s["selected"] for j in cb) for m, s in solutions.items()}})
    result = {"instance": name, "kind": "area", "sector": inst["sector"],
              "params": {**inst["params"], "p": p, "B": B, "objective": "cvar", "seed": seed},
              "zones": zones, "candidates": cands, "solutions": solutions, "quantum": quantum}
    result = json.loads(json.dumps(result, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    if save:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"result_{name}.json").write_text(json.dumps(result))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance", nargs="+")
    ap.add_argument("--p", type=int, default=2)
    ap.add_argument("--B", type=float, default=2.0)
    a = ap.parse_args()
    for nm in a.instance:
        t = time.perf_counter()
        r = solve_area(nm, p=a.p, B=a.B)
        q = r["quantum"]["decomposition"]
        print(f"{nm}: {q['street_points']} street points, {q['candidates']} candidates, "
              f"{q['subproblems']} QAOA sub-problems ({q['subproblems_solved_optimally']} optimal, "
              f"mean amplification x{q['mean_amplification']}, repaired {q['repaired_points']}), "
              f"{time.perf_counter() - t:.0f}s")
        for m, s in r["solutions"].items():
            print(f"   {m:16s} cams={s['num_cameras']:3d} coverage={s['coverage_pct']}% cost={s['cost']} "
                  f"ratio={s['approx_ratio']} colours={s['num_colors']} t={s['runtime_s']}s")


if __name__ == "__main__":
    main()
