"""Map the camera-placement objective onto an Ising cost Hamiltonian (SparsePauliOp).

Substitution  x_j = (1 - Z_j) / 2   (|0> -> x=0, |1> -> x=1).

  linear cost        c_j x_j            = c_j/2 (I - Z_j)
  mount exclusivity  x_j x_k            = (I - Z_j - Z_k + Z_j Z_k) / 4
  zone unseen        prod_{j in S}(1-x_j) = 2^{-|S|} * sum_{T subset S} prod_{j in T} Z_j

The last identity is the key modelling choice: the "zone is uncovered" indicator
is encoded EXACTLY as a higher-order (|S|-local) diagonal term. This avoids the
slack qubits a standard QUBO needs for the inequality sum_j x_j >= 1, so the
qubit count equals the number of candidate cameras. QAOA handles k-local Z terms
natively (exp(-i g Z..Z) compiles to a CNOT ladder + one RZ).
"""
from collections import defaultdict
from itertools import combinations

from qiskit.quantum_info import SparsePauliOp


def build_polynomial(problem):
    """Return {tuple(sorted qubits): coeff} for H expressed in Pauli-Z products."""
    poly = defaultdict(float)
    for j, c in enumerate(problem.cost):
        poly[()] += c / 2
        poly[(j,)] -= c / 2
    for j, k in problem.mount_pairs:
        q = problem.P / 4
        poly[()] += q
        poly[(j,)] -= q
        poly[(k,)] -= q
        poly[tuple(sorted((j, k)))] += q
    for w, S in zip(problem.weight, problem.cover_sets):
        amp = problem.B * w / (2 ** len(S))
        for r in range(len(S) + 1):
            for T in combinations(sorted(S), r):
                poly[T] += amp
    return {k: v for k, v in poly.items() if abs(v) > 1e-12}


def build_cost_operator(problem):
    """SparsePauliOp of H (identity term included, so eigenvalues equal H(x))."""
    poly = build_polynomial(problem)
    terms = [("Z" * len(q), list(q), coeff) for q, coeff in poly.items()]
    return SparsePauliOp.from_sparse_list(terms, num_qubits=problem.n).simplify()


def operator_stats(op):
    locality = [sum(ch == "Z" for ch in str(p)) for p in op.paulis]
    return {"num_terms": len(op), "max_locality": max(locality),
            "terms_by_locality": {k: locality.count(k) for k in sorted(set(locality))}}
