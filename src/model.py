"""Problem model shared by the quantum and classical solvers.

Decision variable  x_j in {0,1}  : deploy candidate configuration j
                                   (mount point + aim direction + lens).

Objective (minimise)
    H(x) =  sum_j c_j x_j                                  hardware + lifetime energy cost
          + B * sum_i w_i * prod_{j in S_i} (1 - x_j)      weighted penalty if zone i is unseen
          + P * sum_{mounts m} sum_{j<k in m} x_j x_k      at most one camera per mount

S_i is the set of configurations that can see zone i (line-of-sight checked),
w_i the zone priority weight, B the coverage weight (the knob that trades cost
against coverage) and P a mount-exclusivity penalty chosen large enough that
violating it never pays off.
"""
import json
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Problem:
    name: str
    n: int                      # number of qubits / candidate configurations
    cost: np.ndarray            # c_j
    weight: np.ndarray          # w_i
    cover_sets: list            # S_i, list of lists of candidate ids
    mount_pairs: list           # (j, k) pairs sharing a mount
    B: float                    # coverage weight
    P: float                    # mount penalty
    raw: dict = field(repr=False, default_factory=dict)

    # ---------- evaluation ----------
    def energy(self, x):
        x = np.asarray(x, dtype=int)
        e = float(self.cost @ x)
        for w, S in zip(self.weight, self.cover_sets):
            if not x[S].any():
                e += self.B * w
        for j, k in self.mount_pairs:
            e += self.P * x[j] * x[k]
        return float(e)

    def all_energies(self):
        """Vectorised H(x) for every basis state k (bit j of k = x_j, Qiskit little-endian)."""
        k = np.arange(2 ** self.n, dtype=np.int64)
        X = ((k[:, None] >> np.arange(self.n)) & 1).astype(np.int8)
        e = X @ self.cost
        for w, S in zip(self.weight, self.cover_sets):
            e += self.B * w * (X[:, S].sum(axis=1) == 0)
        for j, kk in self.mount_pairs:
            e += self.P * (X[:, j] & X[:, kk])
        return e

    def stats(self, x):
        x = np.asarray(x, dtype=int)
        covered = [bool(x[S].any()) for S in self.cover_sets]
        w_cov = float(sum(w for w, c in zip(self.weight, covered) if c))
        mount_ok = all(not (x[j] and x[k]) for j, k in self.mount_pairs)
        cands = self.raw["candidates"]
        sel = [j for j in range(self.n) if x[j]]
        return {
            "selected": sel,
            "num_cameras": len(sel),
            "zones_covered": int(sum(covered)),
            "coverage_pct": round(100.0 * sum(covered) / len(covered), 1),
            "weighted_coverage_pct": round(100.0 * w_cov / float(self.weight.sum()), 1),
            "cost": round(float(self.cost @ x), 3),
            "power_w": round(float(sum(cands[j]["power_w"] for j in sel)), 1),
            "energy": round(self.energy(x), 4),
            "feasible": bool(all(covered) and mount_ok),
        }


def bits_to_x(bits: str, n: int):
    """Qiskit bitstring (qubit n-1 ... qubit 0) -> x vector indexed by qubit."""
    return np.array([int(bits[n - 1 - j]) for j in range(n)], dtype=int)


def load_problem(source, B=2.0, P=None):
    """source: instance dict, path to an instance JSON, or instance name in data/instances/."""
    if isinstance(source, dict):
        inst = source
    else:
        path = Path(source)
        if not path.exists():
            path = ROOT / "data" / "instances" / f"{source}.json"
        inst = json.loads(path.read_text())
    cands = inst["candidates"]
    n = len(cands)
    cost = np.array([c["cost"] for c in cands], dtype=float)
    zones = inst["zones"]
    weight = np.array([z["weight"] for z in zones], dtype=float)
    cover_sets = [inst["coverage"][str(z["id"])] for z in zones]
    by_mount = {}
    for c in cands:
        by_mount.setdefault(c["mount_id"], []).append(c["id"])
    mount_pairs = [p for ids in by_mount.values() for p in combinations(sorted(ids), 2)]
    if P is None:
        # a second camera on a mount can at most uncover-penalty-save this much:
        best_gain = max(B * sum(weight[i] for i, S in enumerate(cover_sets) if j in S) for j in range(n))
        P = round(best_gain + float(cost.max()), 3)
    return Problem(inst["name"], n, cost, weight, cover_sets, mount_pairs, float(B), float(P), inst)
