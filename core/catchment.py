"""Where clients come from and where a new branch would help most (sample data).

The same rules as sql/analysis/14_branch_site.sql, so the Power BI table and the SQL result agree (checked in tests):
  * demand      = Australian matters opened in the last 12 months, by the client's suburb;
  * underserved = a suburb more than UNDERSERVED_KM from the nearest existing office (great-circle distance, 1 decimal);
  * a candidate site wins the underserved matters within REACH_KM of it that are closer to it than to today's offices.
Distances between suburbs use the flat-earth approximation at Sydney's latitude, as the SQL does.
"""
from __future__ import annotations

import pandas as pd

from .model import km
from .ref import AS_OF, BRANCHES, SUBURBS

UNDERSERVED_KM = 10.0
REACH_KM = 10.0
KM_LAT, KM_LON = 110.57, 92.45


def suburbs() -> pd.DataFrame:
    rows = []
    for name, la, lo, pop in SUBURBS:
        d = {b["name"]: float(km(la, lo, b["lat"], b["lon"])) for b in BRANCHES}
        near = min(d, key=d.get)
        rows.append(dict(suburb=name, lat=la, lon=lo, population=pop, nearest_office=near, km_to_office=round(d[near], 1)))
    s = pd.DataFrame(rows)
    s["band"] = pd.cut(s["km_to_office"], [-1, 5, 10, 1e9], labels=["Under 5 km", "5–10 km", "Over 10 km"]).astype(str)
    return s


def demand(M, last_12_months=True) -> pd.DataFrame:
    m = M["matters"]
    m = m[m["suburb"].notna()]
    if last_12_months:
        m = m[(m["opened"] > AS_OF - pd.DateOffset(years=1)) & (m["opened"] <= AS_OF)]
    return m.groupby("suburb").agg(matters=("id", "size"), est_value=("est_value", "sum")).reset_index()


def branch_sites(M, top=10) -> pd.DataFrame:
    s = suburbs()
    d = s.merge(demand(M), on="suburb", how="inner")
    under = d[d["km_to_office"] > UNDERSERVED_KM]
    out = []
    for _, c in s.iterrows():
        k2 = ((c["lat"] - under["lat"]) * KM_LAT) ** 2 + ((c["lon"] - under["lon"]) * KM_LON) ** 2
        w = under[(k2 <= REACH_KM ** 2) & (k2 < under["km_to_office"] ** 2)]
        if w["matters"].sum() > 0:
            out.append(dict(candidate_site=c["suburb"], underserved_matters_ltm=int(w["matters"].sum()), est_value_ltm=round(float(w["est_value"].sum()), 0),
                            suburbs_covered=len(w), nearest_office=c["nearest_office"], km_to_nearest_office=c["km_to_office"]))
    r = pd.DataFrame(out).sort_values(["underserved_matters_ltm", "est_value_ltm", "candidate_site"], ascending=[False, False, True])
    r["site_rank"] = r[["underserved_matters_ltm", "est_value_ltm"]].apply(tuple, axis=1).rank(method="min", ascending=False).astype(int)
    return r.head(top).reset_index(drop=True)


def headline(M) -> dict:
    """The numbers the map captions quote."""
    s = suburbs().merge(demand(M), on="suburb", how="left").fillna({"matters": 0})
    total = int(s["matters"].sum())
    far = int(s.loc[s["km_to_office"] > UNDERSERVED_KM, "matters"].sum())
    top = branch_sites(M).iloc[0]
    return dict(total=total, far=far, share_far=far / total, site=top["candidate_site"], site_matters=int(top["underserved_matters_ltm"]),
                site_value=float(top["est_value_ltm"]))
