> **Status (integrated):** the adapter is connected via `backend/app/solver_adapter.py` (`SOLVER_CALLABLE=app.solver_adapter:optimize`). It solves 100% street-area coverage with decomposed QAOA (`src/solve_area.py`). This document is kept as the original integration contract.

# Huzaifa → Ahmad integration handoff

The frontend and FastAPI server are complete. This document defines the only remaining connection to Huzaifa's solver. Do not rewrite the UI or duplicate quantum/classical algorithms in the API layer.

## Required adapter

Provide a synchronous, importable function:

```python
def optimize(*, instance: str, bbox: list[float], p: int, lambda_: float) -> dict:
    """Run spatial input, optimization and evaluation; return the result JSON."""
    # Call your actual pipeline here. These are boundary arguments, not assumed
    # names for your internal functions. Convert them in this adapter as needed.
    raise NotImplementedError("Replace this body with the real pipeline call")
```

The code above is a contract example, not an included working solver. Install the real package into the backend virtual environment. Example layout: place your independently maintained `solver/` package beside `backend/` and `frontend/`, then install it with `backend/.venv/bin/python -m pip install -e solver` if it has a `pyproject.toml`. An alternative is an importable `backend/huzaifa_adapter.py`, exposing `optimize`, that delegates to your installed pipeline.

Set `SOLVER_CALLABLE=huzaifa_adapter:optimize` (or your actual module path) in `backend/.env`, then restart the server with `--env-file .env` or `npm run dev`. Invalid module/function configuration fails at API startup; the server will not pretend the adapter is connected.

## Argument meanings

| Argument | Incoming value | Adapter responsibility |
|---|---|---|
| `instance` | `sector_8`, `sector_12`, `sector_16` | Choose the configured 8/12/16-qubit setup |
| `bbox` | `[west, south, east, north]` in WGS84 degrees | Pass to actual spatial extraction/candidate generation; do not silently ignore edits |
| `p` | Integer 1–20 | Configure QAOA layers |
| `lambda_` | Positive number | Map to the intended penalty parameter explicitly |

The UI seeds `lambda` from `quantum.penalties.B_coverage` / `params.B`, because those are the supplied penalty fields. Confirm this mapping in the adapter; the brief's `lambda` was not formally defined. The API never changes `P_mount` or other solver penalties on its own.

If a region is unsupported, raise a clear `ValueError` and record actionable details in server logs. The UI keeps the previous valid result and displays the API failure. If you require a narrower sector or qubit limit, enforce it in the adapter before expensive spatial work.

## Output contract

Return the same top-level shape as `data/results/result_sector_*.json`: `sector`, `zones`, `candidates`, `solutions`, `quantum`, plus optional `instance`, `params` and any additional metrics. All outputs must be JSON-serializable native Python values, not NumPy arrays/scalars, pandas frames or Qiskit result objects.

- `candidates[].id` must be unique. `zones[].covered_by` and each solution's `selected` contain these **IDs**, not array indexes. Do not assume IDs are contiguous.
- Each candidate needs the documented mount, lon/lat, height, azimuth, tilt, FOV, range, cost, power and a polygon of at least three `[lon, lat]` positions. Rings may be open or closed; UI closes a copy for GeoJSON.
- `solutions` must contain `qaoa`, `exact`, `greedy`, each with `selected`, `num_cameras`, `coverage_pct`, `cost`, `power_w`, `runtime_s`. `approx_ratio` is optional. Other methods such as `milp` are preserved and exported but are not additional method-toggle options.
- `quantum` needs `num_qubits`, `p`, `depth`, `two_qubit_gates`, `top_bitstrings`, `convergence`, `p_optimal`, `p_optimal_random`. Bitstring entries need `bits`, `prob` in [0,1], `energy`, `feasible`.
- `sector.bbox` is the **actual result extent**; return accurate coordinates for the computed sector. The UI adopts returned geometry only after a successful response.
- Keep each summary consistent with its selected cameras and zone coverage. The frontend uses the supplied summary metrics and calculates per-zone color from membership.
- `solutions.qaoa.selected` is the chosen result. `most_probable` remains a separate diagnostic. The API/UI never substitutes one for the other or infers selections from displayed bitstrings.
- Report costs in the solver's units. Current files use lens/power-adjusted costs; no currency symbol is added.
- Keep bit ordering exactly as your solver returns it. Candidate-to-bit order is not inferred by the UI.
- Extra fields, including `gate_counts`, `most_probable`, `milp`, `amplification`, lens/coverage metadata and additional diagnostics, survive API validation and export.

## Quick integration check

1. Call `GET /health`: expect `solver_configured: true`.
2. POST a request using the example in README; verify the adapter receives all four arguments.
3. Return an actual result. Check that the displayed instance, chart qubit count, geometry, selected IDs and summaries match it.
4. Change bounds and `p`/`lambda`; verify they affect the pipeline rather than replaying a saved file.
5. Check malformed requests (422), adapter errors (500/502) and concurrent runs (429).

One optimization is permitted per API process. Use one worker for the demo. Solver-specific resource limits, cancellation and long-running job queues belong in the pipeline/deployment when needed; a browser disconnect does not kill Python solver execution.
