# Geo-Industrial Insights Atlas

**Atlas geospasial: industri, rumah sakit, dan pemadam di 514 kabupaten/kota Indonesia, dengan uji
kebenaran spatial join dan 216 skenario asumsi.**

- **Masalah**: peta "fasilitas dekat industri" mudah dibuat, tetapi jarang dicek apakah titiknya masuk
  wilayah yang benar dan apakah kesimpulannya bertahan bila definisi data diganti.
- **Data**: batas kab/kota BPS (geoBoundaries), Overture Maps Places (72 ribu titik di kotak Indonesia),
  kawasan industri dan RS OpenStreetMap sebagai pembanding.
- **Metode**: spatial join GeoPandas dan DuckDB (dua mesin, hasil 100% identik pada 89.532 titik),
  fixture kasus tepi, jarak geodesik elipsoid, luas di proyeksi sama-luas, cek silang alamat (99,8%),
  grid sensitivitas 216 kombinasi dengan Kendall tau dan label "kokoh".
- **Temuan**: 97,2% titik manufaktur tercatat berada ≤ 10 km dari rumah sakit (rentang 91–99% antar
  asumsi); peringkat daerah "terjauh" tidak kokoh, kepadatan industri kokoh.
- **Teknologi**: Python, GeoPandas, DuckDB spatial, pyproj, Astro, React, MapLibre GL, GitHub Actions,
  Cloudflare Pages.
- **Kejujuran data**: label "hospital" Overture berisi klinik dan puskesmas, data pemadam bolong;
  keduanya diukur dan ditampilkan, bukan disembunyikan.
