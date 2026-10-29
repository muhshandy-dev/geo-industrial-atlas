"""Jarak geodesik: tetangga terdekat di bola (KD-tree pada vektor satuan) dan verifikasi ke elipsoid."""

from __future__ import annotations

import numpy as np
from pyproj import Geod
from scipy.spatial import cKDTree

from . import config as C

GEOD = Geod(ellps="WGS84")


def unit_vectors(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    lo, la = np.radians(lon), np.radians(lat)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def haversine_m(lon1, lat1, lon2, lat2) -> np.ndarray:
    lo1, la1, lo2, la2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * C.EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# Rasio jarak elipsoid WGS84 terhadap jarak bola radius rata-rata selalu di dalam +-0,6%.
# Margin 1% dipakai untuk menjamin kandidat KD-tree mencakup tetangga terdekat elipsoid.
SPHERE_MARGIN = 0.01


def geod_m(lon1, lat1, lon2, lat2) -> np.ndarray:
    return np.asarray(GEOD.inv(lon1, lat1, lon2, lat2)[2])


def nearest(src_lon, src_lat, dst_lon, dst_lat, k: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """Jarak geodesik elipsoid WGS84 (m) dan indeks fasilitas terdekat untuk tiap titik sumber.

    1. KD-tree pada vektor satuan memberi k kandidat terdekat di bola (jarak tali busur monoton
       terhadap jarak busur).
    2. Jarak elipsoid (pyproj Geod) dihitung untuk k kandidat, diambil minimum.
    3. Penjaga: bila kandidat ke-k di bola belum cukup jauh (dengan margin 1%), titik itu dihitung
       ulang dengan brute force ke semua fasilitas.
    """
    src_lon, src_lat = np.asarray(src_lon, float), np.asarray(src_lat, float)
    dst_lon, dst_lat = np.asarray(dst_lon, float), np.asarray(dst_lat, float)
    n = len(src_lon)
    if len(dst_lon) == 0:
        return np.full(n, np.inf), np.full(n, -1)
    k = min(k, len(dst_lon))
    tree = cKDTree(unit_vectors(dst_lon, dst_lat))
    _, idx = tree.query(unit_vectors(src_lon, src_lat), k=k)
    idx = idx.reshape(n, k)
    rep_lon, rep_lat = np.repeat(src_lon, k), np.repeat(src_lat, k)
    d = geod_m(rep_lon, rep_lat, dst_lon[idx.ravel()], dst_lat[idx.ravel()]).reshape(n, k)
    best = d.argmin(axis=1)
    dist = d[np.arange(n), best]
    nn = idx[np.arange(n), best]
    if k < len(dst_lon):
        kth_sphere = haversine_m(src_lon, src_lat, dst_lon[idx[:, -1]], dst_lat[idx[:, -1]])
        unsafe = np.flatnonzero(kth_sphere * (1 - SPHERE_MARGIN) <= dist * (1 + SPHERE_MARGIN))
        for i in unsafe:
            all_d = geod_m(np.full(len(dst_lon), src_lon[i]), np.full(len(dst_lat), src_lat[i]),
                           dst_lon, dst_lat)
            j = int(all_d.argmin())
            dist[i], nn[i] = all_d[j], j
        nearest.last_bruteforce = int(len(unsafe))
    else:
        nearest.last_bruteforce = 0
    return dist, nn


def brute_nearest(src_lon, src_lat, dst_lon, dst_lat) -> np.ndarray:
    """Pembanding lambat (semua pasangan, jarak elipsoid) untuk tes."""
    out = np.empty(len(src_lon))
    for i in range(len(src_lon)):
        out[i] = geod_m(np.full(len(dst_lon), src_lon[i]), np.full(len(dst_lon), src_lat[i]),
                        dst_lon, dst_lat).min()
    return out


def verify_against_ellipsoid(lon1, lat1, lon2, lat2) -> dict:
    hv = haversine_m(lon1, lat1, lon2, lat2)
    gd = GEOD.inv(lon1, lat1, lon2, lat2)[2]
    ok = gd > 1.0
    rel = np.abs(hv[ok] - gd[ok]) / gd[ok]
    # Jarak "planar derajat" (salah kaprah umum): sqrt(dlon^2+dlat^2) * 111,32 km
    planar = np.hypot(np.asarray(lon2) - lon1, np.asarray(lat2) - lat1) * 111_320
    rel_planar = np.abs(planar[ok] - gd[ok]) / gd[ok]
    return {"n_pairs": int(ok.sum()), "haversine_max_rel_err": float(rel.max()),
            "haversine_median_rel_err": float(np.median(rel)),
            "planar_degree_max_rel_err": float(rel_planar.max()),
            "planar_degree_median_rel_err": float(np.median(rel_planar)),
            "haversine_within_0_5pct": bool(rel.max() <= 0.005)}
