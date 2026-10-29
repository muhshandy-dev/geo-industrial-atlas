"""Lapisan titik: definisi industri, rumah sakit, pemadam (Overture) dan pembanding OSM."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import config as C


def load_places(raw: Path = C.RAW) -> pd.DataFrame:
    df = pd.read_parquet(raw / "overture_places.parquet")
    df = df.sort_values("id").reset_index(drop=True)
    name = df["name"].fillna("")
    df["ind_sempit"] = df["basic_category"].isin(C.INDUSTRY_NARROW_BASIC)
    df["ind_luas"] = df["ind_sempit"] | df["category"].isin(C.INDUSTRY_BROAD_EXTRA_PRIMARY)
    df["rs_mentah"] = df["basic_category"].isin(C.HOSPITAL_BASIC)
    df["rs_nama"] = df["rs_mentah"] & name.str.contains(C.HOSPITAL_NAME_RE)
    df["damkar"] = df["basic_category"].isin(C.FIRE_BASIC)
    df["source_main"] = df["source_datasets"].map(lambda xs: xs[0] if len(xs) else None)
    return df


def load_osm(raw: Path = C.RAW) -> gpd.GeoDataFrame:
    df = pd.read_parquet(raw / "overture_landuse_osm.parquet")
    g = gpd.GeoDataFrame(df.drop(columns="geom_wkb"),
                         geometry=shapely.from_wkb(df["geom_wkb"].to_numpy()), crs=4326)
    g = g.sort_values("id").reset_index(drop=True)
    g["kind"] = np.where(g["class"].isin(C.OSM_HOSPITAL_CLASSES), "rs_osm", "ind_osm")
    rep = shapely.point_on_surface(g.geometry.values)
    g["lon"] = shapely.get_x(rep)
    g["lat"] = shapely.get_y(rep)
    g["area_km2"] = g.to_crs(C.EQUAL_AREA_CRS).area.to_numpy() / 1e6
    return g
