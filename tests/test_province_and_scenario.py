import pandas as pd
import pytest

from geo_atlas import config as C
from geo_atlas import scenario


@pytest.mark.parametrize("raw,iso", [
    ("JB", "ID-JB"), ("ID-JK", "ID-JK"), ("Jawa Barat", "ID-JB"), ("West Java", "ID-JB"),
    ("DKI Jakarta", "ID-JK"), ("Daerah Istimewa Yogyakarta", "ID-YO"), ("Provinsi Bali", "ID-BA"),
    ("Papua Selatan", "ID-PA"), ("Papua Barat Daya", "ID-PB"), ("", None), (None, None),
    (float("nan"), None), ("Indonesia", None), ("XX", None),
])
def test_normalize_province(raw, iso):
    assert C.normalize_province(raw) == iso


def test_all_34_provinces_have_indonesian_names():
    assert set(C.PROVINCE_NAME_ID) == C.ISO_CODES and len(C.ISO_CODES) == 34


def test_grid_is_complete_and_unique():
    rows = scenario.all_scenarios()
    assert len(rows) == 2 * 3 * 3 * 3 * 2 * 2 == 216
    assert len({scenario.scenario_key(s) for s in rows}) == 216
    assert C.BASE_SCENARIO in rows


def _toy():
    pts = pd.DataFrame({
        "sempit": [1, 1, 0, 1, 1], "conf": [900, 400, 900, 800, 800],
        "kab_pb": [0, 0, 0, 1, -1], "kab_pt": [0, 0, 0, 1, 1], "kab_sb": [0, 0, 0, 1, -1], "kab_st": [0, 0, 0, 1, 1],
        "d_rs_nama_c50": [1000, 30000, 2000, 15000, 500],
    })
    pts["d_rs_nama_c00"] = pts["d_rs_nama_c50"]
    kab = pd.DataFrame({"kab_id": [0, 1], "is_admin": [True, True], "area_km2": [100.0, 50.0]})
    return pts, kab


def test_compute_on_known_toy_case():
    pts, kab = _toy()
    s = {"industri": "sempit", "conf": 0.5, "rs": "nama", "radius": 10, "batas": "penuh", "luar": "buang"}
    r = scenario.compute(pts, kab, s)
    # titik 0 (1 km) dan 3 (15 km) masuk; titik 1 conf rendah, titik 2 bukan sempit, titik 4 di luar batas
    assert (r["n"], r["n_cov"]) == (2, 1)
    r2 = scenario.compute(pts, kab, {**s, "luar": "terdekat_1km"})
    assert (r2["n"], r2["n_cov"]) == (3, 2)
    r3 = scenario.compute(pts, kab, {**s, "industri": "luas", "conf": 0.0})
    assert (r3["n"], r3["n_cov"]) == (4, 2)


def test_rank_uses_exact_fractions():
    kab = pd.DataFrame({"kab_id": [0, 1, 2], "is_admin": [True, True, False], "area_km2": [1.0, 1.0, 1.0]})
    res = pd.DataFrame({"kab_id": [0, 1, 2], "n": [30, 10, 50], "n_cov": [20, 6, 0]})
    res["n_uncov"] = res["n"] - res["n_cov"]
    # 10/30 = 0,333 < 4/10 = 0,4 ; unit 2 bukan administratif
    assert scenario.rank_underserved(res, kab) == [1, 0]
