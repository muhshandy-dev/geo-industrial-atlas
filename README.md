# Geo-Industrial Insights Atlas

Atlas geospasial untuk satu pertanyaan: **seberapa jauh titik industri yang tercatat di tiap
kabupaten/kota Indonesia dari rumah sakit dan pemadam kebakaran, dan seberapa kokoh jawaban itu bila
asumsi data dan metode diubah?**

Fokus proyek ini bukan peta yang cantik, tetapi tiga hal yang diuji: **kebenaran spatial join**,
**coverage** (layanan dan kelengkapan data), dan **sensitivitas asumsi**.

## Hasil utama (data asli, rilis Overture 2026-10-21.0)

| Hal | Hasil |
|---|---|
| Spatial join GeoPandas vs DuckDB | 89.532 titik, **100% identik** (batas penuh dan disederhanakan) |
| Fixture jawaban-diketahui (tepi, sudut, lubang, pulau, laut) | 11/11 benar di kedua mesin |
| Provinsi hasil join vs provinsi di alamat titik | **99,8%** cocok (4.355 titik yang alamatnya menyebut provinsi) |
| Titik industri ≤ 10 km dari RS (skenario dasar) | **97,2%** (9.127 dari 9.392) |
| Rentang coverage 10 km di semua kombinasi asumsi | 91,4% sampai 99,4% |
| Asumsi paling berpengaruh | radius (rata-rata 8,5 pp), lalu definisi rumah sakit (8,0 pp) |
| Kesimpulan kokoh | 7 kota selalu di 10 besar kepadatan industri; **tidak ada** kab/kota yang selalu di 10 besar "terjauh dari RS" |

Detail lengkap: [`docs/KRITERIA.md`](docs/KRITERIA.md) (status K1 sampai K13) dan
[`results/results.json`](results/results.json).

## Batas klaim

- Titik = yang **tercatat** di Overture Maps / OpenStreetMap, bukan jumlah resmi pabrik atau rumah sakit.
- Label "hospital" Overture juga memuat klinik (26%) dan puskesmas (17%); karena itu ada definisi
  "nama jelas rumah sakit" dan pembanding OSM.
- Data pemadam sangat tidak lengkap (486 titik; 320 dari 514 kab/kota kosong).
- Jarak = garis lurus geodesik, bukan waktu tempuh jalan. Tidak ada klaim sebab-akibat.

## Struktur

```
src/geo_atlas/      pipeline Python (GeoPandas + DuckDB spatial)
  fetch.py          unduh geoBoundaries (hash dikunci) + Overture via DuckDB httpfs
  boundaries.py     topologi, luas sama-luas vs geodesik, hierarki kab/kota -> provinsi
  join.py           spatial join dua mesin, aturan titik di batas, kebijakan titik luar poligon
  geodesy.py        tetangga terdekat geodesik (KD-tree + verifikasi elipsoid)
  analysis.py       coverage, cek alamat, kesesuaian antar sumber
  scenario.py       216 skenario sensitivitas (logika yang dicerminkan di web)
  publish.py        file publikasi deterministik
web/                Astro + React island + MapLibre GL (situs statis)
  src/lib/scenario.ts  perhitungan ulang di browser (paritas dengan Python)
tests/              pytest: fixture join, geodesi, skenario, hasil publikasi
web/tests/          tes paritas 216 skenario (node:test) + axe
```

## Menjalankan ulang

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
geo-atlas fetch      # ~1-2 menit: geoBoundaries + Overture (hanya kotak Indonesia)
geo-atlas run        # pipeline + tulis web/public/data dan results/
pytest -q

cd web
npm ci
npm test             # paritas browser vs Python
npm run build        # situs statis di web/dist + cek ukuran/atribusi
```

Ekstensi DuckDB `spatial` dan `httpfs` dipasang dari wheel PyPI (`duckdb-extension-*`), jadi tidak
perlu akses ke extensions.duckdb.org. Workflow **Real data run** (`.github/workflows/real-data.yml`)
mengunduh semua data di runner GitHub, menjalankan pipeline dua kali, dan memeriksa bahwa hasilnya
identik byte-per-byte dengan yang di-commit.

## Data dan lisensi

| Lapisan | Sumber | Lisensi |
|---|---|---|
| Batas kab/kota (ADM2) | geoBoundaries gbOpen IDN, dari BPS + OCHA ROAP (2020) | CC BY 3.0 IGO |
| Batas provinsi (ADM1) | geoBoundaries gbOpen IDN, dari OpenStreetMap (2017) | ODbL 1.0 |
| Titik industri, RS, pemadam | Overture Maps Places 2026-10-21.0 | CDLA-Permissive-2.0 (sumber per baris juga Apache-2.0, CC0-1.0) |
| Poligon kawasan industri dan RS | Overture Base land_use, dari OpenStreetMap | ODbL 1.0 |

Kode: MIT. Lihat [`docs/DATA_CARD.md`](docs/DATA_CARD.md).
