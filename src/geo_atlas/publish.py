"""Tulis file publikasi untuk situs (web/public/data) dan ringkasan hasil (results/).

Semua file ditulis deterministik (kunci terurut, angka dibulatkan) supaya rerun menghasilkan byte
yang sama (kriteria K10).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import config as C
from . import scenario

DISPLAY_TOLERANCE_DEG = 0.004  # ~450 m, hanya untuk tampilan peta; perhitungan memakai batas asli


def _clean(o, nd=6):
    if isinstance(o, dict):
        return {str(k): _clean(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v, nd) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, nd)
    return o


def dump(obj, path: Path, nd=6) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(_clean(obj, nd), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(txt + "\n", encoding="utf-8")
    return hashlib.sha256(txt.encode()).hexdigest()


def display_geometry(adm2: gpd.GeoDataFrame) -> np.ndarray:
    geoms = shapely.coverage_simplify(adm2.geometry.values, DISPLAY_TOLERANCE_DEG, simplify_boundary=True)
    geoms = shapely.set_precision(geoms, 1e-4)
    return shapely.make_valid(geoms)


def _feature_collection(geoms, props: list[dict]) -> dict:
    feats = []
    for g, p in zip(geoms, props):
        if g is None or g.is_empty:
            continue
        feats.append({"type": "Feature", "properties": p,
                      "geometry": json.loads(shapely.to_geojson(g))})
    return {"type": "FeatureCollection", "features": feats}


def influence(rows: list[dict]) -> list[dict]:
    """Analisis satu-faktor: rata-rata dan maksimum perubahan coverage nasional (poin persen) saat
    hanya satu asumsi diubah, dihitung di semua kombinasi asumsi lain."""
    df = pd.DataFrame(rows)
    dims = ["industri", "conf", "rs", "radius", "batas", "luar"]
    out = []
    for d in dims:
        others = [x for x in dims if x != d]
        g = df.groupby(others)["share_cov"].agg(lambda s: s.max() - s.min())
        out.append({"asumsi": d, "rata_pp": float(g.mean() * 100), "maks_pp": float(g.max() * 100)})
    return sorted(out, key=lambda r: -r["rata_pp"])


LABEL = {"radius": "radius", "rs": "definisi rumah sakit", "conf": "ambang skor keyakinan",
         "industri": "definisi industri", "batas": "versi batas wilayah", "luar": "aturan titik di luar batas"}


def _id(x: float, d: int = 1) -> str:
    """Format angka gaya Indonesia: koma desimal."""
    return f"{x:.{d}f}".replace(".", ",")


def statements(res: dict) -> list[dict]:
    kab = res["kab"].set_index("kab_id")
    sens = res["sensitivity"]
    rows = pd.DataFrame(sens["rows"])
    n_s = sens["n_scenarios"]
    out = []
    for r in C.RADII_KM:
        sub = rows[rows["radius"] == r]
        lo, hi = float(sub["share_cov"].min()), float(sub["share_cov"].max())
        out.append({
            "id": f"coverage_{r}km",
            "teks": f"Porsi titik industri tercatat yang berjarak ≤ {r} km dari rumah sakit tercatat "
                    f"terdekat berkisar {_id(lo*100)}% sampai {_id(hi*100)}% tergantung asumsi; "
                    "di semua kombinasi tetap mayoritas.",
            "kokoh": bool(lo > 0.5),
            "uji": "minimum di semua skenario radius ini > 50%",
            "rentang": [lo, hi], "n_skenario": int(len(sub)),
        })
    dens = sens["top10_density_frequency"]
    stable = [k for k, v in dens.items() if v == n_s]
    out.append({
        "id": "density_top10",
        "teks": "Kab/kota yang selalu masuk 10 besar kepadatan titik industri tercatat (per km²) di semua "
                f"{n_s} skenario: " + ", ".join(kab.loc[int(k), "name"] for k in stable) + ".",
        "kokoh": bool(len(stable) > 0), "uji": "masuk 10 besar di 100% skenario",
        "kab_ids": [int(k) for k in stable],
    })
    under = sens["top10_underserved_frequency"]
    always = [k for k, v in under.items() if v == n_s]
    often = [(k, v) for k, v in under.items() if v / n_s >= 0.5]
    out.append({
        "id": "underserved_top10",
        "teks": ("Tidak ada kab/kota yang masuk 10 besar 'porsi titik industri jauh dari RS' di semua skenario. "
                 if not always else
                 "Kab/kota yang selalu masuk 10 besar 'porsi titik industri jauh dari RS': "
                 + ", ".join(kab.loc[int(k), "name"] for k in always) + ". ")
                + "Yang masuk di sedikitnya separuh skenario: "
                + ", ".join(f"{kab.loc[int(k), 'name']} ({v/n_s*100:.0f}%)" for k, v in often) + ".",
        "kokoh": bool(len(always) > 0), "uji": "masuk 10 besar di 100% skenario",
        "frekuensi": {str(int(k)): int(v) for k, v in under.items()},
    })
    inf = influence(sens["rows"])
    out.append({
        "id": "most_influential_assumption",
        "teks": f"Asumsi yang paling menggeser coverage nasional adalah {LABEL[inf[0]['asumsi']]} "
                f"(rata-rata {_id(inf[0]['rata_pp'])} poin persen, maksimum {_id(inf[0]['maks_pp'])}); "
                f"berikutnya {LABEL[inf[1]['asumsi']]} ({_id(inf[1]['rata_pp'])} poin persen).",
        "kokoh": None, "uji": "analisis satu-faktor", "detail": inf,
    })
    return out


def write_all(res: dict, manifest: dict, web: Path = C.WEB_DATA, results: Path = C.RESULTS) -> dict:
    kab = res["kab"]
    hashes = {}
    # 1. Batas kab/kota untuk tampilan + batas provinsi hasil dissolve kab/kota (konsisten dengan BPS).
    adm2 = res["adm2"]["penuh"]
    disp = display_geometry(adm2)
    props = [{"id": int(r.kab_id), "nm": r.name, "pv": r.prov_iso, "adm": int(r.is_admin)}
             for r in kab.itertuples()]
    hashes["kab.geojson"] = dump(_feature_collection(disp, props), web / "kab.geojson", nd=4)
    prov = gpd.GeoDataFrame({"pv": kab["prov_iso"].to_numpy()}, geometry=disp, crs=4326).dissolve("pv")
    prov_geoms = shapely.set_precision(prov.geometry.values, 1e-4)
    hashes["provinsi.geojson"] = dump(_feature_collection(
        prov_geoms, [{"pv": p} for p in prov.index]), web / "provinsi.geojson", nd=4)

    # 2. Tabel kab/kota.
    lay = res["per_kab_layers"].set_index("kab_id")
    kab_rows = []
    for r in kab.itertuples():
        row = {"id": int(r.kab_id), "nm": r.name, "pv": r.prov_iso, "pvn": r.prov_name,
               "adm": int(r.is_admin), "km2": round(float(r.area_km2), 3)}
        if r.kab_id in lay.index:
            row.update({k: lay.loc[r.kab_id, k] for k in lay.columns})
        kab_rows.append(row)
    hashes["kab.json"] = dump({"kab": kab_rows}, web / "kab.json", nd=3)

    # 3. Titik industri (tabel kolom). Ini sumber kebenaran untuk perhitungan skenario.
    pub = res["pub"]
    cols = list(pub.columns)
    hashes["points.json"] = dump({"columns": cols, "n": int(len(pub)),
                                  "data": {c: pub[c].tolist() for c in cols}}, web / "points.json", nd=5)

    # 4. Fasilitas (untuk lapisan peta).
    f = res["facilities"]
    fac = {
        "rs": {"lon": f["rs"]["lon"].round(5).tolist(), "lat": f["rs"]["lat"].round(5).tolist(),
               "conf": np.round(f["rs"]["confidence"].fillna(0) * 1000).astype(int).tolist(),
               "nama": f["rs"]["nama"].astype(int).tolist()},
        "damkar": {"lon": f["damkar"]["lon"].round(5).tolist(), "lat": f["damkar"]["lat"].round(5).tolist(),
                   "conf": np.round(f["damkar"]["confidence"].fillna(0) * 1000).astype(int).tolist()},
        "rs_osm": {"lon": f["rs_osm"]["lon"].round(5).tolist(), "lat": f["rs_osm"]["lat"].round(5).tolist()},
        "ind_osm": {"lon": f["ind_osm"]["lon"].round(5).tolist(), "lat": f["ind_osm"]["lat"].round(5).tolist(),
                    "km2": f["ind_osm"]["area_km2"].round(4).tolist()},
    }
    hashes["facilities.json"] = dump(fac, web / "facilities.json", nd=5)

    # 5. Hasil: cek, coverage, sensitivitas, pernyataan, asal data.
    sens = res["sensitivity"]
    st = statements(res)
    out = {
        "provenance": {
            "overture_release": C.OVERTURE_RELEASE, "boundaries": C.BOUNDARY_META,
            "manifest": manifest, "base_scenario": C.BASE_SCENARIO,
            "min_points_for_rank": C.MIN_POINTS_FOR_RANK,
            "licenses": {
                "geoBoundaries ADM2 (BPS, OCHA)": "CC BY 3.0 IGO",
                "geoBoundaries ADM1 (OpenStreetMap)": "ODbL 1.0",
                "Overture Maps Places": "CDLA-Permissive-2.0 (sumber per baris: " +
                                        ", ".join(res["coverage"]["licenses_places"]) + ")",
                "Overture Base land_use (OpenStreetMap)": ", ".join(res["coverage"]["licenses_osm_landuse"]),
            },
        },
        "checks": res["checks"], "coverage": res["coverage"],
        "sensitivity": {k: v for k, v in sens.items()}, "statements": st,
        "influence": influence(sens["rows"]),
        "base": {"n": res["base_res"]["n"], "n_cov": res["base_res"]["n_cov"],
                 "share_cov": res["base_res"]["share_cov"]},
    }
    hashes["results.json"] = dump(out, web / "results.json")
    dump(out, results / "results.json")
    sizes = {p.name: p.stat().st_size for p in sorted(web.glob("*")) if p.is_file()}
    dump({"sha256": hashes, "bytes": sizes}, results / "publish_manifest.json")
    return {"sha256": hashes, "bytes": sizes}
