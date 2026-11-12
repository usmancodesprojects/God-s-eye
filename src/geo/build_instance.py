"""Turn cached OSM data into camera-placement optimisation instances.

Pipeline:
  buildings + streets  ->  zones (street intersections, priority-weighted)
                       ->  mounts (building corners facing each intersection)
                       ->  candidate configs (mount x aim direction x lens)
                       ->  2.5D line-of-sight test (Shapely)  ->  coverage sets
                       ->  small instances (N qubits) written to data/instances/

Coordinates use a local equirectangular projection (metres), accurate to
well under 1 m over this ~700 m sector.
"""
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "osm_sector.json"
OUT = ROOT / "data" / "instances"

CENTER = (40.7536, -73.9840)          # Bryant Park / 6th Ave & 42nd St
MOUNT_HEIGHT = 8.0                    # typical wall / pole mounting height (m)
LENSES = {                            # competing hardware options
    "wide": {"fov_deg": 100.0, "range_m": 65.0, "capex": 1.0, "power_w": 6.0},
    "tele": {"fov_deg": 50.0, "range_m": 125.0, "capex": 1.4, "power_w": 10.0},
}
ENERGY_COST_PER_W = 0.05              # lifetime energy cost per watt, in camera-cost units
PRIORITY_STREETS = {"West 42nd Street", "East 42nd Street", "Broadway"}
MAJOR_STREETS = {"5th Avenue", "6th Avenue", "7th Avenue", "Madison Avenue"}

KY = 110540.0
LAT0, LON0, KX = CENTER[0], CENTER[1], 0.0


def set_origin(lat, lon):
    """Set the local projection origin (metres are measured from here)."""
    global LAT0, LON0, KX
    LAT0, LON0 = lat, lon
    KX = 111320.0 * math.cos(math.radians(lat))


set_origin(*CENTER)


def to_xy(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def to_lonlat(x, y):
    return [round(LON0 + x / KX, 7), round(LAT0 + y / KY, 7)]


def parse_height(tags):
    for key, scale in (("height", 1.0), ("building:levels", 3.2)):
        v = tags.get(key)
        if v:
            m = re.match(r"[\d.]+", v)
            if m:
                return float(m.group()) * scale
    return 15.0


def bearing(p, q):
    """Compass bearing (deg, clockwise from north) from p to q."""
    return math.degrees(math.atan2(q[0] - p[0], q[1] - p[1])) % 360.0


def angdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def circ_mean(a, b):
    ra, rb = math.radians(a), math.radians(b)
    return math.degrees(math.atan2(math.sin(ra) + math.sin(rb), math.cos(ra) + math.cos(rb))) % 360.0


def wedge(p, az, fov, rng, steps=12):
    pts = [p]
    for k in range(steps + 1):
        a = math.radians(az - fov / 2 + fov * k / steps)
        pts.append((p[0] + rng * math.sin(a), p[1] + rng * math.cos(a)))
    pts.append(p)
    return pts


def lens_cost(lens):
    L = LENSES[lens]
    return round(L["capex"] + ENERGY_COST_PER_W * L["power_w"], 3)


def load(raw_path=RAW):
    d = json.loads(Path(raw_path).read_text())
    buildings, streets = [], []
    for e in d["elements"]:
        tags = e.get("tags", {})
        geom = [to_xy(g["lat"], g["lon"]) for g in e.get("geometry", [])]
        if "building" in tags and len(geom) >= 4:
            poly = Polygon(geom).buffer(0)
            if poly.area > 5 and poly.geom_type == "Polygon":
                buildings.append({"poly": poly, "height": parse_height(tags)})
        elif "highway" in tags and len(geom) >= 2:
            streets.append({"name": tags.get("name", "unnamed"), "nodes": e["nodes"], "geom": geom})
    return buildings, streets


def find_intersections(streets):
    node_names, node_xy = defaultdict(set), {}
    for s in streets:
        for nid, xy in zip(s["nodes"], s["geom"]):
            node_names[nid].add(s["name"])
            node_xy[nid] = xy
    zones = []
    for nid in sorted(node_names):
        names = node_names[nid]
        if len(names) < 2:
            continue
        xy = node_xy[nid]
        if any(math.dist(xy, z["xy"]) < 12 for z in zones):  # merge split OSM nodes
            continue
        if PRIORITY_STREETS & names:
            w, pr = 3, True
        elif MAJOR_STREETS & names:
            w, pr = 2, False
        else:
            w, pr = 1, False
        zones.append({"xy": xy, "names": sorted(names), "weight": w, "priority": pr})
    return zones


def build_universe(raw_path=RAW):
    buildings, streets = load(raw_path)
    zones = find_intersections(streets)
    polys = [b["poly"] for b in buildings]
    shrunk = [p.buffer(-0.4) for p in polys]
    occ_tree = STRtree(shrunk)
    poly_tree = STRtree(polys)

    def visible(a, b):
        seg = LineString([a, b])
        return not any(shrunk[i].intersects(seg) for i in occ_tree.query(seg))

    # Mounts: nearest wall point of each corner building around each intersection
    mounts = []
    for zi, z in enumerate(zones):
        zp = Point(z["xy"])
        for bi in sorted(poly_tree.query(zp.buffer(35))):
            wall = nearest_points(polys[bi].exterior, zp)[0]
            d = wall.distance(zp)
            if d > 35 or d < 1:
                continue
            ux, uy = (zp.x - wall.x) / d, (zp.y - wall.y) / d
            m = (wall.x + 1.5 * ux, wall.y + 1.5 * uy)          # bracket 1.5 m off the wall
            if any(math.dist(m, mm["xy"]) < 8 for mm in mounts):
                continue
            if not visible(m, z["xy"]):
                continue
            mounts.append({"xy": m, "height": min(MOUNT_HEIGHT, buildings[bi]["height"]), "home": zi})

    # Candidate configurations: aim at a visible zone, or between the home zone and it
    configs = []
    for mi, m in enumerate(mounts):
        home_b = bearing(m["xy"], zones[m["home"]]["xy"])
        aims = set()
        for z in zones:
            if math.dist(m["xy"], z["xy"]) <= 130 and visible(m["xy"], z["xy"]):
                b = bearing(m["xy"], z["xy"])
                aims.add(round(b))
                aims.add(round(circ_mean(home_b, b)))
        seen = set()
        for az in sorted(aims):
            for lens, L in LENSES.items():
                cov = tuple(zi for zi, z in enumerate(zones)
                            if math.dist(m["xy"], z["xy"]) <= L["range_m"]
                            and angdiff(bearing(m["xy"], z["xy"]), az) <= L["fov_deg"] / 2
                            and visible(m["xy"], z["xy"]))
                if cov and (lens, cov) not in seen:
                    seen.add((lens, cov))
                    configs.append({"mount": mi, "az": float(az), "lens": lens, "covers": list(cov)})

    # Drop configs dominated on the same mount (subset coverage at >= cost)
    keep = []
    for i, c in enumerate(configs):
        sc, cc = set(c["covers"]), lens_cost(c["lens"])
        dominated = False
        for k, o in enumerate(configs):
            if k == i or o["mount"] != c["mount"]:
                continue
            so, co = set(o["covers"]), lens_cost(o["lens"])
            if sc <= so and co <= cc and (sc < so or co < cc or k < i):
                dominated = True
                break
        if not dominated:
            keep.append(c)
    return zones, mounts, keep


def make_instance(name, n_zones, n_qubits, universe, max_degree=4, bbox=None,
                  sector_name="Midtown Manhattan (Bryant Park)", save=True):
    """bbox (optional) = [west, south, east, north]: only intersections inside it are targets."""
    zones, mounts, configs = universe
    pool_z = range(len(zones))
    if bbox is not None:
        w, s, e, n = bbox
        pool_z = [i for i in pool_z if w <= to_lonlat(*zones[i]["xy"])[0] <= e
                  and s <= to_lonlat(*zones[i]["xy"])[1] <= n]
    order = sorted(pool_z, key=lambda i: math.hypot(*zones[i]["xy"]))[:n_zones]
    if len(order) < 2:
        raise ValueError(f"only {len(order)} street intersection(s) found in the selected region; "
                         "choose a larger area with a street grid")
    zset = set(order)
    cands = [{**c, "covers": [z for z in c["covers"] if z in zset]} for c in configs]
    cands = [c for c in cands if c["covers"]]

    chosen, deg = [], defaultdict(int)

    def ok(c):
        return all(deg[z] < max_degree for z in c["covers"])

    def add(c):
        chosen.append(c)
        for z in c["covers"]:
            deg[z] += 1

    # 1) greedy cover so that every zone is coverable
    uncovered = set(order)
    while uncovered and len(chosen) < n_qubits:
        pool = [c for c in cands if c not in chosen and ok(c) and set(c["covers"]) & uncovered]
        if not pool:
            break
        best = max(pool, key=lambda c: (len(set(c["covers"]) & uncovered) / lens_cost(c["lens"]), len(c["covers"])))
        add(best)
        uncovered -= set(best["covers"])
    if uncovered:
        raise ValueError(f"{name}: {len(uncovered)} intersection(s) cannot be seen from any candidate mount "
                         f"within the {n_qubits}-qubit budget; try a different region")
    # 2) extras: alternatives on used mounts (real angle trade-offs) and multi-zone views
    used = {c["mount"] for c in chosen}
    rest = sorted((c for c in cands if c not in chosen),
                  key=lambda c: (-(c["mount"] in used), -len(c["covers"]), lens_cost(c["lens"]), c["mount"], c["az"]))
    for c in rest:
        if len(chosen) >= n_qubits:
            break
        if ok(c):
            add(c)
    chosen.sort(key=lambda c: (c["mount"], c["az"], c["lens"]))

    zid = {z: k for k, z in enumerate(sorted(order))}
    mid = {m: k for k, m in enumerate(sorted({c["mount"] for c in chosen}))}
    out_z = []
    for z in sorted(order):
        Z = zones[z]
        lon, lat = to_lonlat(*Z["xy"])
        out_z.append({"id": zid[z], "name": " & ".join(Z["names"]), "lon": lon, "lat": lat,
                      "x": round(Z["xy"][0], 2), "y": round(Z["xy"][1], 2),
                      "weight": Z["weight"], "priority": Z["priority"]})
    out_c = []
    for j, c in enumerate(chosen):
        M, L = mounts[c["mount"]], LENSES[c["lens"]]
        dmean = sum(math.dist(M["xy"], zones[z]["xy"]) for z in c["covers"]) / len(c["covers"])
        lon, lat = to_lonlat(*M["xy"])
        out_c.append({
            "id": j, "mount_id": mid[c["mount"]], "lon": lon, "lat": lat,
            "x": round(M["xy"][0], 2), "y": round(M["xy"][1], 2), "height_m": M["height"],
            "azimuth_deg": c["az"], "tilt_deg": round(math.degrees(math.atan2(M["height"], dmean)), 1),
            "lens": c["lens"], "fov_deg": L["fov_deg"], "range_m": L["range_m"],
            "capex": L["capex"], "power_w": L["power_w"], "cost": lens_cost(c["lens"]),
            "covers": sorted(zid[z] for z in c["covers"]),
            "fov_polygon": [to_lonlat(*p) for p in wedge(M["xy"], c["az"], L["fov_deg"], L["range_m"])],
        })
    coverage = {str(z["id"]): [c["id"] for c in out_c if z["id"] in c["covers"]] for z in out_z}
    lons = [z["lon"] for z in out_z] + [c["lon"] for c in out_c]
    lats = [z["lat"] for z in out_z] + [c["lat"] for c in out_c]
    inst = {"name": name,
            "sector": {"name": sector_name, "center": [round(LON0, 7), round(LAT0, 7)],
                       "bbox": [min(lons), min(lats), max(lons), max(lats)]},
            "params": {"energy_cost_per_w": ENERGY_COST_PER_W, "lenses": LENSES, "mount_height_m": MOUNT_HEIGHT},
            "zones": out_z, "candidates": out_c, "coverage": coverage}
    if save:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{name}.json").write_text(json.dumps(inst, indent=1))
    return inst


SIZES = [("intersections_8", 5, 8), ("intersections_12", 7, 12), ("intersections_16", 9, 16)]
ZONES_FOR_QUBITS = {nq: nz for _, nz, nq in SIZES}
MAX_REGION_DEG = 0.02          # ~2 km; keeps Overpass downloads and geometry work small
EDGE_PAD_M = 80.0              # extra OSM context around the region for mounts / occlusion


def build_for_bbox(name, bbox, n_qubits):
    """Full spatial pipeline for an arbitrary [west, south, east, north] region (live API)."""
    from src.geo.fetch_osm import osm_for_bbox

    w, s, e, n = bbox
    if e - w > MAX_REGION_DEG or n - s > MAX_REGION_DEG:
        raise ValueError(f"region too large ({(e - w) * 84:.1f} x {(n - s) * 111:.1f} km); "
                         f"select at most ~2 x 2 km")
    if n_qubits not in ZONES_FOR_QUBITS:
        raise ValueError(f"unsupported qubit count {n_qubits}")
    clat, clon = (s + n) / 2, (w + e) / 2
    pad_lat = EDGE_PAD_M / KY
    pad_lon = EDGE_PAD_M / (111320.0 * math.cos(math.radians(clat)))
    raw = osm_for_bbox((s - pad_lat, w - pad_lon, n + pad_lat, e + pad_lon))
    prev = (LAT0, LON0)
    set_origin(clat, clon)
    try:
        uni = build_universe(raw)
        return make_instance(name, ZONES_FOR_QUBITS[n_qubits], n_qubits, uni, bbox=bbox,
                             sector_name=f"Custom region ({clat:.4f}, {clon:.4f})", save=False)
    finally:
        set_origin(*prev)

if __name__ == "__main__":
    uni = build_universe()
    print(f"universe: {len(uni[0])} zones, {len(uni[1])} mounts, {len(uni[2])} configs")
    for name, nz, nq in SIZES:
        inst = make_instance(name, nz, nq, uni)
        degs = [len(v) for v in inst["coverage"].values()]
        n_m = len({c["mount_id"] for c in inst["candidates"]})
        print(f"{name}: {len(inst['zones'])} zones, {len(inst['candidates'])} qubits, {n_m} mounts, zone degrees {degs}")
