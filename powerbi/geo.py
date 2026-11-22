"""Locations for the matter maps: client countries and the three offices.

The Power BI map visuals geocode the country and place names themselves; latitude and longitude here are used by the
browser preview, which draws its own basemap (powerbi/assets/basemaps.json, built from Natural Earth via world-atlas).
"""
from __future__ import annotations

import json
from pathlib import Path

COUNTRY_LATLON = {
    "Australia": (-25.3, 134.5), "New Zealand": (-41.5, 172.8), "United Kingdom": (54.0, -2.5), "Japan": (36.2, 138.3),
    "United States": (39.8, -98.6), "Singapore": (1.35, 103.82), "Hong Kong": (22.32, 114.17), "India": (21.0, 78.9),
    "South Korea": (36.5, 127.9),
}
OFFICE_LATLON = {"Richmond": (-33.600, 150.752), "Camden": (-34.054, 150.696), "Liverpool": (-33.920, 150.923)}
SYDNEY_CBD = (-33.8688, 151.2093)
# faint reference places on the office map, for orientation only
SYDNEY_REF = {"Parramatta": (-33.8150, 151.0011), "Penrith": (-33.7507, 150.6877), "Campbelltown": (-34.0650, 150.8142)}

WORLD_BOX = (-170.0, -50.0, 180.0, 72.0)          # lon_min, lat_min, lon_max, lat_max
SYDNEY_BOX = (150.35, -34.30, 151.45, -33.40)


def _decode(topo, name):
    """TopoJSON object -> list of rings (lists of (lon, lat))."""
    sc, tr = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)

    def ring(idx):
        out = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(a if not out else a[1:])
        return out
    rings = []
    for g in topo["objects"][name]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        for poly in polys:
            for r in poly:
                rings.append(ring(r))
    return rings


def _path(rings, box, W, H, pad=0.3):
    lon0, lat0, lon1, lat1 = box
    ex = (lon1 - lon0) * pad
    ey = (lat1 - lat0) * pad
    out = []
    for r in rings:
        if not any(lon0 - ex <= x <= lon1 + ex and lat0 - ey <= y <= lat1 + ey for x, y in r):
            continue
        pts = []
        for x, y in r:                         # clamp far-away points to a margin around the box: keeps the shape, drops the bulk
            x = min(max(x, lon0 - ex), lon1 + ex)
            y = min(max(y, lat0 - ey), lat1 + ey)
            px = round((x - lon0) / (lon1 - lon0) * W, 1)
            py = round((lat1 - y) / (lat1 - lat0) * H, 1)
            if not pts or pts[-1] != (px, py):
                pts.append((px, py))
        if len(pts) > 2:
            out.append("M" + "L".join(f"{a},{b}" for a, b in pts) + "Z")
    return "".join(out)


def build_basemaps(atlas_dir, out):
    """Run once with the npm package world-atlas@2 unpacked in atlas_dir."""
    world = json.loads((Path(atlas_dir) / "land-110m.json").read_text())
    fine = json.loads((Path(atlas_dir) / "land-10m.json").read_text())
    maps = {"world": {"box": WORLD_BOX, "w": 1000, "h": 350, "path": _path(_decode(world, "land"), WORLD_BOX, 1000, 350, 0.02)},
            "sydney": {"box": SYDNEY_BOX, "w": 600, "h": 590, "path": _path(_decode(fine, "land"), SYDNEY_BOX, 600, 590)},
            "attribution": "Basemap: Natural Earth (public domain) via world-atlas"}
    Path(out).write_text(json.dumps(maps, separators=(",", ":")))


if __name__ == "__main__":
    import sys
    build_basemaps(sys.argv[1], Path(__file__).resolve().parent / "assets" / "basemaps.json")
