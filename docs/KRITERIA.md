# Status kriteria penerimaan

Kriteria ditulis 2026-10-29 **sebelum coding** (`/mnt/project-files/geo-industrial-atlas/kriteria-penerimaan.md`).
Status di bawah dicek 2026-10-29 pada data asli (Overture 2026-10-21.0, geoBoundaries dengan hash terkunci);
K10 bagian CI ditambahkan 2026-10-30.

| # | Kriteria | Status | Bukti |
|---|---|---|---|
| K1 | Spatial join benar 100% pada fixture (tepi, sudut, lubang, multipoligon, laut), kedua mesin | **Lulus** | `tests/test_join_fixture.py`: 11/11 kasus, GeoPandas dan DuckDB; jumlah kecocokan ganda sama (4) |
| K2 | GeoPandas vs DuckDB ≥ 99,99% identik di data asli | **Lulus** | 89.532/89.532 titik identik (100%) di batas penuh dan disederhanakan; 0 perbedaan |
| K3 | Titik di luar poligon dihitung; kebijakan ≤ 1 km diuji sebagai asumsi | **Lulus** | 32.454 titik di luar (MY 21.819, SG 2.858, …; 56 berlabel ID); 0 titik berlabel negara lain masuk kab/kota; 165 titik ditarik oleh aturan ≤ 1 km; masuk grid sensitivitas |
| K4 | Geometri invalid 0; tumpang tindih dan celah dilaporkan; hierarki ≥ 99% atau dicantumkan | **Lulus dengan catatan** | invalid 0, tumpang tindih 0, 9 celah (26,8 km²); 5 unit bukan kab/kota ditandai; 61 kab/kota < 99% di satu provinsi (batas ADM1 OSM 2017 vs ADM2 BPS 2020), semua dicantumkan di `results.json` |
| K5 | Provinsi hasil join vs alamat ≥ 90% atau diselidiki | **Lulus** | 99,82% dari 4.355 titik (kode ISO 99,90%, nama 98,37%); contoh ketidakcocokan dicatat. Hanya 9% titik punya teks provinsi |
| K6 | Haversine vs Geod ≤ 0,5%; luas sama-luas vs geodesik ≤ 0,5% | **Sebagian gagal, diperbaiki** | Luas: maks 0,0018% (lulus). Haversine: maks **0,56%** (gagal). Perbaikan: jarak publikasi memakai geodesik elipsoid; selisih vs brute force 0 m pada 300 sampel |
| K7 | Coverage layanan dan data, kesesuaian antar sumber | **Lulus** | Skenario dasar 97,18% (9.127/9.392) ≤ 10 km dari RS; kab/kota kosong per lapisan; Spearman industri 0,51 (luas OSM) / 0,59 (jumlah), RS 0,66 |
| K8 | Grid sensitivitas lengkap; label "kokoh" jujur | **Lulus** | 216 kombinasi; Kendall tau median 0,49 ("terjauh dari RS") vs 0,91 (kepadatan); 7 kota kokoh di 10 besar kepadatan; tidak ada kab/kota kokoh di 10 besar "terjauh" (Kutai Kartanegara 78%) |
| K9 | Browser = Python untuk semua skenario | **Lulus** | `web/tests/parity.test.ts`: 216 kombinasi, n, n_cov, coverage, 10 besar identik |
| K10 | Rerun dari data terkunci identik byte-per-byte | **Lulus** | Lokal: tiga kali `geo-atlas run`, hash 6 file publikasi sama. GitHub: `real-data.yml` run 41083221269 (2026-10-30) mengunduh ulang geoBoundaries + Overture di runner, hasil `identik` dengan yang di-commit, run kedua identik, pytest 34 lulus |
| K11 | Statis, file < 25 MiB, tanpa tile eksternal, atribusi tampil | **Lulus** | `scripts/check-build.mjs`: 20 file, terbesar 2,6 MiB, tidak ada URL tile, atribusi CC BY 3.0 IGO / CDLA-P-2.0 / ODbL ada di HTML |
| K12 | Tidak ada klaim jumlah resmi atau sebab-akibat | **Lulus** | `tests/test_published_results.py::test_k12…` memindai teks pernyataan dan sumber web |
| K13 | UI beda, dicek 1440/390 terang/gelap, axe 0 | **Lulus (lokal + CI)** | Screenshot 5 bab × 4 tampilan; axe 0 pelanggaran di 20 kombinasi, juga di job CI `web`. Situs langsung belum ada |

## Penyimpangan dari Master PDF dan dari rencana

1. **Titik fasilitas** memakai Overture Maps (Meta/Microsoft/Foursquare) dan OSM, bukan daftar resmi
   Kemenkes/BPS. Master menulis "open data BPS/wilayah dan titik fasilitas publik": batas wilayah memang
   turunan BPS, tetapi bps.go.id dan HDX diblokir dari sesi dan belum ada pembanding hitungan resmi.
2. **K6** gagal pada rumus bola; metode diganti ke elipsoid (lebih benar), dicatat di `docs/METODE.md`.
3. **Kaggle** tidak dipakai: DA09 tidak melatih model, semua komputasi berjalan di laptop/CI dalam ~1 menit.
4. Hanya **jarak garis lurus**; waktu tempuh lewat jalan (routing) di luar lingkup.
5. Batas provinsi 34 (sebelum pemekaran Papua 2022) karena lapisan ADM1 geoBoundaries tahun 2017.

## Yang belum bisa diklaim

- Situs langsung di Cloudflare Pages: belum dibuat, dan sesi tidak bisa membuka `*.pages.dev`.
  Shandy perlu mengecek sendiri setelah deploy.
