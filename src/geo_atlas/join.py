"""Spatial join titik ke kab/kota dengan dua mesin independen: GeoPandas (GEOS) dan DuckDB spatial.

Aturan titik di batas: titik dianggap masuk poligon bila berada di dalam ATAU tepat di garis batas
(predikat `intersects`). Bila satu titik cocok dengan lebih dari satu poligon (titik tepat di garis
bersama), dipilih kab_id terkecil. Aturan yang sama dipakai di kedua mesin.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Geod, Transformer

from . import config as C
from .fetch import connect

UNASSIGNED = -1
GEOD = Geod(ellps="WGS84")


def points_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)


def join_geopandas(points: gpd.GeoDataFrame, polys: gpd.GeoDataFrame) -> np.ndarray:
    """kab_id per titik (atau -1). Mengembalikan juga jumlah kecocokan ganda lewat atribut."""
    j = gpd.sjoin(points[["geometry"]].reset_index(drop=True).assign(_pt=lambda d: d.index),
                  polys[["kab_id", "geometry"]], how="left", predicate="intersects")
    j["kab_id"] = j["kab_id"].fillna(UNASSIGNED).astype(np.int64)
    multi = int(j.groupby("_pt").size().gt(1).sum())
    best = j.sort_values(["_pt", "kab_id"]).groupby("_pt")["kab_id"].first()
    out = best.reindex(range(len(points))).to_numpy().astype(np.int32)
    join_geopandas.last_multi = multi
    return out


def join_duckdb(points: pd.DataFrame, polys: gpd.GeoDataFrame) -> np.ndarray:
    con = connect()
    pts = pd.DataFrame({"pt": np.arange(len(points)), "lon": points["lon"].to_numpy(),
                        "lat": points["lat"].to_numpy()})
    pol = pd.DataFrame({"kab_id": polys["kab_id"].to_numpy(),
                        "wkb": shapely.to_wkb(polys.geometry.values)})
    con.register("pts_df", pts)
    con.register("pol_df", pol)
    con.execute("CREATE TABLE pol AS SELECT kab_id, ST_GeomFromWKB(wkb) AS geom FROM pol_df")
    con.execute("CREATE TABLE pts AS SELECT pt, ST_Point(lon, lat) AS geom FROM pts_df")
    res = con.sql("""
        SELECT pts.pt, min(pol.kab_id) AS kab_id, count(*) AS n
        FROM pts JOIN pol ON ST_Intersects(pol.geom, pts.geom)
        GROUP BY pts.pt
    """).df()
    out = np.full(len(points), UNASSIGNED, dtype=np.int32)
    out[res["pt"].to_numpy()] = res["kab_id"].to_numpy()
    join_duckdb.last_multi = int((res["n"] > 1).sum())
    return out


def nearest_within(points: gpd.GeoDataFrame, polys: gpd.GeoDataFrame, idx: np.ndarray,
                   tol_m: float = C.NEAREST_TOLERANCE_M) -> tuple[np.ndarray, np.ndarray]:
    """Untuk titik idx (yang tidak masuk poligon): kab_id poligon terdekat dan jarak geodesiknya (m).

    Poligon terdekat dicari di proyeksi sama-luas, lalu jarak dihitung geodesik dari titik ke titik
    terdekat di tepi poligon itu. Kembali kab_id (-1 bila > tol) dan jarak.
    """
    if len(idx) == 0:
        return np.array([], dtype=np.int32), np.array([])
    to_ea = Transformer.from_crs(4326, C.EQUAL_AREA_CRS, always_xy=True)
    to_ll = Transformer.from_crs(C.EQUAL_AREA_CRS, 4326, always_xy=True)
    pg = polys.to_crs(C.EQUAL_AREA_CRS)
    tree = shapely.STRtree(pg.geometry.values)
    x, y = to_ea.transform(points["lon"].to_numpy()[idx], points["lat"].to_numpy()[idx])
    pts = shapely.points(x, y)
    _, nearest = tree.query_nearest(pts, return_distance=False, all_matches=False)
    kab = np.full(len(idx), UNASSIGNED, dtype=np.int32)
    dist = np.empty(len(idx))
    for k, (p, j) in enumerate(zip(pts, nearest)):
        q = shapely.ops.nearest_points(pg.geometry.values[j], p)[0]
        lon2, lat2 = to_ll.transform(q.x, q.y)
        lon1, lat1 = to_ll.transform(p.x, p.y)
        dist[k] = GEOD.inv(lon1, lat1, lon2, lat2)[2]
        if dist[k] <= tol_m:
            kab[k] = int(pg["kab_id"].iat[j])
    return kab, dist


def compare(a: np.ndarray, b: np.ndarray, points: pd.DataFrame) -> dict:
    diff = np.flatnonzero(a != b)
    return {
        "n_points": int(len(a)),
        "n_identical": int(len(a) - len(diff)),
        "agreement": float(1 - len(diff) / len(a)) if len(a) else 1.0,
        "differences": [
            {"id": str(points["id"].iat[i]) if "id" in points else int(i),
             "lon": float(points["lon"].iat[i]), "lat": float(points["lat"].iat[i]),
             "geopandas": int(a[i]), "duckdb": int(b[i])}
            for i in diff[:50]
        ],
    }


import shapely.ops  # noqa: E402  (dipakai di nearest_within)
