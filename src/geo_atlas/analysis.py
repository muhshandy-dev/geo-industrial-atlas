"""Pipeline utama: batas wilayah, spatial join dua mesin, coverage, sensitivitas, cek silang."""

from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from scipy.stats import spearmanr

from . import boundaries as B
from . import config as C
from . import geodesy, join, layers, scenario
from .join import UNASSIGNED


def _assign(points: pd.DataFrame, polys, allow_tol: np.ndarray) -> dict:
    """Join dua mesin + kebijakan titik luar poligon. allow_tol: titik yang boleh ditarik ke terdekat."""
    pg = join.points_gdf(points)
    g = join.join_geopandas(pg, polys)
    multi_g = join.join_geopandas.last_multi
    d = join.join_duckdb(points, polys)
    multi_d = join.join_duckdb.last_multi
    cmp = join.compare(g, d, points)
    cmp["multi_match_geopandas"], cmp["multi_match_duckdb"] = multi_g, multi_d
    out_idx = np.flatnonzero((g == UNASSIGNED) & allow_tol)
    near_kab, near_dist = join.nearest_within(pg, polys, out_idx)
    tol = g.copy()
    tol[out_idx] = near_kab
    return {"kab": g, "kab_tol": tol, "check": cmp, "outside_idx": out_idx, "outside_dist": near_dist}


def run(raw=C.RAW) -> dict:
    adm2 = {k: B.load_adm2(k, raw) for k in C.BOUNDARY_DEFS}
    adm1 = B.load_adm1(raw)
    ac = B.area_check(adm2["penuh"])
    area_km2 = ac.pop("area_km2")
    ac_simpl = B.area_check(adm2["sederhana"])
    ac_simpl.pop("area_km2")
    topo = {k: B.topology_report(v) for k, v in adm2.items()}
    nest = B.nest_adm2_in_adm1(adm2["penuh"], adm1)
    kab = adm2["penuh"][["kab_id", "shapeID", "name", "is_admin"]].copy()
    kab["area_km2"] = np.round(area_km2, 3)  # nilai yang dipublikasi = nilai yang dipakai
    kab = kab.merge(nest[["kab_id", "prov_iso", "prov_name"]], on="kab_id")

    places = layers.load_places(raw)
    osm = layers.load_osm(raw)
    # Semua titik (Overture + titik representatif poligon OSM) di-join sekaligus.
    pts = pd.concat([
        places.assign(layer="overture")[["id", "lon", "lat", "addr_country", "layer"]],
        osm.assign(layer="osm", addr_country=None)[["id", "lon", "lat", "addr_country", "layer"]],
    ], ignore_index=True)
    # Titik yang alamatnya jelas negara lain tidak boleh ditarik ke kab/kota terdekat.
    allow_tol = pts["addr_country"].isna().to_numpy() | (pts["addr_country"] == "ID").to_numpy()
    res = {k: _assign(pts, adm2[k], allow_tol) for k in C.BOUNDARY_DEFS}
    for k in C.BOUNDARY_DEFS:
        pts[f"kab_{k[0]}b"] = res[k]["kab"]
        pts[f"kab_{k[0]}t"] = res[k]["kab_tol"]

    join_report = {}
    for k in C.BOUNDARY_DEFS:
        r = res[k]
        in_id = pts["addr_country"].isin(["ID"]) | pts["addr_country"].isna()
        join_report[k] = {
            "engine_check": r["check"],
            "n_points_total": int(len(pts)),
            "n_assigned": int((r["kab"] >= 0).sum()),
            "n_outside_all_polygons": int((r["kab"] < 0).sum()),
            "outside_by_addr_country": pts.loc[r["kab"] < 0, "addr_country"].fillna("(kosong)")
                                          .value_counts().to_dict(),
            "n_outside_but_indonesian_or_unknown": int(((r["kab"] < 0) & in_id).sum()),
            "n_pulled_by_nearest_1km": int((r["kab_tol"] >= 0).sum() - (r["kab"] >= 0).sum()),
            "outside_dist_m_quantiles": (np.quantile(r["outside_dist"], [0.5, 0.9, 0.99]).round(1).tolist()
                                         if len(r["outside_dist"]) else []),
            "n_assigned_non_id_addr": int(((r["kab"] >= 0) & pts["addr_country"].notna()
                                           & (pts["addr_country"] != "ID")).sum()),
        }
    # Sensitivitas batas: titik yang pindah kab/kota antara versi penuh dan sederhana.
    both = (pts["kab_pb"] >= 0) | (pts["kab_sb"] >= 0)
    moved = both & (pts["kab_pb"] != pts["kab_sb"])
    join_report["penuh_vs_sederhana"] = {
        "n_points_in_either": int(both.sum()),
        "n_changed_kab": int(moved.sum()),
        "share_changed": float(moved.sum() / both.sum()),
        "n_lost_in_simplified": int(((pts["kab_pb"] >= 0) & (pts["kab_sb"] < 0)).sum()),
        "n_gained_in_simplified": int(((pts["kab_pb"] < 0) & (pts["kab_sb"] >= 0)).sum()),
    }

    P = places.merge(pts.loc[pts["layer"] == "overture", ["id", "kab_pb", "kab_pt", "kab_sb", "kab_st"]],
                     on="id")
    O = osm.merge(pts.loc[pts["layer"] == "osm", ["id", "kab_pb", "kab_pt", "kab_sb", "kab_st"]], on="id")
    prov_of = dict(zip(kab["kab_id"], kab["prov_iso"]))

    # K5: provinsi hasil join vs provinsi di alamat.
    a = P[P["kab_pb"] >= 0].copy()
    a["prov_join"] = a["kab_pb"].map(prov_of)
    a["prov_addr"] = a["addr_region"].map(C.normalize_province)
    has = a["prov_addr"].notna()
    agree = (a.loc[has, "prov_join"] == a.loc[has, "prov_addr"])
    by_raw = (a[has].assign(ok=agree).groupby("addr_region")["ok"].agg(["size", "mean"])
              .sort_values("size", ascending=False).head(25))
    dis = a[has & ~(a["prov_join"] == a["prov_addr"])]
    addr_report = {
        "n_assigned": int(len(a)),
        "n_with_region_text": int(a["addr_region"].fillna("").str.strip().ne("").sum()),
        "n_region_recognized": int(has.sum()),
        "agreement": float(agree.mean()) if has.any() else None,
        "by_region_text": [{"region": r, "n": int(row["size"]), "agreement": round(float(row["mean"]), 4)}
                           for r, row in by_raw.iterrows()],
        "disagreement_examples": dis[["name", "addr_region", "prov_addr", "prov_join", "lon", "lat"]]
                                 .head(15).to_dict("records"),
        "agreement_two_letter_codes": float(agree[a.loc[has, "addr_region"].str.len() == 2].mean())
            if (a.loc[has, "addr_region"].str.len() == 2).any() else None,
        "agreement_full_names": float(agree[a.loc[has, "addr_region"].str.len() > 2].mean())
            if (a.loc[has, "addr_region"].str.len() > 2).any() else None,
    }

    # Fasilitas di Indonesia (batas penuh + toleransi 1 km), tetap untuk semua skenario.
    in_id_p = P["kab_pt"] >= 0
    fac = {}
    for rs in ("mentah", "nama"):
        for c in C.CONFIDENCE_LEVELS:
            m = in_id_p & P[f"rs_{rs}"] & (np.round(P["confidence"] * 1000) >= round(c * 1000))
            fac[scenario.fac_column(rs, c)] = P.loc[m, ["lon", "lat"]]
    for c in C.CONFIDENCE_LEVELS:
        m = in_id_p & P["damkar"] & (np.round(P["confidence"] * 1000) >= round(c * 1000))
        fac[scenario.fac_column("damkar", c)] = P.loc[m, ["lon", "lat"]]
    fac["d_rs_osm"] = O.loc[(O["kab_pt"] >= 0) & (O["kind"] == "rs_osm"), ["lon", "lat"]]

    # Titik industri: definisi luas (super-set), masuk Indonesia di salah satu varian batas/kebijakan.
    I = P[P["ind_luas"] & ((P[["kab_pb", "kab_pt", "kab_sb", "kab_st"]] >= 0).any(axis=1))].copy()
    I = I.sort_values("id").reset_index(drop=True)
    pub = pd.DataFrame({
        "lon": I["lon"].round(5), "lat": I["lat"].round(5),
        "sempit": I["ind_sempit"].astype(int),
        "conf": np.round(I["confidence"].fillna(0) * scenario.CONF_SCALE).astype(int),
        "kab_pb": I["kab_pb"], "kab_pt": I["kab_pt"], "kab_sb": I["kab_sb"], "kab_st": I["kab_st"],
    })
    nn_bruteforce = {}
    for col, f in fac.items():
        d, _ = geodesy.nearest(I["lon"].to_numpy(), I["lat"].to_numpy(),
                               f["lon"].to_numpy(), f["lat"].to_numpy())
        nn_bruteforce[col] = geodesy.nearest.last_bruteforce
        pub[col] = np.round(d).astype(np.int64)
    # Verifikasi jarak: sampel dibandingkan brute force penuh.
    rng = np.random.default_rng(0)
    smp = rng.choice(len(I), size=min(300, len(I)), replace=False)
    f = fac["d_rs_nama_c50"]
    bf = geodesy.brute_nearest(I["lon"].to_numpy()[smp], I["lat"].to_numpy()[smp],
                               f["lon"].to_numpy(), f["lat"].to_numpy())
    dist_check = {
        "sample_n": int(len(smp)),
        "max_abs_diff_m_vs_bruteforce": float(np.abs(np.round(bf) - pub["d_rs_nama_c50"].to_numpy()[smp]).max()),
        "bruteforce_fallbacks": nn_bruteforce,
    }
    # Kesalahan bola vs elipsoid & planar-derajat pada pasangan titik industri -> RS terdekat.
    _, nn = geodesy.nearest(I["lon"].to_numpy(), I["lat"].to_numpy(), f["lon"].to_numpy(), f["lat"].to_numpy())
    sphere_check = geodesy.verify_against_ellipsoid(I["lon"].to_numpy(), I["lat"].to_numpy(),
                                                    f["lon"].to_numpy()[nn], f["lat"].to_numpy()[nn])

    sens = scenario.sensitivity(pub, kab)
    base_res = scenario.compute(pub, kab, C.BASE_SCENARIO)

    # Coverage data & kesesuaian antar sumber per kab/kota (unit administratif, batas penuh).
    admin = kab[kab["is_admin"]]
    def per_kab(df, col="kab_pb"):
        return df.groupby(col).size().reindex(admin["kab_id"], fill_value=0)
    conf_ok = P["confidence"] >= 0.5
    ov_ind = per_kab(P[P["ind_sempit"] & conf_ok & (P["kab_pb"] >= 0)])
    ov_rs = per_kab(P[P["rs_nama"] & conf_ok & (P["kab_pb"] >= 0)])
    ov_rs_raw = per_kab(P[P["rs_mentah"] & (P["kab_pb"] >= 0)])
    ov_fire = per_kab(P[P["damkar"] & (P["kab_pb"] >= 0)])
    osm_ind_n = per_kab(O[(O["kind"] == "ind_osm") & (O["kab_pb"] >= 0)])
    osm_ind_area = (O[(O["kind"] == "ind_osm") & (O["kab_pb"] >= 0)].groupby("kab_pb")["area_km2"].sum()
                    .reindex(admin["kab_id"], fill_value=0.0))
    osm_rs = per_kab(O[(O["kind"] == "rs_osm") & (O["kab_pb"] >= 0)])

    def sp(x, y):
        r = spearmanr(x, y)
        return {"spearman": round(float(r.statistic), 4), "p_value": float(r.pvalue), "n_kab": int(len(x))}

    raw_in = P[P["rs_mentah"] & (P["kab_pb"] >= 0)]
    nm = raw_in["name"].fillna("")
    coverage = {
        "n_admin_kab": int(len(admin)),
        "kab_zero": {
            "industri_overture_sempit_c50": int((ov_ind == 0).sum()),
            "industri_osm": int((osm_ind_n == 0).sum()),
            "rs_overture_nama_c50": int((ov_rs == 0).sum()),
            "rs_overture_mentah": int((ov_rs_raw == 0).sum()),
            "rs_osm": int((osm_rs == 0).sum()),
            "damkar_overture": int((ov_fire == 0).sum()),
        },
        "national_counts_in_indonesia": {
            "industri_sempit_semua_conf": int((P["ind_sempit"] & (P["kab_pb"] >= 0)).sum()),
            "industri_luas_semua_conf": int((P["ind_luas"] & (P["kab_pb"] >= 0)).sum()),
            "rs_mentah": int(len(raw_in)),
            "rs_nama": int((P["rs_nama"] & (P["kab_pb"] >= 0)).sum()),
            "rs_osm": int(((O["kind"] == "rs_osm") & (O["kab_pb"] >= 0)).sum()),
            "damkar": int((P["damkar"] & (P["kab_pb"] >= 0)).sum()),
            "osm_industri_poligon": int(((O["kind"] == "ind_osm") & (O["kab_pb"] >= 0)).sum()),
            "osm_industri_luas_km2": round(float(osm_ind_area.sum()), 2),
        },
        "rs_mentah_name_mix": {
            "klinik": round(float(nm.str.contains("klinik|clinic", case=False).mean()), 4),
            "puskesmas": round(float(nm.str.contains(r"puskesmas|\bPKM\b", case=False).mean()), 4),
            "dokter_bidan_praktik": round(float(nm.str.contains(r"\bdr\.|\bdrg\b|dokter|bidan|praktek|praktik", case=False).mean()), 4),
            "nama_rumah_sakit": round(float(nm.str.contains(C.HOSPITAL_NAME_RE).mean()), 4),
        },
        "cross_source": {
            "industri_overture_vs_osm_area": sp(ov_ind, osm_ind_area),
            "industri_overture_vs_osm_count": sp(ov_ind, osm_ind_n),
            "rs_overture_nama_vs_osm": sp(ov_rs, osm_rs),
        },
        "address_completeness": {
            "share_with_region_text": round(float(P.loc[P["kab_pb"] >= 0, "addr_region"].fillna("").str.strip().ne("").mean()), 4),
        },
        "confidence_quantiles": {
            k: np.quantile(P.loc[P[k] & (P["kab_pb"] >= 0), "confidence"], [0.1, 0.25, 0.5, 0.75, 0.9]).round(3).tolist()
            for k in ("ind_sempit", "rs_mentah", "rs_nama", "damkar")
        },
        "source_mix": {
            k: P.loc[P[k] & (P["kab_pb"] >= 0), "source_main"].value_counts().to_dict()
            for k in ("ind_sempit", "rs_nama", "damkar")
        },
        "licenses_places": sorted({l for ls in P["source_licenses"] for l in ls if l}),
        "licenses_osm_landuse": sorted({l for ls in O["source_licenses"] for l in ls if l}),
    }
    per_kab_layers = pd.DataFrame({
        "kab_id": admin["kab_id"].to_numpy(),
        "ov_ind": ov_ind.to_numpy(), "ov_rs": ov_rs.to_numpy(), "ov_rs_raw": ov_rs_raw.to_numpy(),
        "ov_fire": ov_fire.to_numpy(), "osm_ind_n": osm_ind_n.to_numpy(),
        "osm_ind_km2": osm_ind_area.round(3).to_numpy(), "osm_rs": osm_rs.to_numpy(),
    })

    facilities = {
        "rs": P[in_id_p & P["rs_mentah"]].assign(nama=lambda d: d["rs_nama"].astype(int)),
        "damkar": P[in_id_p & P["damkar"]],
        "rs_osm": O[(O["kab_pt"] >= 0) & (O["kind"] == "rs_osm")],
        "ind_osm": O[(O["kab_pt"] >= 0) & (O["kind"] == "ind_osm")],
    }
    return {
        "kab": kab, "adm2": adm2, "pub": pub, "industrial": I, "facilities": facilities,
        "per_kab_layers": per_kab_layers, "base_res": base_res,
        "checks": {
            "area": {"penuh": ac, "sederhana": ac_simpl}, "topology": topo,
            "nesting": B.nesting_summary(nest, adm2["penuh"]),
            "join": join_report, "address": addr_report, "distance": dist_check,
            "sphere_vs_ellipsoid": sphere_check,
        },
        "coverage": coverage, "sensitivity": sens,
    }
