"""K1: spatial join benar 100% pada kasus dengan jawaban diketahui, di kedua mesin."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, Polygon

from geo_atlas import join

# Tiga "kab/kota" buatan berdampingan di sekitar lon 110, lat -7:
#  A: persegi 110.0-110.1 dengan lubang 110.04-110.06 (lubang = wilayah C, seperti kota di dalam kabupaten)
#  B: persegi 110.1-110.2 berbagi tepi dengan A
#  C: pulau-pulau (multipoligon): lubang di A + pulau terpisah di 110.3
A = Polygon([(110.0, -7.1), (110.1, -7.1), (110.1, -7.0), (110.0, -7.0)],
            holes=[[(110.04, -7.06), (110.06, -7.06), (110.06, -7.04), (110.04, -7.04)]])
B = Polygon([(110.1, -7.1), (110.2, -7.1), (110.2, -7.0), (110.1, -7.0)])
C = MultiPolygon([
    Polygon([(110.04, -7.06), (110.06, -7.06), (110.06, -7.04), (110.04, -7.04)]),
    Polygon([(110.3, -7.1), (110.35, -7.1), (110.35, -7.05), (110.3, -7.05)]),
])
POLYS = gpd.GeoDataFrame({"kab_id": [0, 1, 2]}, geometry=[A, B, C], crs=4326)

CASES = [
    # (lon, lat, expected kab_id, keterangan)
    (110.02, -7.02, 0, "di dalam A"),
    (110.15, -7.05, 1, "di dalam B"),
    (110.05, -7.05, 2, "di dalam lubang A = wilayah C"),
    (110.32, -7.07, 2, "di pulau terpisah C"),
    (110.1, -7.05, 0, "tepat di tepi bersama A|B -> kab_id terkecil"),
    (110.1, -7.0, 0, "tepat di sudut bersama A|B"),
    (110.04, -7.05, 0, "tepat di tepi lubang A|C -> kab_id terkecil"),
    (110.2, -7.05, 1, "tepi luar B (tidak ada tetangga)"),
    (110.25, -7.05, -1, "laut antara B dan pulau C"),
    (109.0, -7.05, -1, "jauh di luar"),
    (110.06, -7.06, 0, "sudut lubang (A dan C bertemu)"),
]


@pytest.fixture(scope="module")
def pts():
    df = pd.DataFrame([(lon, lat) for lon, lat, *_ in CASES], columns=["lon", "lat"])
    df["id"] = [c[3] for c in CASES]
    return join.points_gdf(df)


def test_geopandas_matches_known_answers(pts):
    got = join.join_geopandas(pts, POLYS)
    assert got.tolist() == [c[2] for c in CASES]


def test_duckdb_matches_known_answers(pts):
    got = join.join_duckdb(pts, POLYS)
    assert got.tolist() == [c[2] for c in CASES]


def test_engines_report_same_multi_matches(pts):
    join.join_geopandas(pts, POLYS)
    join.join_duckdb(pts, POLYS)
    # tepi A|B, sudut A|B, tepi lubang A|C, sudut lubang A|C
    assert join.join_geopandas.last_multi == join.join_duckdb.last_multi == 4


def test_nearest_within_tolerance():
    # 0,005 derajat lintang di selatan tepi bawah B ~ 553 m: masuk toleransi 1 km.
    # 0,02 derajat ~ 2,2 km: tetap di luar.
    df = pd.DataFrame({"lon": [110.15, 110.15], "lat": [-7.105, -7.12]})
    p = join.points_gdf(df)
    kab, dist = join.nearest_within(p, POLYS, np.array([0, 1]))
    assert kab.tolist() == [1, -1]
    assert 540 < dist[0] < 565
    assert 2150 < dist[1] < 2250
