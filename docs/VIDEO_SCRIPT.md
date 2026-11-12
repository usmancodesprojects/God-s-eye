# God’s Eye: 3-minute demo script

Record the web app at http://localhost:5173 with `npm run dev` running. Keep the whole video **under 3:00**.

| Time | On screen | Say (about 430 words in total) |
|---|---|---|
| 0:00–0:20 | Hero page (Area L selected), orbit animation | “This is God’s Eye. Cities install street cameras for public safety, but every camera costs money and power for years, and manual placement leaves blind spots between intersections. Choosing a mount, a direction and a lens for every camera in a district is an NP-hard set-cover problem.” |
| 0:20–0:50 | Click **Explore the workspace**. Area L map, then toggle **Exact**, **Greedy**, **QAOA** | “We build the problem from real OpenStreetMap geometry of Midtown Manhattan. Every street is sampled every 15 metres. Every facade facing a street becomes a candidate mount with 36 aim directions and two lenses, and a camera only counts if no building blocks its line of sight. The objective is hardware plus lifetime energy cost, subject to every street point being in view and at most one camera per mount.” |
| 0:50–1:30 | **Quantum diagnostics** tab: qubits, depth, distribution, convergence, P(optimum) vs random | “We map this to qubits exactly. The ‘point is unseen’ term becomes a higher-order Pauli-Z term, so we need one qubit per camera and no slack qubits. We solve it with QAOA in Qiskit: two layers, a CVaR objective, COBYLA, and the Statevector sampler. A full district has hundreds of candidates, so we split it into sub-problems of at most 12 qubits and check every one against brute force.” |
| 1:30–2:05 | Back to **Placement**: metric cards, comparison table, click a camera row to show the inspector | “Results. On the intersection benchmark, QAOA returns the proven optimum at 8, 12 and 16 qubits and beats greedy by one camera, sampling the optimum up to 110 times more often than random guessing. For Area L, 230 street points, every method reaches 100% coverage and all 15 QAOA sub-problems hit their verified optimum. Honestly, the exact MILP needs 33 cameras against our 48. That gap comes from the decomposition: the same decomposition with an exact sub-solver needs 47.” |
| 2:05–2:35 | Select **Area S**, press **Run live** (about 5 s). Then **Map region → Use map view** on a new block, **Run live** | “Everything runs live. Here the solver re-runs in a few seconds, and on a new region the whole pipeline (map download, geometry, Hamiltonian, QAOA and validation) runs from just the map bounds. Each camera’s colour differs from its neighbours’ so overlapping views are easy to tell apart.” |
| 2:35–2:55 | README limitations section or report | “We claim no quantum advantage. These are noise-free simulations; the circuits are too deep for today’s hardware without error mitigation, and the geometry is simplified. Next we want hardware runs, an XY mixer for the mount constraint, and better decomposition to close the gap.” |
| 2:55–3:00 | Hero page | “God’s Eye: every street in view, with the fewest cameras. Thank you.” |

**Tips**
* Before recording, open each area once so the map tiles are cached.
* Use Area S for the live run, because it is the fastest.
* For the new-region demo, a block inside Times Square (44th–48th St) works offline from the cache.
