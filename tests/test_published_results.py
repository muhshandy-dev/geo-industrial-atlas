"""Kriteria yang diperiksa pada hasil pipeline nyata (results/results.json).

Dilewati bila pipeline belum dijalankan (mis. CI tanpa data). Workflow real-data menjalankan
pipeline dulu lalu tes ini.
"""

import json
import re
from pathlib import Path

import pytest

from geo_atlas import config as C

RES = C.RESULTS / "results.json"
pytestmark = pytest.mark.skipif(not RES.exists(), reason="pipeline belum dijalankan")


@pytest.fixture(scope="module")
def r():
    return json.loads(RES.read_text())


def test_k2_engines_agree(r):
    for k in ("penuh", "sederhana"):
        e = r["checks"]["join"][k]["engine_check"]
        assert e["agreement"] >= 0.9999, e["differences"][:5]
        assert e["multi_match_geopandas"] == e["multi_match_duckdb"]


def test_k3_outside_points_reported_and_no_foreign_points_inside(r):
    j = r["checks"]["join"]["penuh"]
    assert j["n_outside_all_polygons"] > 0
    assert j["n_assigned_non_id_addr"] == 0
    assert "n_pulled_by_nearest_1km" in j


def test_k4_topology(r):
    t = r["checks"]["topology"]["penuh"]
    assert t["n_invalid_after_fix"] == 0
    assert t["overlap_pairs_gt_0_01km2"] == 0
    assert "gap_total_km2" in t and "below_99pct" in r["checks"]["nesting"]


def test_k5_address_agreement(r):
    a = r["checks"]["address"]
    assert a["n_region_recognized"] > 1000
    assert a["agreement"] >= 0.9


def test_k6_distance_and_area(r):
    assert r["checks"]["distance"]["max_abs_diff_m_vs_bruteforce"] <= 1
    assert r["checks"]["area"]["penuh"]["laea_max_rel_err"] <= 0.005


def test_k8_sensitivity_complete_and_robust_labels_honest(r):
    s = r["sensitivity"]
    assert s["n_scenarios"] == len(s["rows"]) == 216
    for st in r["statements"]:
        if st["id"] == "underserved_top10":
            assert st["kokoh"] == any(v == 216 for v in st["frekuensi"].values())
        if st["id"].startswith("coverage_"):
            assert st["kokoh"] == (st["rentang"][0] > 0.5)


def test_k11_publication_sizes():
    for p in C.WEB_DATA.glob("*"):
        assert p.stat().st_size < 25 * 1024 * 1024, p


FORBIDDEN = [r"\bmenyebabkan\b", r"\bakibat(nya)?\b", r"\bpenyebab\b", r"jumlah pabrik (di Indonesia )?adalah",
             r"jumlah rumah sakit (di Indonesia )?adalah", r"\bdata resmi\b"]


def test_k12_no_causal_or_official_count_claims(r):
    texts = [st["teks"] for st in r["statements"]]
    web = Path(C.ROOT / "web" / "src")
    texts += [p.read_text() for p in web.rglob("*") if p.suffix in {".tsx", ".astro", ".ts"}]
    for t in texts:
        for pat in FORBIDDEN:
            assert not re.search(pat, t, re.IGNORECASE), (pat, t[:200])
    atlas = (web / "components" / "Atlas.tsx").read_text()
    assert "bukan jumlah pabrik sebenarnya" in atlas
    assert "tidak menjelaskan sebab" in atlas
