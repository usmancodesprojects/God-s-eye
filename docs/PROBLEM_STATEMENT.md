# God’s Eye: problem statement

**Domain:** Energy & Smart Infrastructure (Qiskit Fall Fest 2026, Domain 6)

## Motivation
Cities install street cameras on building walls and poles for public safety and traffic management. Every camera costs money to buy and mount, and it draws power for years. Planners usually place cameras intersection by intersection. That leaves **blind spots** on the streets between intersections and wastes budget and energy on **overlapping views**. Choosing a mount, an aim direction and a lens for every camera across a whole district is a weighted set-cover problem with side constraints, which is **NP-hard**.

## Intended users
* Municipal smart-infrastructure and public-safety planners.
* The street-lighting and utility departments that host and power the cameras.

## Objective
Choose camera configurations so that **every street point in the selected area is in view (100% coverage)**, with priority intersections weighted higher, while **minimising total cost**: hardware capex plus lifetime energy cost of each lens’s power draw.

## Decision variables
`x_j ∈ {0,1}`: install candidate configuration *j*, which is a wall mount (1.5 m off a facade, 8 m high) × an aim direction (36 presets, 10° apart) × a lens type.

| Lens | Field of view | Range | Cost |
|---|---|---|---|
| Wide | 100° | 65 m | 1.0 capex + 0.05 × 6 W = 1.3 |
| Tele | 50° | 125 m | 1.4 capex + 0.05 × 10 W = 1.9 |

## Constraints
1. **Coverage:** every street point (sampled every 15 m, intersections included) is seen by at least one selected camera. "Seen" means within range, inside the field of view, and with no building blocking the line of sight.
2. **One camera per mount.**
3. **Budget trade-off:** the coverage weight λ sets how much a covered point is worth relative to camera and energy cost.

## Objective function (minimised)
`H(x) = Σ_j c_j x_j + λ Σ_i w_i Π_{j∈S_i}(1 − x_j) + P Σ_mount Σ_{j<k} x_j x_k`

The coverage term is exactly 1 for an unseen point, so it maps to a higher-order Ising Hamiltonian with **one qubit per candidate and no slack qubits**.

## Measurable success criteria
* Coverage %, with a target of 100%.
* Number of cameras.
* Total cost.
* Total power (W).
* Optimality gap to the exact MILP optimum.
* Probability that QAOA samples the optimum, compared with random guessing.

## Test instances (real OpenStreetMap geometry, Midtown Manhattan)
| Instance | Street points | Candidate configurations |
|---|---|---|
| Area S · 6th Ave & 42nd St | 32 | 205 |
| Area M · Bryant Park west | 103 | 750 |
| Area L · Bryant Park sector | 230 | 1,890 |
| Intersection benchmark | 5–9 intersections | 8, 12 and 16 qubits (solved without decomposition) |
