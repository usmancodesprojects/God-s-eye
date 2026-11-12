"""Correctness checks for the quantum mapping and the classical references."""
import numpy as np
import pytest

from src.classical.baselines import exact_bruteforce, exact_milp
from src.model import load_problem
from src.quantum.hamiltonian import build_cost_operator


@pytest.mark.parametrize("name", ["intersections_8", "intersections_12"])
def test_operator_diagonal_equals_objective(name):
    """Every eigenvalue of the Pauli operator equals H(x) for the matching bitstring."""
    prob = load_problem(name)
    op = build_cost_operator(prob)
    diag = np.real(op.to_matrix(sparse=True).diagonal())
    assert np.allclose(diag, prob.all_energies())
    # and the operator is purely diagonal (only Z / I terms)
    assert not any(p.x.any() for p in op.paulis)


@pytest.mark.parametrize("name", ["intersections_8", "intersections_12", "intersections_16"])
def test_bruteforce_matches_independent_milp(name):
    prob = load_problem(name)
    bf, mp = exact_bruteforce(prob), exact_milp(prob)
    assert np.isclose(bf["energy"], mp["energy"])


def test_single_energy_matches_vectorised():
    prob = load_problem("intersections_8")
    e = prob.all_energies()
    for k in [0, 1, 37, 2 ** prob.n - 1]:
        x = [(k >> j) & 1 for j in range(prob.n)]
        assert np.isclose(prob.energy(x), e[k])
