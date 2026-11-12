"""QAOA solver built directly on Qiskit primitives.

* Ansatz      : qiskit.circuit.library.QAOAAnsatz with the higher-order cost operator
                and the standard X mixer, p layers.
* Objective   : <psi(beta,gamma)| H |psi(beta,gamma)>  via StatevectorEstimator
                (optionally CVaR_alpha computed from the simulated distribution).
* Optimiser   : COBYLA (scipy), linear-ramp initialisation + seeded random restarts.
* Read-out    : StatevectorSampler with a finite number of shots, decoded into
                camera selections; best sampled bitstring is the QAOA answer.

qiskit-aer is not required: exact statevector simulation is used, which is
practical up to ~20 qubits and matches what an ideal (noise-free) device does.
"""
import time

import numpy as np
from qiskit import transpile
from qiskit.circuit.library import QAOAAnsatz
from qiskit.primitives import StatevectorEstimator, StatevectorSampler
from qiskit.quantum_info import SparsePauliOp, Statevector
from scipy.optimize import minimize

BASIS = ["cx", "rz", "rx", "h", "sx", "x"]


def _split_identity(op):
    const = 0.0
    keep = []
    for pauli, coeff in zip(op.paulis, op.coeffs):
        if not pauli.z.any() and not pauli.x.any():
            const += float(np.real(coeff))
        else:
            keep.append((pauli, coeff))
    rest = SparsePauliOp([p for p, _ in keep], [c for _, c in keep])
    return const, rest


class QAOASolver:
    def __init__(self, cost_op, reps=2, shots=4096, seed=7, restarts=3, maxiter=200,
                 objective="expectation", cvar_alpha=0.2):
        self.n = cost_op.num_qubits
        self.reps, self.shots, self.seed = reps, shots, seed
        self.restarts, self.maxiter = restarts, maxiter
        self.objective, self.cvar_alpha = objective, cvar_alpha
        self.const, rest = _split_identity(cost_op)
        # rescale so gamma has an O(1) natural range; energies are reported in original units
        self.scale = float(np.max(np.abs(rest.coeffs.real)))
        self.op = cost_op
        self.op_scaled = (rest / self.scale).simplify()
        ansatz = QAOAAnsatz(self.op_scaled, reps=reps)
        self.circuit = transpile(ansatz, basis_gates=BASIS, optimization_level=1, seed_transpiler=seed)
        params = list(self.circuit.parameters)
        self.betas = sorted([p for p in params if p.name.startswith("β")], key=lambda p: p.index)
        self.gammas = sorted([p for p in params if p.name.startswith("γ")], key=lambda p: p.index)
        self.estimator = StatevectorEstimator()
        self.history = []

    # ---------- circuit info ----------
    def circuit_stats(self):
        ops = self.circuit.count_ops()
        return {"num_qubits": self.n, "p": self.reps, "depth": self.circuit.depth(),
                "two_qubit_gates": int(ops.get("cx", 0)), "total_gates": int(sum(ops.values())),
                "gate_counts": {k: int(v) for k, v in ops.items()}}

    def _bind(self, theta):
        b, g = theta[: self.reps], theta[self.reps:]
        mapping = {**dict(zip(self.betas, b)), **dict(zip(self.gammas, g))}
        return self.circuit.assign_parameters(mapping)

    # ---------- objective ----------
    def _expectation(self, theta):
        ev = self.estimator.run([(self._bind(theta), self.op)]).result()[0].data.evs
        return float(np.real(ev))

    def _cvar(self, theta, energies):
        probs = Statevector(self._bind(theta)).probabilities()
        order = np.argsort(energies)
        cum = np.cumsum(probs[order])
        cut = np.searchsorted(cum, self.cvar_alpha) + 1
        p = probs[order][:cut].copy()
        p[-1] -= cum[cut - 1] - self.cvar_alpha if cum[cut - 1] > self.cvar_alpha else 0
        return float(p @ energies[order][:cut] / p.sum())

    def optimize(self, energies=None):
        rng = np.random.default_rng(self.seed)
        p = self.reps
        ramp = np.arange(1, p + 1) / (p + 1)
        starts = [np.concatenate([0.6 * (1 - ramp), 0.9 * ramp])]          # linear ramp (adiabatic-like)
        for _ in range(self.restarts - 1):
            starts.append(np.concatenate([rng.uniform(0, np.pi / 2, p), rng.uniform(0, np.pi, p)]))

        def f(theta, trace):
            val = self._cvar(theta, energies) if self.objective == "cvar" else self._expectation(theta)
            trace.append(val)
            return val

        best = None
        self.n_evals = 0
        t0 = time.perf_counter()
        for s in starts:
            trace = []
            res = minimize(f, s, args=(trace,), method="COBYLA", options={"maxiter": self.maxiter, "rhobeg": 0.3})
            self.n_evals += len(trace)
            if best is None or res.fun < best[0].fun:
                best = (res, trace)
        self.opt_time = time.perf_counter() - t0
        self.theta = best[0].x
        self.history = best[1]
        return self.theta

    # ---------- read-out ----------
    def sample(self, theta=None):
        theta = self.theta if theta is None else theta
        qc = self._bind(theta).copy()
        qc.measure_all()
        sampler = StatevectorSampler(seed=self.seed)
        counts = sampler.run([qc], shots=self.shots).result()[0].data.meas.get_counts()
        return counts

    def probabilities(self, theta=None):
        theta = self.theta if theta is None else theta
        return Statevector(self._bind(theta)).probabilities()
