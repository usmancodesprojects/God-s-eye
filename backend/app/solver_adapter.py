"""Adapter between the FastAPI server and the quantum pipeline in src/ (docs/SOLVER_HANDOFF.md).

Enable with SOLVER_CALLABLE=app.solver_adapter:optimize in backend/.env.

Goal: 100% camera coverage of every street in the selected area (street points every 15 m).
* bbox equal to a saved area's bounds -> re-solve that area (same street points / candidates)
* any other bbox                       -> full spatial pipeline for that region
                                          (OSM download/cache -> street points -> mounts ->
                                          line-of-sight coverage -> decomposed QAOA)
* lambda_ maps to B, the coverage weight in H(x); P (one camera per mount) is derived from B.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.geo.area_instance import AREAS, build_area_for_bbox  # noqa: E402
from src.geo.fetch_osm import OSMDownloadError  # noqa: E402
from src.solve_area import solve_area  # noqa: E402

from .solver_bridge import SolverRequestError  # noqa: E402

MAX_P = 3
BBOX_TOL = 1e-6


def optimize(*, instance: str, bbox: list, p: int, lambda_: float) -> dict:
    if not 1 <= p <= MAX_P:
        raise SolverRequestError(f"p={p} is not supported: use 1-{MAX_P} QAOA layers "
                                 f"(each sub-problem circuit gets deeper with p).")
    if lambda_ < 1.0:
        raise SolverRequestError("lambda (coverage weight) must be >= 1 so that covering a street point "
                                 "always outweighs the cost of a camera; full coverage is the goal.")
    saved = AREAS[instance]["bbox"]
    same_region = all(abs(a - b) <= BBOX_TOL for a, b in zip(bbox, saved))
    if same_region:
        result = solve_area(instance, p=p, B=float(lambda_), save=False)
    else:
        try:
            inst = build_area_for_bbox(f"{instance}_custom", list(bbox))
        except ValueError as exc:
            raise SolverRequestError(str(exc)) from None
        except OSMDownloadError:
            raise SolverRequestError(
                "OpenStreetMap data for this region could not be downloaded: the public Overpass servers are not "
                "responding right now. Try again in a few minutes, or choose a region inside an already-cached "
                "area (Midtown around Bryant Park, or Times Square 44th-48th St).") from None
        if len(inst["zones"]) > 400:
            raise SolverRequestError(f"region has {len(inst['zones'])} street points; select a smaller area "
                                     "(up to ~400 points, about 600 x 600 m) for a live run")
        result = solve_area(inst["name"], p=p, B=float(lambda_), save=False, instance=inst)
    result["params"]["requested_bbox"] = list(bbox)
    result["params"]["lambda_maps_to"] = "B_coverage"
    result["params"]["region_mode"] = "saved area" if same_region else "live spatial pipeline"
    return result
