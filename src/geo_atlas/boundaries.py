"""Lapisan batas wilayah: muat, periksa topologi, hierarki kab/kota ke provinsi, luas."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Geod

from . import config as C

GEOD = Geod(ellps="WGS84")


def load_adm2(kind: str = "penuh", raw: Path = C.RAW) -> gpd.GeoDataFrame:
    """kind: 'penuh' (resolusi asli) atau 'sederhana' (versi simplified geoBoundaries).

    kab_id adalah indeks stabil berdasarkan urutan shapeID, sama untuk kedua versi.
    """
    fname = {"penuh": "geoBoundaries-IDN-ADM2.geojson",
             "sederhana": "geoBoundaries-IDN-ADM2_simplified.geojson"}[kind]
    g = gpd.read_file(raw / fname)
    g = g.sort_values("shapeID").reset_index(drop=True)
    g["kab_id"] = np.arange(len(g), dtype=np.int32)
    g["name"] = g["shapeName"]
    g["is_admin"] = ~g["name"].isin(C.NON_ADMIN_UNITS)
    n_invalid = int((~g.is_valid).sum())
    if n_invalid:
        g["geometry"] = shapely.make_valid(g.geometry.values, method="structure", keep_collapsed=False)
    g.attrs["n_invalid_before_fix"] = n_invalid
    return g[["kab_id", "shapeID", "name", "is_admin", "geometry"]]


def load_adm1(raw: Path = C.RAW) -> gpd.GeoDataFrame:
    g = gpd.read_file(raw / "geoBoundaries-IDN-ADM1.geojson")
    g = g.sort_values("shapeISO").reset_index(drop=True)
    n_invalid = int((~g.is_valid).sum())
    if n_invalid:
        g["geometry"] = shapely.make_valid(g.geometry.values, method="structure", keep_collapsed=False)
    g.attrs["n_invalid_before_fix"] = n_invalid
    return g.rename(columns={"shapeISO": "prov_iso", "shapeName": "prov_name"})[
        ["prov_iso", "prov_name", "geometry"]]


def geodesic_area_km2(geoms) -> np.ndarray:
    return np.array([abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6 for g in geoms])


def area_check(adm2: gpd.GeoDataFrame) -> dict:
    """Luas proyeksi sama-luas vs luas geodesik (rujukan); juga contoh salah pakai Web Mercator."""
    geo = geodesic_area_km2(adm2.geometry)
    laea = adm2.to_crs(C.EQUAL_AREA_CRS).area.to_numpy() / 1e6
    merc = adm2.to_crs(3857).area.to_numpy() / 1e6
    rel_laea = np.abs(laea - geo) / geo
    rel_merc = np.abs(merc - geo) / geo
    return {
        "geodesic_total_km2": float(geo.sum()),
        "laea_max_rel_err": float(rel_laea.max()),
        "laea_median_rel_err": float(np.median(rel_laea)),
        "mercator_max_rel_err": float(rel_merc.max()),
        "mercator_median_rel_err": float(np.median(rel_merc)),
        "pass": bool(rel_laea.max() <= 0.005),
        "area_km2": geo,  # dipakai modul lain, dibuang saat publikasi
    }


def topology_report(adm2: gpd.GeoDataFrame) -> dict:
    """Tumpang tindih antar kab/kota dan celah (lubang di gabungan) dalam km2 (proyeksi sama-luas)."""
    g = adm2.to_crs(C.EQUAL_AREA_CRS)
    geoms = g.geometry.values
    tree = shapely.STRtree(geoms)
    left, right = tree.query(geoms, predicate="intersects")
    mask = left < right
    left, right = left[mask], right[mask]
    inter = shapely.intersection(geoms[left], geoms[right])
    areas = shapely.area(inter) / 1e6
    overlaps = [
        {"a": adm2["name"].iat[i], "b": adm2["name"].iat[j], "km2": round(float(a), 4)}
        for i, j, a in zip(left, right, areas) if a > 0.01
    ]
    union = shapely.union_all(geoms)
    holes = [shapely.Polygon(r) for p in shapely.get_parts(union) for r in p.interiors]
    hole_areas = np.array([h.area / 1e6 for h in holes]) if holes else np.array([])
    return {
        "n_units": int(len(adm2)),
        "n_non_admin_units": int((~adm2["is_admin"]).sum()),
        "non_admin_units": sorted(adm2.loc[~adm2["is_admin"], "name"].tolist()),
        "n_invalid_before_fix": int(adm2.attrs.get("n_invalid_before_fix", 0)),
        "n_invalid_after_fix": int((~adm2.is_valid).sum()),
        "overlap_pairs_gt_0_01km2": len(overlaps),
        "overlap_total_km2": round(float(areas.sum()), 4),
        "overlap_top": sorted(overlaps, key=lambda d: -d["km2"])[:10],
        "gap_count": int(len(holes)),
        "gap_total_km2": round(float(hole_areas.sum()), 4),
        "gap_count_gt_1km2": int((hole_areas > 1).sum()),
        "gap_largest_km2": round(float(hole_areas.max()), 4) if len(hole_areas) else 0.0,
    }


def nest_adm2_in_adm1(adm2: gpd.GeoDataFrame, adm1: gpd.GeoDataFrame) -> pd.DataFrame:
    """Spatial join poligon ke poligon: provinsi dominan tiap kab/kota berdasarkan luas irisan.

    Dua ukuran dipisah karena sumbernya berbeda (ADM2 BPS 2020, ADM1 OSM 2017):
    - share_outside: bagian kab/kota yang tidak tertutup provinsi mana pun (beda garis pantai);
    - share_in_prov: bagian dari luas yang tertutup provinsi yang jatuh di provinsi dominan
      (rendah = kab/kota terbelah dua provinsi, masalah hierarki sesungguhnya).
    Kab/kota tanpa irisan sama sekali diberi provinsi terdekat dan ditandai.
    """
    a2 = adm2.to_crs(C.EQUAL_AREA_CRS)
    a1 = adm1.to_crs(C.EQUAL_AREA_CRS)
    g1 = a1.geometry.values
    tree = shapely.STRtree(g1)
    rows = []
    for i, geom in enumerate(a2.geometry.values):
        cand = tree.query(geom, predicate="intersects")
        areas = {int(j): shapely.intersection(geom, g1[j]).area for j in cand}
        covered = sum(areas.values())
        if covered > 0:
            best = max(areas, key=areas.get)
            share_in, method = areas[best] / covered, "irisan"
        else:
            best = int(tree.query_nearest(geom)[0])
            share_in, method = 1.0, "terdekat"
        rows.append({
            "kab_id": int(a2["kab_id"].iat[i]),
            "prov_iso": a1["prov_iso"].iat[best],
            "prov_name": C.PROVINCE_NAME_ID[a1["prov_iso"].iat[best]],
            "share_in_prov": float(share_in),
            "share_outside": float(1 - covered / geom.area),
            "n_prov_touching": int(sum(1 for a in areas.values() if covered and a / covered > 0.001)),
            "method": method,
        })
    return pd.DataFrame(rows)


def nesting_summary(nest: pd.DataFrame, adm2: gpd.GeoDataFrame) -> dict:
    df = nest.merge(adm2[["kab_id", "name", "is_admin"]], on="kab_id")
    low = df[df["share_in_prov"] < 0.99].sort_values("share_in_prov")
    return {
        "min_share_in_prov": round(float(df["share_in_prov"].min()), 6),
        "median_share_in_prov": round(float(df["share_in_prov"].median()), 6),
        "n_below_99pct": int(len(low)),
        "below_99pct": [{"kab": r.name, "prov": r.prov_iso, "share": round(r.share_in_prov, 4)}
                        for r in low.itertuples()],
        "median_share_outside_adm1": round(float(df["share_outside"].median()), 6),
        "max_share_outside_adm1": round(float(df["share_outside"].max()), 6),
        "n_assigned_by_nearest": int((df["method"] == "terdekat").sum()),
        "assigned_by_nearest": df.loc[df["method"] == "terdekat", "name"].tolist(),
    }
