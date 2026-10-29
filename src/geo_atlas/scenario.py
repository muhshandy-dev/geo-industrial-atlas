"""Hitung coverage per skenario dari tabel titik yang DIPUBLIKASI (nilai sudah dibulatkan).

Modul ini sengaja sederhana dan hanya memakai kolom yang juga ada di points.json, supaya
web/src/lib/scenario.ts bisa menghitung ulang dan hasilnya identik (kriteria K9).
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

from . import config as C

CONF_SCALE = 1000  # confidence dipublikasi sebagai bilangan bulat permil


def fac_column(rs: str, conf: float) -> str:
    """Kolom jarak (m) ke fasilitas terdekat. OSM tidak punya skor confidence."""
    if rs == "osm":
        return "d_rs_osm"
    return f"d_{'rs_' + rs if rs != 'damkar' else 'damkar'}_c{int(round(conf * 100)):02d}"


def kab_column(batas: str, luar: str) -> str:
    return f"kab_{'p' if batas == 'penuh' else 's'}{'t' if luar == 'terdekat_1km' else 'b'}"


def select(pts: pd.DataFrame, industri: str, conf: float, batas: str, luar: str) -> pd.DataFrame:
    m = pts["conf"] >= int(round(conf * CONF_SCALE))
    if industri == "sempit":
        m &= pts["sempit"] == 1
    kab = pts[kab_column(batas, luar)]
    m &= kab >= 0
    return pts.loc[m]


def compute(pts: pd.DataFrame, kab: pd.DataFrame, s: dict) -> dict:
    """kab: tabel kab/kota dengan kolom kab_id, is_admin, area_km2."""
    sel = select(pts, s["industri"], s["conf"], s["batas"], s["luar"])
    kcol = kab_column(s["batas"], s["luar"])
    dist = sel[fac_column(s["rs"], s["conf"])].to_numpy()
    covered = dist <= s["radius"] * 1000
    n = len(sel)
    per = pd.DataFrame({"kab_id": sel[kcol].to_numpy(), "cov": covered.astype(int)})
    g = per.groupby("kab_id")["cov"].agg(["size", "sum"])
    g = g.reindex(kab["kab_id"], fill_value=0)
    out_kab = pd.DataFrame({
        "kab_id": kab["kab_id"].to_numpy(),
        "n": g["size"].to_numpy().astype(int),
        "n_cov": g["sum"].to_numpy().astype(int),
    })
    out_kab["n_uncov"] = out_kab["n"] - out_kab["n_cov"]
    return {"n": int(n), "n_cov": int(covered.sum()),
            "share_cov": (int(covered.sum()) / n) if n else None, "kab": out_kab}


def rank_underserved(kab_res: pd.DataFrame, kab: pd.DataFrame) -> list[int]:
    """Urutan kab/kota (n >= MIN) menurut porsi titik industri di luar radius, terbesar dulu.

    Seri: n_uncov lebih besar dulu, lalu kab_id. Hanya unit administratif.
    """
    df = kab_res.merge(kab[["kab_id", "is_admin"]], on="kab_id")
    df = df[(df["n"] >= C.MIN_POINTS_FOR_RANK) & df["is_admin"]].copy()
    # Pecahan eksak (tanpa floating point) supaya urutan sama persis dengan versi JS.
    rows = sorted(zip(df["n_uncov"], df["n"], df["kab_id"]),
                  key=lambda r: (-Fraction(int(r[0]), int(r[1])), -int(r[0]), int(r[2])))
    return [int(r[2]) for r in rows]


def rank_density(kab_res: pd.DataFrame, kab: pd.DataFrame) -> list[int]:
    df = kab_res.merge(kab[["kab_id", "is_admin", "area_km2"]], on="kab_id")
    df = df[df["is_admin"] & (df["n"] > 0)].copy()
    df["dens"] = df["n"] / df["area_km2"]
    return df.sort_values(["dens", "kab_id"], ascending=[False, True])["kab_id"].astype(int).tolist()


def all_scenarios() -> list[dict]:
    keys = ["industri", "conf", "rs", "radius", "batas", "luar"]
    vals = [C.INDUSTRY_DEFS, C.CONFIDENCE_LEVELS, C.HOSPITAL_DEFS, C.RADII_KM, C.BOUNDARY_DEFS,
            C.OUTSIDE_POLICIES]
    return [dict(zip(keys, v)) for v in itertools.product(*vals)]


def scenario_key(s: dict) -> str:
    return f"{s['industri']}|{s['conf']}|{s['rs']}|{s['radius']}|{s['batas']}|{s['luar']}"


def _tau(base: list[int], other: list[int], base_scores: dict, other_scores: dict) -> float | None:
    common = sorted(set(base) & set(other))
    if len(common) < 3:
        return None
    t = kendalltau([base_scores[k] for k in common], [other_scores[k] for k in common]).statistic
    return None if np.isnan(t) else float(t)


def sensitivity(pts: pd.DataFrame, kab: pd.DataFrame) -> dict:
    base = C.BASE_SCENARIO
    base_res = compute(pts, kab, base)
    b_rank = rank_underserved(base_res["kab"], kab)
    b_dens = rank_density(base_res["kab"], kab)

    def scores(res):
        k = res["kab"]
        return {int(r.kab_id): (r.n_uncov / r.n if r.n else 0.0) for r in k.itertuples()}

    def dens_scores(res):
        k = res["kab"].merge(kab[["kab_id", "area_km2"]], on="kab_id")
        return {int(r.kab_id): r.n / r.area_km2 for r in k.itertuples()}

    b_sc, b_dsc = scores(base_res), dens_scores(base_res)
    rows = []
    top10_count: dict[int, int] = {}
    dens_top10_count: dict[int, int] = {}
    for s in all_scenarios():
        r = compute(pts, kab, s)
        rk, dk = rank_underserved(r["kab"], kab), rank_density(r["kab"], kab)
        for k in rk[:10]:
            top10_count[k] = top10_count.get(k, 0) + 1
        for k in dk[:10]:
            dens_top10_count[k] = dens_top10_count.get(k, 0) + 1
        rows.append({
            "key": scenario_key(s), **s,
            "n": r["n"], "n_cov": r["n_cov"], "share_cov": r["share_cov"],
            "n_ranked": len(rk),
            "tau_underserved": _tau(b_rank, rk, b_sc, scores(r)),
            "top10_overlap_underserved": len(set(rk[:10]) & set(b_rank[:10])) / 10,
            "tau_density": _tau(b_dens, dk, b_dsc, dens_scores(r)),
            "top10_overlap_density": len(set(dk[:10]) & set(b_dens[:10])) / 10,
            "top10_underserved": rk[:10],
            "top10_density": dk[:10],
        })
    n_s = len(rows)
    return {
        "base": base, "n_scenarios": n_s, "rows": rows,
        "base_top10_underserved": b_rank[:10], "base_top10_density": b_dens[:10],
        "top10_underserved_frequency": dict(sorted(top10_count.items(), key=lambda kv: -kv[1])),
        "top10_density_frequency": dict(sorted(dens_top10_count.items(), key=lambda kv: -kv[1])),
    }
