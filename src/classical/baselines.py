"""Classical references.

* exact_bruteforce : enumerates all 2^n assignments of H(x) -> provably optimal.
* exact_milp       : independent MILP (scipy/HiGHS) of the *constrained* problem
                     (y_i <= sum x_j, one camera per mount). Matching optimum
                     confirms the penalty encoding is faithful.
* greedy           : classic weighted set-cover heuristic (cost-effectiveness),
                     the kind of rule a planner would use by hand.
"""
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


def exact_bruteforce(problem):
    t = time.perf_counter()
    e = problem.all_energies()
    k = int(np.argmin(e))
    emin = float(e[k])
    n_opt = int(np.sum(np.isclose(e, emin)))
    x = np.array([(k >> j) & 1 for j in range(problem.n)])
    return {"x": x, "energy": emin, "n_optimal": n_opt, "energy_max": float(e.max()),
            "runtime_s": time.perf_counter() - t, "energies": e}


def exact_milp(problem):
    t = time.perf_counter()
    n, m = problem.n, len(problem.cover_sets)
    # variables: x_0..x_{n-1}, y_0..y_{m-1} (y_i = zone i covered)
    # min sum c x + B sum w (1 - y)  ==  const + sum c x - B sum w y
    c = np.concatenate([problem.cost, -problem.B * problem.weight])
    A, lb, ub = [], [], []
    for i, S in enumerate(problem.cover_sets):          # y_i - sum_{j in S_i} x_j <= 0
        row = np.zeros(n + m)
        row[S] = -1
        row[n + i] = 1
        A.append(row); lb.append(-np.inf); ub.append(0)
    mounts = {}
    for cand in problem.raw["candidates"]:
        mounts.setdefault(cand["mount_id"], []).append(cand["id"])
    for ids in mounts.values():                         # sum_{j in mount} x_j <= 1
        if len(ids) > 1:
            row = np.zeros(n + m)
            row[ids] = 1
            A.append(row); lb.append(-np.inf); ub.append(1)
    res = milp(c, constraints=LinearConstraint(np.array(A), lb, ub), integrality=np.ones(n + m),
               bounds=Bounds(0, 1))
    x = np.round(res.x[:n]).astype(int)
    return {"x": x, "energy": problem.energy(x), "runtime_s": time.perf_counter() - t, "status": res.message}


def greedy(problem):
    t = time.perf_counter()
    x = np.zeros(problem.n, dtype=int)
    covered = np.zeros(len(problem.cover_sets), dtype=bool)
    blocked = set()
    mount_of = {c["id"]: c["mount_id"] for c in problem.raw["candidates"]}
    while True:
        best, best_score = None, 0.0
        for j in range(problem.n):
            if x[j] or mount_of[j] in blocked:
                continue
            gain = sum(problem.weight[i] for i, S in enumerate(problem.cover_sets) if j in S and not covered[i])
            net = problem.B * gain - problem.cost[j]
            if net <= 0:
                continue
            score = gain / problem.cost[j]
            if score > best_score:
                best, best_score = j, score
        if best is None:
            break
        x[best] = 1
        blocked.add(mount_of[best])
        for i, S in enumerate(problem.cover_sets):
            if best in S:
                covered[i] = True
    return {"x": x, "energy": problem.energy(x), "runtime_s": time.perf_counter() - t}
