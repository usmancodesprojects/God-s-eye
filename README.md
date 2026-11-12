# God’s Eye — Quantum Public-Safety Camera Coverage


**Deliverables:** [Report (.docx)](docs/GodsEye_Report.docx) · [Problem statement](docs/PROBLEM_STATEMENT.md) · [Architecture diagram](docs/report_assets/architecture.png) · [Video script](docs/VIDEO_SCRIPT.md)

**Qiskit Fall Fest 2026 Hackathon · Domain 6: Energy & Smart Infrastructure**

Where should a city mount a limited number of CCTV cameras, which way should each one point and which lens should it use, so that every street intersection in a sector is covered at the lowest hardware and lifetime energy cost?
We build the problem from real OpenStreetMap geometry of Midtown Manhattan (Bryant Park) and solve it with **QAOA in Qiskit**. We compare it against an exact brute-force solution, an independent MILP and a greedy heuristic.

## Full street-area coverage (what the web app shows)

**Goal: 100% camera coverage of every street in the selected area.**

* Each street is sampled every 15 m; intersections are priority points.
* A camera covers a point if the point is within range, inside its field of view, and not blocked by a building.
* Wall mounts are generated along every facade facing a street.
* Each mount has 36 aim presets × 2 lens types.
* View wedges are ray-cast, so they stop at buildings.

A whole area produces hundreds of candidate configurations, far more than the 12-qubit sub-problems we simulate, so `src/solve_area.py` solves it by **spatial decomposition**:
1. Find the hardest uncovered street point, and take its 6 nearest uncovered neighbours as a cluster.
2. Pick at most 12 candidate cameras for that cluster. Each sub-problem includes every uncovered point those candidates can see, with at most 4 candidates per point.
3. Run QAOA (CVaR, p=2) on that sub-problem's higher-order cost Hamiltonian, and keep the cheapest feasible sample.
4. Repeat until all street points are covered.
5. Finally, drop redundant cameras (a classical clean-up).

Selected cameras are then coloured with DSatur graph colouring. Cameras whose views touch, or whose mounts are less than 20 m apart, never share a colour.

| Area | Street points | Candidates | QAOA (decomposed) | Exact MILP (whole area) | Greedy | Decomposed + brute force |
|---|---|---|---|---|---|---|
| S · 6th Ave & 42nd St | 32 | 205 | 6 cams, cost 9.6, **100%** | 5 cams, 7.7, 100% | 5 cams, 8.3, 100% | 6 cams, 9.6 |
| M · Bryant Park west | 103 | 750 | 20 cams, cost 32.6, **100%** | 16 cams, 25.0, 100% | 20 cams, 29.6, 100% | 19 cams, 30.7 |
| L · Bryant Park sector | 230 | 1890 | 48 cams, cost 75.0, **100%** | 33 cams, 54.9, 100% | 45 cams, 65.7, 100% | 47 cams, 73.1 |

* **QAOA quality:** every QAOA sub-problem (3, 7 and 15 of them) was solved **optimally**, as checked against brute force on each sub-problem. The optimum was on average 12–15× more likely to be sampled than by uniform random guessing.
* **Where the cost gap comes from:** QAOA ends up 25–37% more expensive than the whole-area MILP optimum (approximation ratio 0.73–0.80). That gap comes from the **decomposition**, not from QAOA, because the identical decomposition with an exact sub-solver lands at almost the same cost.
* **Colouring:** the camera graph needs 2–4 colours, and no two touching cameras share one (verified).

```bash
python -m src.geo.area_instance                 # build the three street-area instances
python -m src.solve_area sector_8 sector_12 sector_16   # decomposed QAOA + references -> data/results/
```

## Intersection benchmark: exact QAOA without decomposition (QAOA p=2, CVaR objective, 4096 shots, seed 7)

This smaller benchmark covers only intersections, so the whole problem fits in 8–16 qubits and QAOA is checked against the true optimum without any decomposition. Its instances and results are named `intersections_*`.

| Instance | Qubits | Zones | QAOA | Exact optimum | Greedy | P(opt) QAOA vs random |
|---|---|---|---|---|---|---|
| intersections_8  | 8  | 5 | **5.1** (3 cams) ✅ | 5.1 | 5.1 | 0.117 vs 0.0156 (×7) |
| intersections_12 | 12 | 7 | **7.0** (4 cams) ✅ | 7.0 | 8.3 (5 cams) | 0.0146 vs 0.00024 (×60) |
| intersections_16 | 16 | 9 | **8.9** (5 cams) ✅ | 8.9 | 10.2 (6 cams) | 0.0034 vs 0.00003 (×110) |

All solutions cover 100% of the intersections. Cost = hardware capex + 0.05 × lens power (W), in camera-cost units.
On both larger instances QAOA finds the true optimum, while greedy needs one extra camera.

## Problem formulation

* **Decision variables:** `x_j ∈ {0,1}`, deploy candidate configuration *j* = (mount point on a building wall, azimuth, lens type). One qubit per configuration.
* **Coverage:** zone *i* (a street intersection) is seen by configuration *j* if it lies within the lens range and field of view **and** the line of sight is not blocked by any building (Shapely). `S_i` is the set of configurations that see zone *i*.
* **Objective (minimise):**

```
H(x) = Σ_j c_j x_j                                hardware + lifetime energy cost
     + B Σ_i w_i Π_{j∈S_i} (1 − x_j)              priority-weighted penalty for an unseen zone
     + P Σ_mounts Σ_{j<k on mount} x_j x_k        at most one camera per mount
```

* **Quantum mapping:** substituting `x = (1 − Z)/2` gives a diagonal Ising Hamiltonian. The "zone unseen" product is encoded **exactly** as `2^{-|S_i|} Σ_{T⊆S_i} Π_{j∈T} Z_j`, a higher-order (up to 4-local) term. This avoids the slack qubits a QUBO would need for `Σ x_j ≥ 1`, so the qubit count equals the number of candidates. `tests/test_mapping.py` checks that the operator's diagonal equals `H(x)` for every bitstring.
* **Algorithm:**
  * `QAOAAnsatz` (X mixer, p layers), transpiled to `cx/rz/rx/h/sx`.
  * COBYLA with a linear-ramp start plus seeded random restarts.
  * The objective is the **CVaR(α=0.2)** of the energy (Barkoutsos et al., 2020), or the plain expectation via `StatevectorEstimator`.
  * Final read-out uses `StatevectorSampler` (4096 shots), and the lowest-cost sampled bitstring is decoded into cameras.

## Architecture

```
OpenStreetMap (Overpass) ──► data/raw/osm_sector.json (cached, offline-reproducible)
        │
        ▼
src/geo/build_instance.py   zones (intersections, priority weights) · wall mounts ·
                            aim directions × lenses · 2.5D line-of-sight → coverage sets
        │                   → data/instances/sector_{8,12,16}.json
        ▼
src/model.py                H(x) objective, penalties, stats
        │
        ├──► src/quantum/hamiltonian.py   H(x) → SparsePauliOp (higher-order Z terms)
        │          └──► src/quantum/qaoa.py   QAOAAnsatz + COBYLA + Estimator/Sampler
        │
        ├──► src/classical/baselines.py   brute force (exact) · MILP (HiGHS) · greedy
        ▼
src/solve.py ──► data/results/result_<instance>.json   (saved results shown instantly by the app)
src/eval/experiments.py, map_plot.py ──► results/*.json, results/plots/*.png

Web app (Q·Scope)
frontend/  React + MapLibre (OpenFreeMap 3D buildings, no API key) + Chart.js
   │  POST /api/optimize {instance, p, lambda, bbox}
   ▼
backend/app/main.py (FastAPI, validation) ──► backend/app/solver_adapter.py
   • bbox = saved sector  → re-solve that instance with the requested p and λ (λ = coverage weight B)
   • bbox = new region    → live OSM download → geo pipeline → Hamiltonian → QAOA + baselines
```

## Repository layout

| Path | Contents |
|---|---|
| `src/` | Quantum and classical core: geo pipeline, model, Hamiltonian, QAOA, baselines, experiments |
| `tests/` | Core correctness tests (pytest) |
| `data/raw/` | Cached OpenStreetMap data |
| `data/instances/` | The 8/12/16-qubit problem instances |
| `data/results/` | Solver output in the app's JSON contract |
| `results/` | Benchmark sweeps and report plots |
| `backend/` | FastAPI server, request/response validation, solver adapter and tests |
| `frontend/` | React/Vite web app ([details](docs/FULLSTACK_README.md)) |
| `docs/` | Adapter contract, GitHub setup and verification notes |

## Setup and reproduction

Requires Python 3.10+ (tested on 3.12) and Node.js 20.19+ (tested on 24). One Python environment at the repository root serves both the quantum core and the API.

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend ci
```

### Run the web app (saved results and live quantum solving)

```bash
copy backend\.env.example backend\.env      # Linux/macOS: cp backend/.env.example backend/.env
# (the example already sets SOLVER_CALLABLE=app.solver_adapter:optimize for live solving)
npm run dev
```

Open http://localhost:5173. The API runs at http://127.0.0.1:8000 (docs at `/docs`).
* **Saved results** load instantly.
* **Run live** re-solves the area with decomposed QAOA, using the chosen p (1–3) and λ (the coverage weight B, which must be at least 1):
  * Area S: about 5–10 s
  * Area M: about 25 s
  * Area L: about 45 s
* **New region:** edit the map bounds or use **Use map view**, then press **Run live**. This runs the whole pipeline on fresh OpenStreetMap data. Regions are capped at about 400 street points.

### Reproduce the results and plots

```bash
python -m pytest -q tests                                # quantum mapping + exact-solver checks
python -m src.geo.build_instance                         # rebuild instances from cached OSM data
python -m src.solve intersections_8 intersections_12 intersections_16  # intersection benchmark
python -m src.eval.experiments                           # depth & Pareto sweeps + plots -> results/
python -m src.eval.map_plot intersections_12 intersections_16   # map figures -> results/plots/
cd backend && python -m unittest discover -s tests       # API contract tests
npm --prefix frontend test                               # front-end data tests
```

`python -m src.geo.fetch_osm` re-downloads the OSM data. This is optional, because the cached copy is committed.
Every run is seeded (`--seed`, default 7).

## Honest limitations

* **No quantum advantage is claimed.** These instances (≤16 qubits) are solved instantly by brute force and MILP. They exist so QAOA can be checked against a provably exact reference.
* **Simulation only.** Results come from exact, noise-free statevector simulation. The 16-qubit p=2 circuit has 232 CNOTs, which is too deep for reliable current hardware without error mitigation. The 16-qubit CVaR loop takes about 5 minutes on a laptop.
* **The higher-order terms cost depth.** A zone seen by d candidates adds up to 2^d Pauli terms, so we cap d ≤ 4 when building candidates.
* **The decomposition costs optimality.** For full street areas, QAOA only ever sees sub-problems of 12 qubits or fewer. Solving them one at a time and merging them gives a layout 25–37% more expensive than the whole-area MILP optimum, even though every sub-problem is solved optimally. Better ways to split the area, such as overlapping clusters or iterated re-optimisation, are future work. The MILP is the honest reference for "minimum cameras".
* **Coverage of a street = coverage of 15 m sample points.** Gaps between neighbouring sample points are not checked separately.
* **Discretised geometry:** 10° aim presets, two lens types, a fixed 8 m mount height, and 2.5D occlusion (footprints only, ignoring building height and terrain). The field-of-view polygons are ray-cast against the same building footprints.
* **Penalty tuning:** P is set automatically to dominate any gain from double-mounting, but large penalties make the optimisation landscape rougher, and most probability mass still sits on suboptimal or infeasible states.
* **Scaling to a full city** would need decomposing it into sectors, plus warm-starts or hardware runs. We have not evaluated this.
* **Privacy and governance:** the tool only plans *coverage of public streets*. It does not process video or identify people. Any real deployment should follow local privacy law and signage rules.

## Credits

* Map data © OpenStreetMap contributors (ODbL).
* Built with Qiskit (`QAOAAnsatz`, `StatevectorEstimator`, `StatevectorSampler`), SciPy (COBYLA, HiGHS MILP) and Shapely.
* CVaR objective: Barkoutsos et al., *Improving Variational Quantum Optimization using CVaR*, Quantum 4, 256 (2020).
