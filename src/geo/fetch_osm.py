"""Download and cache OpenStreetMap buildings + drivable streets.

`python -m src.geo.fetch_osm` downloads the default demo sector once (needs internet).
Everything downstream reads cached JSON, so the pipeline is reproducible offline.
`osm_for_bbox()` is used by the live API when the user selects a different map region.
Data (c) OpenStreetMap contributors, ODbL.
"""
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DEFAULT_FILE = RAW / "osm_sector.json"

# Midtown Manhattan around Bryant Park: (south, west, north, east)
BBOX = (40.7510, -73.9880, 40.7560, -73.9800)
ENDPOINTS = ["https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.private.coffee/api/interpreter"]
TIMEOUT_S = 40          # per mirror; public Overpass servers are sometimes overloaded
HIGHWAYS = "^(primary|secondary|tertiary|residential|unclassified|trunk)$"


def fetch(swne):
    s, w, n, e = swne
    query = f"""
[out:json][timeout:{TIMEOUT_S}];
(
  way["building"]({s},{w},{n},{e});
  way["highway"~"{HIGHWAYS}"]({s},{w},{n},{e});
);
out body geom;
"""
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for url in ENDPOINTS:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": "qiskit-hackathon-camera-planner"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S + 5) as r:
                payload = json.load(r)
            payload["bbox"] = list(swne)
            return payload
        except Exception as exc:  # try the mirror
            last = exc
    raise OSMDownloadError(f"Overpass download failed: {last}")


def contains(outer_swne, inner_swne):
    return (outer_swne[0] <= inner_swne[0] and outer_swne[1] <= inner_swne[1]
            and outer_swne[2] >= inner_swne[2] and outer_swne[3] >= inner_swne[3])


class OSMDownloadError(RuntimeError):
    """All Overpass mirrors failed (timeout / overload)."""


def cached_bboxes():
    """(path, swne) for every cached OSM download, default sector first."""
    paths = [DEFAULT_FILE] + [p for p in sorted(RAW.glob("osm_*.json")) if p != DEFAULT_FILE]
    out = []
    for p in paths:
        if not p.exists():
            continue
        try:
            bb = json.loads(p.read_text()).get("bbox") or (BBOX if p == DEFAULT_FILE else None)
        except (OSError, ValueError):
            continue
        if bb:
            out.append((p, tuple(bb)))
    return out


def osm_for_bbox(swne):
    """Return a cached OSM file covering `swne` (any earlier download that contains it),
    downloading and caching it only if no cached file covers the region."""
    for path, bb in cached_bboxes():
        if contains(bb, swne):
            return path
    key = hashlib.sha1(json.dumps([round(v, 5) for v in swne]).encode()).hexdigest()[:12]
    path = RAW / f"osm_{key}.json"
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fetch(swne)))
    return path


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    payload = fetch(BBOX)
    DEFAULT_FILE.write_text(json.dumps(payload))
    els = payload["elements"]
    nb = sum(1 for e in els if "building" in e.get("tags", {}))
    nh = sum(1 for e in els if "highway" in e.get("tags", {}))
    print(f"saved {len(els)} ways: {nb} buildings, {nh} street ways")


if __name__ == "__main__":
    main()
