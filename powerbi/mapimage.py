"""Static basemap images for the catchment maps.

Power BI's own map visuals depend on Bing/Azure map services that an organisation can switch off (and the Bing map is being
retired). The catchment maps are therefore scatter charts - longitude on X, latitude on Y - drawn over a plot-area image of
Western Sydney made here. The axes are fixed to the image's extent, so a bubble sits exactly where its suburb is.

Run once when the suburbs, offices or the best site change (needs Playwright):
    python -m powerbi.mapimage
It writes powerbi/assets/maps/<name>.png and extents.json; the build only copies them, so the build stays deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assets" / "maps"
KM_LAT, KM_LON = 110.57, 92.45

# plot area of each map in report pixels (visual size less title, subtitle and padding)
MAPS = {"overview": (600, 146), "catchment": (500, 506)}


def extents(name):
    from core.ref import BRANCHES, SUBURBS
    from .geo import SYDNEY_CBD
    lats = [s[1] for s in SUBURBS] + [b["lat"] for b in BRANCHES] + [SYDNEY_CBD[0]]
    lons = [s[2] for s in SUBURBS] + [b["lon"] for b in BRANCHES] + [SYDNEY_CBD[1]]
    lat0, lat1, lon0, lon1 = min(lats), max(lats), min(lons), max(lons)
    pad_lat, pad_lon = (lat1 - lat0) * 0.12, (lon1 - lon0) * 0.12
    lat0, lat1, lon0, lon1 = lat0 - pad_lat, lat1 + pad_lat, lon0 - pad_lon, lon1 + pad_lon
    w, h = MAPS[name]
    want = (w / h) * KM_LAT / KM_LON            # lon span / lat span that keeps the map undistorted
    if (lon1 - lon0) / (lat1 - lat0) < want:
        extra = want * (lat1 - lat0) - (lon1 - lon0)
        lon0, lon1 = lon0 - extra / 2, lon1 + extra / 2
    else:
        extra = (lon1 - lon0) / want - (lat1 - lat0)
        lat0, lat1 = lat0 - extra / 2, lat1 + extra / 2
    return [round(lon0, 4), round(lat0, 4), round(lon1, 4), round(lat1, 4)]


def svg(name, site):
    from core.ref import BRANCHES
    from .geo import SYDNEY_CBD, SYDNEY_PLACES
    bm = json.loads((ROOT / "assets" / "basemaps.json").read_text())["sydney"]
    lon0, lat0, lon1, lat1 = extents(name)
    w, h = MAPS[name]
    W, H = w * 2, h * 2                         # draw at 2x for a crisp image
    P = lambda la, lo: ((lo - lon0) / (lon1 - lon0) * W, (lat1 - la) / (lat1 - lat0) * H)
    blon0, blat0, blon1, blat1 = bm["box"]
    sx = (blon1 - blon0) / bm["w"] / (lon1 - lon0) * W
    sy = (blat1 - blat0) / bm["h"] / (lat1 - lat0) * H
    tx, ty = (blon0 - lon0) / (lon1 - lon0) * W, (lat1 - blat1) / (lat1 - lat0) * H
    k = W / 600 if name == "overview" else W / 500
    k = max(1.6, min(2.2, k))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="#aacbe6"/>']
    wx = (blon0 - lon0) / (lon1 - lon0) * W     # inland, west of the basemap's box
    if wx > 0:
        out.append(f'<rect x="0" y="0" width="{wx + 1:.1f}" height="{H}" fill="#f2efe9"/>')
    out.append(f'<path d="{bm["path"]}" fill="#f2efe9" transform="translate({tx:.2f},{ty:.2f}) scale({sx:.5f},{sy:.5f})"/>')
    font = "font-family:Segoe UI,Arial,sans-serif"
    def label(x, y, t, size, fill, weight=400, anchor="middle", spacing=0):
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size * k:.1f}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" '
                f'letter-spacing="{spacing * k:.1f}" style="{font}" stroke="#f2efe9" stroke-width="{3 * k:.1f}" paint-order="stroke">{t}</text>')
    marks = [P(b["lat"], b["lon"]) for b in BRANCHES] + ([P(site[1], site[2])] if site else [])
    for n, la, lo, rk in SYDNEY_PLACES:
        x, y = P(la, lo)
        near = any(abs(x - mx) < 70 * k and abs(y - my) < 14 * k for mx, my in marks)   # keep office and site labels readable
        if 0 <= x <= W and 0 <= y <= H and not near:
            out.append(label(x, y, n, 8.5 if rk == 1 else 7.5, "#7a7a7a" if rk == 1 else "#9a9a9a", 600 if rk == 1 else 400, spacing=0.5 if rk == 1 else 0))
    x, y = P(*SYDNEY_CBD)
    out.append(f'<rect x="{x - 3.5 * k:.1f}" y="{y - 3.5 * k:.1f}" width="{7 * k:.1f}" height="{7 * k:.1f}" fill="#475569" transform="rotate(45 {x:.1f} {y:.1f})"/>')
    for b in BRANCHES:
        x, y = P(b["lat"], b["lon"])
        out.append(f'<rect x="{x - 5 * k:.1f}" y="{y - 5 * k:.1f}" width="{10 * k:.1f}" height="{10 * k:.1f}" rx="{2 * k:.1f}" fill="#0f172a" stroke="#fff" stroke-width="{1.5 * k:.1f}"/>')
        out.append(label(x + 9 * k, y + 4 * k, b["name"], 9, "#0f172a", 700, "start"))
    if site:
        n, la, lo = site
        x, y = P(la, lo)
        import math
        R = 9 * k
        pts = " ".join(f"{x + (R if i % 2 == 0 else R * .45) * math.cos(-math.pi / 2 + i * math.pi / 5):.1f},"
                       f"{y + (R if i % 2 == 0 else R * .45) * math.sin(-math.pi / 2 + i * math.pi / 5):.1f}" for i in range(10))
        out.append(f'<polygon points="{pts}" fill="#7c3aed" stroke="#fff" stroke-width="{1.5 * k:.1f}"/>')
        out.append(label(x + 12 * k, y - 6 * k, f"New branch? {n}", 9, "#6d28d9", 700, "start"))
    out.append(label(W - 6 * k, H - 6 * k, "Basemap: Natural Earth", 6.5, "#8a8a8a", anchor="end"))
    out.append("</svg>")
    return "\n".join(out)


def main():
    from core.model import build_model
    from core.catchment import branch_sites
    from core.ref import SUBURBS
    from playwright.sync_api import sync_playwright
    top = branch_sites(build_model()).iloc[0]["candidate_site"]
    lat, lon = next((s[1], s[2]) for s in SUBURBS if s[0] == top)
    OUT.mkdir(parents=True, exist_ok=True)
    ext = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, (w, h) in MAPS.items():
            pg = b.new_page(viewport={"width": w * 2, "height": h * 2})
            pg.set_content(f'<html><body style="margin:0">{svg(name, (top, lat, lon))}</body></html>')
            pg.screenshot(path=str(OUT / f"{name}.png"))
            ext[name] = extents(name)
        b.close()
    (OUT / "extents.json").write_text(json.dumps({"site": top, **ext}, indent=1))
    print("wrote", ", ".join(f"{n}.png" for n in MAPS), "and extents.json")


if __name__ == "__main__":
    main()
