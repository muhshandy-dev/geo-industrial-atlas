# Metode

## 1. Spatial join titik ke kab/kota

- Predikat `intersects`: titik di dalam **atau tepat di garis batas** dianggap masuk. Bila cocok dengan
  lebih dari satu poligon (garis bersama, sudut), dipilih `kab_id` terkecil. Aturan sama di kedua mesin.
- Mesin 1: `geopandas.sjoin` (GEOS, STRtree). Mesin 2: DuckDB spatial `ST_Intersects` dalam SQL join.
- Diuji pada 11 kasus jawaban-diketahui (`tests/test_join_fixture.py`) dan dibandingkan per titik pada
  data asli (89.532 titik termasuk titik representatif poligon OSM).
- Titik di luar semua poligon: kebijakan **buang** (dasar) atau **ambil kab/kota terdekat ≤ 1 km**
  (geodesik, hanya untuk titik berlabel Indonesia atau tanpa label negara).

## 2. Hierarki kab/kota → provinsi (poligon ke poligon)

Irisan luas di proyeksi sama-luas; dua ukuran dilaporkan terpisah: bagian kab/kota di luar semua
provinsi (beda garis pantai) dan bagian yang jatuh di provinsi dominan (kab/kota terbelah).

## 3. Luas dan jarak

- Luas: Lambert Azimuthal Equal Area (lat 0 -2, lon 0 118), diverifikasi terhadap luas geodesik pyproj
  (selisih maks 0,0018%). Web Mercator meleset sampai 4,2% (ditampilkan sebagai peringatan).
- Jarak: geodesik WGS84 (pyproj Geod). Kandidat terdekat dari KD-tree pada vektor satuan (k = 8), lalu
  jarak elipsoid; bila kandidat ke-8 belum cukup jauh (margin 1%), titik dihitung ulang brute force.
  Sampel 300 titik dibandingkan brute force penuh: selisih 0 m.
- **Penyimpangan dari kriteria awal (K6)**: kriteria menulis "haversine vs Geod ≤ 0,5%". Diukur, haversine
  (bola) meleset sampai 0,56% di dekat khatulistiwa arah utara-selatan, jadi **gagal**. Pipeline diganti
  memakai jarak elipsoid langsung; kesalahan bola dilaporkan, bukan disembunyikan.

## 4. Coverage

- Layanan: porsi titik industri dengan jarak ≤ R km ke fasilitas terdekat, nasional dan per kab/kota.
- Data: kab/kota tanpa titik per lapisan, kelengkapan alamat, sebaran skor keyakinan, campuran sumber.
- Antar sumber: korelasi Spearman per kab/kota antara titik manufaktur Overture dan kawasan industri OSM
  (luas 0,51; jumlah 0,59), serta RS Overture (nama jelas) vs RS OSM (0,66).

## 5. Sensitivitas

Grid penuh 216 kombinasi: definisi industri (2) × ambang keyakinan 0/0,5/0,7 (3) × definisi RS
mentah/nama/OSM (3) × radius 5/10/20 km (3) × batas penuh/disederhanakan (2) × titik luar buang/≤1 km (2).

Per kombinasi: coverage nasional, peringkat kab/kota "porsi terjauh dari RS" (minimal 10 titik, pecahan
eksak), peringkat kepadatan; Kendall tau dan irisan 10 besar terhadap skenario dasar. Analisis satu-faktor
mengukur perubahan coverage bila hanya satu asumsi diubah. Sebuah pernyataan diberi label **kokoh** hanya
bila lolos di semua 216 kombinasi.

## 6. Paritas browser

`web/src/lib/scenario.ts` mencerminkan `scenario.py` dan hanya memakai nilai yang dipublikasi (jarak
dibulatkan ke meter, keyakinan permil, luas 3 desimal). Tes `web/tests/parity.test.ts` memastikan n,
n_cov, coverage, dan 10 besar sama persis untuk 216 kombinasi.
