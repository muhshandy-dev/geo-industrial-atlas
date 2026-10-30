"""K6: jarak geodesik benar; tetangga terdekat KD-tree sama dengan brute force."""

import numpy as np

from geo_atlas import geodesy


def test_haversine_known_distance():
    # Satu derajat lintang di bola radius rata-rata = 111,195 km
    d = geodesy.haversine_m(np.array([110.0]), np.array([-7.0]), np.array([110.0]), np.array([-6.0]))
    assert abs(d[0] - 111_195.08) < 1.0


def test_kdtree_nearest_equals_bruteforce():
    rng = np.random.default_rng(7)
    slon, slat = rng.uniform(95, 141, 300), rng.uniform(-11, 6, 300)
    dlon, dlat = rng.uniform(95, 141, 500), rng.uniform(-11, 6, 500)
    d, _ = geodesy.nearest(slon, slat, dlon, dlat)
    assert np.allclose(d, geodesy.brute_nearest(slon, slat, dlon, dlat), rtol=0, atol=1e-6)



def test_sphere_error_is_measured_not_hidden():
    """Haversine (bola) bisa meleset > 0,5% di dekat khatulistiwa arah utara-selatan.

    Karena itu jarak publikasi memakai elipsoid (Geod); tes ini menjaga bahwa angka kesalahan bola
    tetap dilaporkan dan di bawah batas teoretis 0,6%.
    """
    rng = np.random.default_rng(3)
    lon1, lat1 = rng.uniform(95, 141, 2000), rng.uniform(-11, 6, 2000)
    lon2, lat2 = lon1 + rng.uniform(-0.5, 0.5, 2000), lat1 + rng.uniform(-0.5, 0.5, 2000)
    r = geodesy.verify_against_ellipsoid(lon1, lat1, lon2, lat2)
    assert r["haversine_max_rel_err"] < 0.006
    assert r["planar_degree_max_rel_err"] > r["haversine_max_rel_err"]


def test_nearest_uses_ellipsoid_and_equals_bruteforce_on_hard_cases():
    # Banyak fasilitas hampir sama jauh (cincin), memaksa jalur penjaga brute force.
    ang = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    dlon, dlat = 117 + 0.2 * np.cos(ang), 0.0 + 0.2 * np.sin(ang)
    slon, slat = np.array([117.0, 117.001]), np.array([0.0, 0.0005])
    d, _ = geodesy.nearest(slon, slat, dlon, dlat)
    assert np.allclose(d, geodesy.brute_nearest(slon, slat, dlon, dlat), atol=1e-6)
