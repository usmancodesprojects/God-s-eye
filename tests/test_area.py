"""Checks for the full street-area coverage pipeline (what the web app shows)."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

from src.model import ROOT, load_problem
from src.quantum.hamiltonian import build_cost_operator
from src.solve_area import pick_candidates, reduce_zones, solve_area, subinstance

AREAS = ["sector_8", "sector_12", "sector_16"]


def _inst(name):
    return json.loads((ROOT / "data" / "instances" / f"{name}.json").read_text())


def _res(name):
    return json.loads((ROOT / "data" / "results" / f"result_{name}.json").read_text())


@pytest.mark.parametrize("name", AREAS)
def test_coverage_matrix_is_consistent_and_complete(name):
    inst = _inst(name)
    for z in inst["zones"]:
        cov = inst["coverage"][str(z["id"])]
        assert cov, f"street point {z['id']} cannot be seen by any candidate"
        assert set(cov) == {c["id"] for c in inst["candidates"] if z["id"] in c["covers"]}
    assert inst["params"]["street_points_unreachable"] == 0


@pytest.mark.parametrize("name", AREAS)
def test_saved_results_cover_every_street_point(name):
    r = _res(name)
    by_id = {c["id"]: c for c in r["candidates"]}
    for m, s in r["solutions"].items():
        sel = set(s["selected"])
        assert s["num_cameras"] == len(sel)
        assert all(any(j in sel for j in z["covered_by"]) for z in r["zones"]), f"{m} leaves a point uncovered"
        assert s["coverage_pct"] == 100.0
        assert math.isclose(sum(by_id[j]["cost"] for j in sel), s["cost"], abs_tol=1e-6)
        mounts = [by_id[j]["mount_id"] for j in sel]
        assert len(mounts) == len(set(mounts)), f"{m} puts two cameras on one mount"


@pytest.mark.parametrize("name", AREAS)
def test_exact_is_cheapest_and_qaoa_subproblems_optimal(name):
    r = _res(name)
    s = r["solutions"]
    assert all(s["exact"]["cost"] <= s[m]["cost"] + 1e-9 for m in s)
    subs = r["quantum"]["subproblems"]
    assert subs and all(sp["qubits"] <= 12 for sp in subs)
    assert r["quantum"]["decomposition"]["subproblems_solved_optimally"] == len(subs)


@pytest.mark.parametrize("name", AREAS)
def test_adjacent_cameras_never_share_a_colour(name):
    r = _res(name)
    c = {x["id"]: x for x in r["candidates"]}
    for m, s in r["solutions"].items():
        col, sel = s["colors"], s["selected"]
        assert set(col) == {str(j) for j in sel}
        for a in sel:
            for b in sel:
                if a < b and col[str(a)] == col[str(b)]:
                    pa = Polygon(c[a]["fov_polygon"]).buffer(0)
                    pb = Polygon(c[b]["fov_polygon"]).buffer(0)
                    near = math.dist((c[a]["x"], c[a]["y"]), (c[b]["x"], c[b]["y"])) < 20
                    assert not (pa.intersects(pb) or near), f"{m}: cameras {a},{b} touch but share a colour"


def test_zone_reduction_is_exact():
    """Every dropped point is implied by a kept point (covering the kept one covers it too)."""
    inst = _inst("sector_12")
    sets = [frozenset(inst["coverage"][str(z["id"])]) for z in inst["zones"]]
    keep = reduce_zones([list(s) for s in sets])
    for b in set(range(len(sets))) - set(keep):
        assert any(sets[a] <= sets[b] for a in keep)


def test_subproblem_hamiltonian_matches_objective():
    inst = _inst("sector_8")
    cands = inst["candidates"]
    covers_of = [inst["coverage"][str(z["id"])] for z in inst["zones"]]
    cand_covers = [set(c["covers"]) for c in cands]
    cost = [c["cost"] for c in cands]
    cluster = list(range(6))
    chosen = pick_candidates(cluster, covers_of, cand_covers, cost, set(range(len(cands))), set(range(len(covers_of))))
    assert 1 <= len(chosen) <= 12
    prob = load_problem(subinstance(cluster, chosen, inst))
    diag = np.real(build_cost_operator(prob).to_matrix(sparse=True).diagonal())
    assert np.allclose(diag, prob.all_energies())


def test_solve_area_end_to_end_small():
    r = solve_area("sector_8", p=1, save=False)
    for m, s in r["solutions"].items():
        assert s["coverage_pct"] == 100.0, m
    assert r["quantum"]["p"] == 1 and r["quantum"]["num_qubits"] <= 12


def test_live_adapter_rejects_unsupported_requests():
    sys.path.insert(0, str(ROOT / "backend"))
    from app.solver_adapter import optimize
    from app.solver_bridge import SolverRequestError
    bbox = _inst("sector_8")["sector"]["bbox"]
    with pytest.raises(SolverRequestError):
        optimize(instance="sector_8", bbox=bbox, p=4, lambda_=2.0)
    with pytest.raises(SolverRequestError):
        optimize(instance="sector_8", bbox=bbox, p=1, lambda_=0.5)
    with pytest.raises(SolverRequestError):      # no streets in a 5 m box
        optimize(instance="sector_8", bbox=[-73.98400, 40.75300, -73.98394, 40.75305], p=1, lambda_=2.0)


def test_osm_outage_gives_clear_message(monkeypatch):
    sys.path.insert(0, str(ROOT / "backend"))
    import app.solver_adapter as adapter
    from app.solver_bridge import SolverRequestError
    from src.geo.fetch_osm import OSMDownloadError

    def down(*_a, **_k):
        raise OSMDownloadError("all mirrors timed out")
    monkeypatch.setattr(adapter, "build_area_for_bbox", down)
    with pytest.raises(SolverRequestError, match="Overpass servers are not responding"):
        adapter.optimize(instance="sector_8", bbox=[-73.97, 40.74, -73.968, 40.742], p=1, lambda_=2.0)


def test_cached_osm_lookup_reuses_covering_download():
    from src.geo.fetch_osm import BBOX, DEFAULT_FILE, osm_for_bbox
    inner = (BBOX[0] + 0.001, BBOX[1] + 0.001, BBOX[2] - 0.001, BBOX[3] - 0.001)
    assert osm_for_bbox(inner) == DEFAULT_FILE        # no network needed
