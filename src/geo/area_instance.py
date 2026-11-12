"""Full street-area coverage instances (v2).

Instead of covering only intersections, every street in the selected area is sampled
every SPACING metres; a camera configuration covers a sample point if it is within
range, inside the field of view, and the line of sight is not blocked by a building.
"100% coverage" therefore means every sampled street point in the area is watched.

  OSM buildings + streets  ->  street sample points (intersections = priority)
                           ->  wall mounts along every facade facing a street
                           ->  configs = mount x aim (10 deg steps) x lens
                           ->  line-of-sight coverage, per-mount dominance pruning
                           ->  ray-cast field-of-view polygons (clipped at buildings)
"""
import json
import math
from collections import defaultdict

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from src.geo import build_instance as bi

SPACING = 15.0          # metres between street sample points
MOUNT_SEARCH = 30.0     # wall must be within this distance of a street point
MOUNT_DEDUP = 12.0      # minimum spacing between mounts
AIM_STEP = 10           # degrees between aim presets
RAYS = 14               # rays per field-of-view polygon

AREAS = {   # saved demo areas inside the cached Midtown OSM download: [west, south, east, north]
    "sector_8":  {"label": "Area S - 6th Ave & 42nd St", "bbox": [-73.9858, 40.7533, -73.9832, 40.7549]},
    "sector_12": {"label": "Area M - Bryant Park west", "bbox": [-73.9868, 40.7524, -73.9826, 40.7552]},
    "sector_16": {"label": "Area L - Bryant Park sector", "bbox": [-73.9876, 40.7516, -73.9812, 40.7557]},
}


def _street_points(streets, area_xy, intersections):
    pts = []
    for z in intersections:                        # intersections first (priority weights)
        if area_xy.contains(Point(z["xy"])):
            pts.append({"xy": z["xy"], "name": " & ".join(z["names"]), "weight": z["weight"],
                        "priority": z["priority"], "kind": "intersection"})
    for s in streets:
        line = LineString(s["geom"]).intersection(area_xy)
        parts = getattr(line, "geoms", [line])
        for part in parts:
            if part.is_empty or part.length < 1:
                continue
            k = max(1, int(part.length // SPACING))
            for i in range(k + 1):
                p = part.interpolate(i * part.length / k)
                xy = (p.x, p.y)
                if any(math.dist(xy, q["xy"]) < SPACING * 0.6 for q in pts):
                    continue
                pts.append({"xy": xy, "name": s["name"], "weight": 1, "priority": False, "kind": "street"})
    return pts


def build_area(name, bbox, label, raw_path=None):
    """bbox = [west, south, east, north]; the projection origin is set to the bbox centre."""
    w, s, e, n = bbox
    prev = (bi.LAT0, bi.LON0)
    bi.set_origin((s + n) / 2, (w + e) / 2)
    try:
        return _build(name, bbox, label, raw_path or bi.RAW)
    finally:
        bi.set_origin(*prev)


def _build(name, bbox, label, raw_path):
    w, s, e, n = bbox
    x0, y0 = bi.to_xy(s, w)
    x1, y1 = bi.to_xy(n, e)
    area = box(x0, y0, x1, y1)
    buildings, streets = bi.load(raw_path)
    polys = [b["poly"] for b in buildings]
    shrunk = [p.buffer(-0.4) for p in polys]
    occ = STRtree(shrunk)
    ptree = STRtree(polys)

    def blocked_at(a, b):
        """distance from a to the first building hit on segment a->b (None if clear)."""
        seg = LineString([a, b])
        best = None
        for i in occ.query(seg):
            if shrunk[i].intersects(seg):
                d = Point(a).distance(shrunk[i].intersection(seg))
                best = d if best is None else min(best, d)
        return best

    zones = _street_points(streets, area, bi.find_intersections(streets))
    if len(zones) < 2:
        raise ValueError("fewer than 2 street points in the selected region; choose an area with streets")

    # mounts: wall points of every building near each street point (both sides of the street)
    mounts = []
    for z in zones:
        zp = Point(z["xy"])
        for b in sorted(ptree.query(zp.buffer(MOUNT_SEARCH))):
            wall = nearest_points(polys[b].exterior, zp)[0]
            d = wall.distance(zp)
            if d > MOUNT_SEARCH or d < 1:
                continue
            m = (wall.x + 1.5 * (zp.x - wall.x) / d, wall.y + 1.5 * (zp.y - wall.y) / d)
            if any(math.dist(m, q["xy"]) < MOUNT_DEDUP for q in mounts):
                continue
            if blocked_at(m, z["xy"]) is not None:
                continue
            mounts.append({"xy": m, "height": min(bi.MOUNT_HEIGHT, buildings[b]["height"])})

    rmax = max(L["range_m"] for L in bi.LENSES.values())
    configs = []
    for mi, m in enumerate(mounts):
        vis = []     # (zone, distance, bearing) for visible zones within max range
        for zi, z in enumerate(zones):
            d = math.dist(m["xy"], z["xy"])
            if d <= rmax and blocked_at(m["xy"], z["xy"]) is None:
                vis.append((zi, d, bi.bearing(m["xy"], z["xy"])))
        if not vis:
            continue
        seen, mine = set(), []
        for az in range(0, 360, AIM_STEP):
            for lens, L in bi.LENSES.items():
                cov = tuple(zi for zi, d, b in vis if d <= L["range_m"] and bi.angdiff(b, az) <= L["fov_deg"] / 2)
                if cov and (lens, cov) not in seen:
                    seen.add((lens, cov))
                    mine.append({"mount": mi, "az": float(az), "lens": lens, "covers": list(cov)})
        # per-mount dominance: drop configs whose coverage is a subset of a cheaper-or-equal one
        keep = []
        for i, c in enumerate(mine):
            sc, cc = set(c["covers"]), bi.lens_cost(c["lens"])
            dom = False
            for k, o in enumerate(mine):
                if k == i:
                    continue
                so, co = set(o["covers"]), bi.lens_cost(o["lens"])
                if sc <= so and co <= cc and (sc < so or co < cc or k < i):
                    dom = True
                    break
            if not dom:
                keep.append(c)
        configs.extend(keep)

    covered_any = {z for c in configs for z in c["covers"]}
    uncoverable = [zi for zi in range(len(zones)) if zi not in covered_any]
    zones_kept = [zi for zi in range(len(zones)) if zi in covered_any]
    zid = {z: k for k, z in enumerate(zones_kept)}
    used_m = sorted({c["mount"] for c in configs})
    mid = {m: k for k, m in enumerate(used_m)}

    def fov_polygon(m, az, L):
        pts = [m]
        for k in range(RAYS + 1):
            a = math.radians(az - L["fov_deg"] / 2 + L["fov_deg"] * k / RAYS)
            end = (m[0] + L["range_m"] * math.sin(a), m[1] + L["range_m"] * math.cos(a))
            hit = blocked_at(m, end)
            r = L["range_m"] if hit is None else max(hit, 2.0)
            pts.append((m[0] + r * math.sin(a), m[1] + r * math.cos(a)))
        pts.append(m)
        return [bi.to_lonlat(*p) for p in pts]

    out_z = []
    for zi in zones_kept:
        Z = zones[zi]
        lon, lat = bi.to_lonlat(*Z["xy"])
        out_z.append({"id": zid[zi], "name": Z["name"], "kind": Z["kind"], "lon": lon, "lat": lat,
                      "x": round(Z["xy"][0], 2), "y": round(Z["xy"][1], 2),
                      "weight": Z["weight"], "priority": Z["priority"]})
    out_c = []
    for j, c in enumerate(configs):
        M, L = mounts[c["mount"]], bi.LENSES[c["lens"]]
        dmean = sum(math.dist(M["xy"], zones[z]["xy"]) for z in c["covers"]) / len(c["covers"])
        lon, lat = bi.to_lonlat(*M["xy"])
        out_c.append({
            "id": j, "mount_id": mid[c["mount"]], "lon": lon, "lat": lat,
            "x": round(M["xy"][0], 2), "y": round(M["xy"][1], 2), "height_m": M["height"],
            "azimuth_deg": c["az"], "tilt_deg": round(math.degrees(math.atan2(M["height"], max(dmean, 1.0))), 1),
            "lens": c["lens"], "fov_deg": L["fov_deg"], "range_m": L["range_m"],
            "capex": L["capex"], "power_w": L["power_w"], "cost": bi.lens_cost(c["lens"]),
            "covers": sorted(zid[z] for z in c["covers"]),
            "fov_polygon": fov_polygon(M["xy"], c["az"], L),
        })
    coverage = {str(z["id"]): [] for z in out_z}
    for c in out_c:
        for z in c["covers"]:
            coverage[str(z)].append(c["id"])
    return {
        "name": name, "kind": "area",
        "sector": {"name": label, "center": [round(bi.LON0, 7), round(bi.LAT0, 7)], "bbox": list(bbox)},
        "params": {"energy_cost_per_w": bi.ENERGY_COST_PER_W, "lenses": bi.LENSES, "mount_height_m": bi.MOUNT_HEIGHT,
                   "street_sample_spacing_m": SPACING, "aim_step_deg": AIM_STEP,
                   "street_points_total": len(zones), "street_points_unreachable": len(uncoverable)},
        "zones": out_z, "candidates": out_c, "coverage": coverage,
    }


def build_area_for_bbox(name, bbox):
    """Live API: arbitrary region -> OSM download/cache -> area instance."""
    from src.geo.fetch_osm import osm_for_bbox
    w, s, e, n = bbox
    if e - w > bi.MAX_REGION_DEG or n - s > bi.MAX_REGION_DEG:
        raise ValueError("region too large; select at most ~2 x 2 km")
    clat = (s + n) / 2
    pad_lat = bi.EDGE_PAD_M / bi.KY
    pad_lon = bi.EDGE_PAD_M / (111320.0 * math.cos(math.radians(clat)))
    raw = osm_for_bbox((s - pad_lat, w - pad_lon, n + pad_lat, e + pad_lon))
    return build_area(name, bbox, f"Custom region ({clat:.4f}, {(w + e) / 2:.4f})", raw)


if __name__ == "__main__":
    import time
    for nm, a in AREAS.items():
        t = time.perf_counter()
        inst = build_area(nm, a["bbox"], a["label"])
        (bi.OUT / f"{nm}.json").write_text(json.dumps(inst))
        degs = [len(v) for v in inst["coverage"].values()]
        print(f"{nm}: {len(inst['zones'])} street points ({inst['params']['street_points_unreachable']} unreachable), "
              f"{len(inst['candidates'])} candidates, {len({c['mount_id'] for c in inst['candidates']})} mounts, "
              f"zone degree min/median/max {min(degs)}/{sorted(degs)[len(degs)//2]}/{max(degs)}, {time.perf_counter()-t:.1f}s")
