# Data card

## Sumber dan versi terkunci

| Berkas mentah | Asal | Kunci versi |
|---|---|---|
| geoBoundaries-IDN-ADM2.geojson | wmgeolab/geoBoundaries `releaseData/gbOpen/IDN/ADM2` (ID IDN-ADM2-22746128) | SHA-256 `947cedc0…a5602` |
| geoBoundaries-IDN-ADM2_simplified.geojson | idem, versi disederhanakan | SHA-256 `146653d4…0430c` |
| geoBoundaries-IDN-ADM1.geojson | IDN-ADM1-65028918 | SHA-256 `9a2c93ed…cbb3af` |
| overture_places.parquet | Overture `release/2026-10-21.0/theme=places/type=place` (16 file), kotak 94,5..141,5 BT, -11,5..6,5 LS; kategori manufacturer, industrial_company, commercial_industrial, hospital, fire_station | digest isi di `results/results.json` |
| overture_landuse_osm.parquet | Overture `release/2026-10-21.0/theme=base/type=land_use` (32 file), kelas industrial, works, hospital | digest isi di `results/results.json` |

Hash lengkap: `src/geo_atlas/config.py` dan `results/results.json` → `provenance.manifest`.

## Isi dan ukuran (setelah spatial join ke Indonesia)

| Lapisan | Jumlah |
|---|---|
| Unit ADM2 | 519 (514 kab/kota + Danau, Danau Toba, Hutan, Waduk Cirata, Wadung Kedungombo) |
| Provinsi ADM1 | 34 (sebelum pemekaran Papua 2022) |
| Titik manufaktur (semua skor keyakinan) | 20.018 |
| + perusahaan industri (definisi luas) | 24.013 |
| Label "hospital" | 22.320 |
| Rumah sakit nama jelas | 8.036 |
| Pemadam kebakaran | 486 |
| Poligon kawasan industri OSM | 8.469 (2.270 km²) |
| Poligon rumah sakit OSM | 1.790 |

Sumber utama titik Overture: Meta (99%), lalu Microsoft dan Foursquare.

## Kualitas dan bias yang diketahui

- **Bias kota**: 156 dari 514 kab/kota tidak punya titik manufaktur (keyakinan ≥ 0,5); daerah timur
  dan pedalaman jauh lebih jarang tercatat.
- **Label "hospital" campur aduk**: 26% bernama klinik, 17% puskesmas, 7% dokter/bidan praktik. Saring
  nama juga ikut menangkap unit di dalam RS (mis. "Ruang Picu RSUD …"), tidak masalah untuk jarak.
- **Pemadam**: hanya 486 titik, 320 kab/kota kosong. Coverage pemadam terutama mengukur data yang hilang.
- **Alamat**: hanya 9% titik punya teks provinsi; format campur (kode ISO dua huruf, nama Indonesia,
  nama Inggris).
- **Batas provinsi** dari OSM 2017 tidak persis sejalan dengan batas kab/kota BPS 2020 (61 kab/kota
  kurang dari 99% di satu provinsi). Provinsi ditentukan dari irisan luas terbesar; Kepulauan Seribu
  tidak beririsan sama sekali dan diberi provinsi terdekat (DKI Jakarta).
- Titik di dekat perbatasan darat (Kalimantan, Timor, Papua) yang tidak punya label negara bisa ditarik
  ke kab/kota terdekat bila asumsi "≤ 1 km" dipilih. Rumah sakit OSM di negara tetangga dalam 1 km dari
  perbatasan bisa ikut terhitung. Dampaknya diukur di grid sensitivitas (asumsi "luar" berpengaruh
  rata-rata 0,05 poin persen).

## Privasi

Titik adalah tempat usaha dan fasilitas publik. File publikasi tidak memuat nama, alamat, atau ID
tempat; hanya koordinat (5 desimal), skor keyakinan, dan kode kab/kota.
