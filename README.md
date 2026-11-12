# Q·Scope — Quantum Camera Placement

Ahmad's full-stack deliverable: React + Vite frontend, MapLibre/OpenFreeMap 3D map, Chart.js diagnostics, and a Python FastAPI integration server. The three supplied Huzaifa JSON files are included unchanged. No API key is required.

**Ready now:** explore saved 8/12/16-qubit results, switch QAOA/Exact/Greedy, inspect camera FOVs and placement details, compare metrics, inspect quantum charts, edit a requested map region, and export results. **To enable fresh optimization:** connect Huzaifa's synchronous pipeline through one adapter. The API never disguises a saved file as a new solver run.

## 1. Local folder structure

Extract the ZIP. Use `quantum-camera-placement/` as the repository root, or copy its **contents** into your existing repository root. Keep these directories together because both services use `data/results/`.

| Path | Purpose |
|---|---|
| `frontend/` | React application, map, controls, tables, charts, npm lockfile |
| `frontend/src/components/CityMap.jsx` | MapLibre building extrusion, markers, zones, FOVs |
| `frontend/src/components/FrustumLayer.js` | Schematic 3D mount-to-footprint surfaces and pan/tilt rays |
| `frontend/src/components/DataMap.jsx` | Clearly labelled 2D fallback when WebGL is unavailable |
| `frontend/src/api.js` | Saved-file loader and live API client |
| `backend/app/main.py` | FastAPI routes, validation and pipeline invocation |
| `backend/app/models.py` | Request/response contract; preserves extra solver fields |
| `backend/app/solver_bridge.py` | Loads Huzaifa's configured adapter |
| `backend/tests/` | API, parameter forwarding and result integrity tests |
| `data/results/` | Canonical supplied JSON files, unchanged |
| `scripts/dev.mjs` | Optional launcher for both frontend and backend |
| `docs/SOLVER_HANDOFF.md` | Exact adapter contract for Huzaifa |
| `docs/GITHUB_SETUP.md` | Copy, commit and push instructions |
| `docs/VERIFICATION.md` | Checks performed and remaining verification limits |
| `.github/workflows/checks.yml` | Frontend tests/build and backend tests on pushes/PRs |

Generated `frontend/public/saved-results/` is copied from `data/results/` automatically on `npm run dev` / `npm run build`. Edit only the canonical files; generated copies are ignored by Git. Do not move the three originals into `src/` or install Qiskit for the frontend.

## 2. Install

Requires **Python 3.11+** and **Node.js 22 LTS** (Node 20.19+ also supported). Commands assume your terminal is in the extracted repository root.

### macOS / Linux

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
```

### Windows PowerShell

```powershell
py -3 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
```

`requirements-dev.txt` includes HTTPX for tests. Use `requirements.txt` alone if tests are unnecessary. Optional `.env` templates are included; the saved-result demo works without creating `.env` files.

## 3. Run locally

From the repository root, after installing:

```bash
npm run dev
```

Open the Vite URL printed in the terminal (normally **http://localhost:5173**). The API runs at **http://127.0.0.1:8000**, and interactive API documentation at **http://127.0.0.1:8000/docs**. Stop both with Ctrl+C.

Alternatively use two terminals:

**Backend** (macOS/Linux, from root):

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --env-file .env.example --host 127.0.0.1 --port 8000
```

On Windows substitute `.\.venv\Scripts\python.exe` for `.venv/bin/python`. When configuring the real solver, copy `.env.example` to `.env`, edit it, and use `--env-file .env` instead.

**Frontend** (from root):

```bash
cd frontend
npm run dev
```

The Vite dev proxy forwards browser `/api/*` requests to the API and strips `/api`. Adjust `API_PROXY_TARGET` in `frontend/.env` if your backend uses another host/port. `VITE_API_BASE` is a browser-visible URL, never a secret.

## 4. Use the app

1. Choose an 8, 12 or 16-qubit instance. This loads the supplied recorded result.
2. Choose QAOA, Exact or Greedy. The selected IDs drive the map, wedges, summary and camera table. Zone color comes from intersection of `covered_by` and `selected`, not a cached `covered` flag.
3. Click a selected map pin or camera-table row to fly to that mount. The inspector shows height, pan (azimuth), tilt, FOV and range. Enable **All candidates** to inspect unselected placements too.
4. Use map controls for 3D buildings and schematic 3D rays. Ground FOV polygons use the exact supplied coordinates; the mount-to-footprint surfaces are illustrative and do not run visibility calculations. Azimuth is clockwise from north; positive tilt is downward from horizontal.
5. Open **Quantum diagnostics** for bitstring probabilities (green = feasible), raw convergence, qubits/depth/gates and optimal-sampling probability.
6. Expand **Map region** to enter `[west, south, east, north]`, or choose **Use map view** while the 3D map is available. The purple outline represents the next requested region; saved-result coverage remains for its original gray sector.
7. Change `p` and `λ`, then **Run live** to POST to FastAPI. Inputs do not alter recorded results. A spinner remains while the synchronous pipeline works. An API failure leaves the last successful result visible.
8. **Export result** downloads the complete active JSON, including the additional fields supplied by Huzaifa.

The app displays `solutions.qaoa.selected`, **not** `most_probable.selected`. A most probable sample can be infeasible. The Qiskit bitstrings are displayed unchanged; frontend code never derives camera IDs from bit order.

## 5. Enable the real solver

Read [docs/SOLVER_HANDOFF.md](docs/SOLVER_HANDOFF.md). Huzaifa supplies an importable adapter with this signature:

```python
def optimize(*, instance: str, bbox: list[float], p: int, lambda_: float) -> dict:
    ...  # Invoke Huzaifa's existing spatial + optimization pipeline.
```

Set `SOLVER_CALLABLE=your_package.adapter:optimize` in `backend/.env`, install that package into `backend/.venv`, then restart the backend. Keep this module importable from the backend working directory (for example, install the solver package with `pip install -e ../solver`). **No frontend changes are needed.**

`λ` is forwarded as `lambda_`; the UI initially uses the recorded coverage penalty `quantum.penalties.B_coverage`, falling back to `params.B`. The adapter must explicitly map this to the correct solver parameter; the original brief does not define its exact mathematical meaning.

Without an adapter, `POST /optimize` returns a clear **503**, while all saved-result features and GET endpoints continue working. OSMnx candidate generation, QAOA, exact/MILP/greedy implementations and solver evaluation remain Huzaifa's work.

## 6. API

| Method | Route | Behavior |
|---|---|---|
| GET | `/health` | API status, `solver_configured`, current mode |
| GET | `/instances` | Available instance IDs and qubit counts |
| GET | `/results/sector_8` | Complete saved JSON (also `sector_12`, `sector_16`) |
| POST | `/optimize` | Validate input, call configured pipeline, validate response |
| GET | `/docs` | Interactive OpenAPI documentation |
| GET | `/openapi.json` | Generated API schema |

Live request example:

```json
{
  "instance": "sector_12",
  "p": 2,
  "lambda": 2.0,
  "bbox": [-73.988, 40.751, -73.980, 40.756]
}
```

`bbox` is optional for compatibility with the original brief; omission uses the selected instance's saved bounds. Invalid bounds/parameters return 422. Unconfigured solver: 503. Busy solver: 429. Invalid solver output: 502. Unexpected pipeline failure: 500; full details stay in server logs.

The synchronous endpoint uses FastAPI's worker threadpool so other requests can still run. A per-process lock permits one active optimization at a time. Run **one Uvicorn worker** for this demo; a production job queue and persistent concurrency control are outside this deliverable. Closing the browser does not stop an already-running optimization.

## 7. Tests and build

From root:

```bash
npm --prefix frontend test
npm --prefix frontend run build
```

Backend, from `backend/`:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

Tests check all three files, camera sums and coverage, sparse IDs, polygon closure, malformed references/requests, forwarded bounds and parameters, CORS, busy/error cases and honest handling of an unconnected solver. CI repeats these checks when the folders are placed at the GitHub repository root.

## 8. Optional single-server build

For a local packaged demo served entirely by FastAPI:

1. Copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_BASE=` (empty). Build with `npm --prefix frontend run build`.
2. Copy `backend/.env.example` to `backend/.env` and set `SERVE_FRONTEND=1`.
3. From `backend/`, run `.venv/bin/python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000` (use Windows Python path where needed).
4. Open **http://127.0.0.1:8000**. API routes are `/optimize`, `/health`, etc. directly.

This app uses no client-side URL routing. For hosting behind a separate reverse proxy, either route `/api` to FastAPI with the prefix stripped or set `VITE_API_BASE` to its accessible API URL before building and configure `CORS_ORIGINS` accordingly. It is a local research demo; add authentication and deployment-specific request limits before exposing expensive solver runs publicly.

## 9. Map requirements and troubleshooting

- The real city map needs Internet access to `tiles.openfreemap.org` (style/vector tiles/glyphs/sprites) and a browser with WebGL2 / hardware acceleration. No map access token is needed. Font download is optional; local system fonts are the fallback.
- The `building` source is discovered from the Liberty style; extrusion height is read from `render_height`. Missing OSM height values render at zero, never an invented height.
- Without WebGL, a labelled 2D data view renders the supplied camera positions, FOV polygons and coverage zones. It is not a city basemap. A table and diagnostics remain usable.
- **API offline:** start the backend and check its terminal. **503 on Run live:** connect `SOLVER_CALLABLE`; this is expected until the solver is supplied. **502:** check the adapter output against the contract. **422:** check bounds, `p` and positive `lambda`.
- If a port is busy, stop the other process, or change the API port and proxy target together. Vite can choose another free port; add that browser origin to `CORS_ORIGINS` when directly accessing FastAPI cross-origin.
- If you replace a JSON file, restart the dev server or rebuild the frontend to refresh its generated public copy.

Technical references: [MapLibre 3D buildings](https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/), [FastAPI request models](https://fastapi.tiangolo.com/tutorial/body/), [FastAPI synchronous endpoints](https://fastapi.tiangolo.com/async/).
