"""Unduh data mentah: batas wilayah geoBoundaries dan titik/poligon Overture Maps.

Overture dibaca langsung dari S3 publik dengan DuckDB (httpfs + spatial), hanya baris di kotak
Indonesia dan kategori yang dipakai. Hasilnya disimpan sebagai Parquet di data/raw/.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

import duckdb

from . import config as C


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def connect(with_httpfs: bool = False) -> duckdb.DuckDBPyConnection:
    """Koneksi DuckDB dengan ekstensi spatial dari wheel PyPI (tanpa akses extensions.duckdb.org)."""
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    con.execute("SET enable_progress_bar = false")
    names = ["spatial"] + (["httpfs"] if with_httpfs else [])
    for name in names:
        try:
            con.execute(f"LOAD {name}")
            continue
        except duckdb.Error:
            pass
        pattern = os.path.join(os.path.dirname(duckdb.__file__), "..",
                               f"duckdb_extension_{name}", "**", f"{name}.duckdb_extension")
        found = glob.glob(pattern, recursive=True)
        if found:
            con.execute(f"INSTALL '{os.path.abspath(found[0])}'")
        else:
            con.execute(f"INSTALL {name}")
        con.execute(f"LOAD {name}")
    if with_httpfs:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            con.execute(f"SET http_proxy='{proxy.removeprefix('http://').rstrip('/')}'")
    return con


def fetch_boundaries(out: Path = C.RAW) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    info = {}
    for key, (rel, sha) in C.BOUNDARY_FILES.items():
        dest = out / Path(rel).name
        if not dest.exists() or sha256_file(dest) != sha:
            urllib.request.urlretrieve(f"{C.GEOBOUNDARIES_BASE}/{rel}", dest)
        got = sha256_file(dest)
        if got != sha:
            raise RuntimeError(f"SHA-256 {dest.name} tidak cocok: {got} != {sha}")
        info[key] = {"file": dest.name, "sha256": got}
    return info


def _overture_urls(theme: str, typ: str) -> list[str]:
    prefix = f"release/{C.OVERTURE_RELEASE}/theme={theme}/type={typ}/"
    urls, token = [], None
    while True:
        q = f"{C.OVERTURE_BUCKET}/?list-type=2&prefix={prefix}"
        if token:
            q += "&continuation-token=" + urllib.request.quote(token, safe="")
        body = urllib.request.urlopen(q, timeout=60).read().decode()
        urls += [f"{C.OVERTURE_BUCKET}/{k}" for k in re.findall(r"<Key>(.*?)</Key>", body)
                 if k.endswith(".parquet")]
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", body)
        if not m:
            break
        token = m.group(1)
    if not urls:
        raise RuntimeError(f"Tidak ada file Overture untuk {prefix}")
    return urls


def _bbox_sql() -> str:
    b = C.BBOX
    return (f"bbox.xmin >= {b['xmin']} AND bbox.xmax <= {b['xmax']} "
            f"AND bbox.ymin >= {b['ymin']} AND bbox.ymax <= {b['ymax']}")


def _in(values) -> str:
    return "(" + ", ".join(f"'{v}'" for v in sorted(values)) + ")"


def fetch_places(out: Path = C.RAW) -> dict:
    con = connect(with_httpfs=True)
    urls = _overture_urls("places", "place")
    dest = out / "overture_places.parquet"
    basics = C.INDUSTRY_NARROW_BASIC | C.HOSPITAL_BASIC | C.FIRE_BASIC
    con.execute(f"""
        COPY (
          SELECT id,
                 names."primary" AS name,
                 basic_category,
                 taxonomy."primary" AS category,
                 confidence,
                 operating_status,
                 addresses[1].region AS addr_region,
                 addresses[1].country AS addr_country,
                 list_transform(sources, s -> s.dataset) AS source_datasets,
                 list_distinct(list_transform(sources, s -> s.license)) AS source_licenses,
                 ST_X(geometry) AS lon,
                 ST_Y(geometry) AS lat
          FROM read_parquet({urls!r})
          WHERE {_bbox_sql()}
            AND (basic_category IN {_in(basics)} OR taxonomy."primary" IN {_in(C.INDUSTRY_BROAD_EXTRA_PRIMARY)})
          ORDER BY id
        ) TO '{dest}' (FORMAT parquet, COMPRESSION zstd)
    """)
    n = con.sql(f"SELECT count(*) FROM '{dest}'").fetchone()[0]
    return {"file": dest.name, "rows": n, "release": C.OVERTURE_RELEASE, "n_source_files": len(urls),
            "content_digest": content_digest(con, dest, "id, lon, lat, basic_category, category, confidence")}


def fetch_landuse(out: Path = C.RAW) -> dict:
    con = connect(with_httpfs=True)
    urls = _overture_urls("base", "land_use")
    dest = out / "overture_landuse_osm.parquet"
    classes = C.OSM_INDUSTRY_CLASSES | C.OSM_HOSPITAL_CLASSES
    con.execute(f"""
        COPY (
          SELECT id, names."primary" AS name, subtype, class,
                 list_distinct(list_transform(sources, s -> s.license)) AS source_licenses,
                 ST_AsWKB(geometry) AS geom_wkb
          FROM read_parquet({urls!r})
          WHERE {_bbox_sql()} AND class IN {_in(classes)}
          ORDER BY id
        ) TO '{dest}' (FORMAT parquet, COMPRESSION zstd)
    """)
    n = con.sql(f"SELECT count(*) FROM '{dest}'").fetchone()[0]
    return {"file": dest.name, "rows": n, "release": C.OVERTURE_RELEASE, "n_source_files": len(urls),
            "content_digest": content_digest(con, dest, "id, class, md5(geom_wkb)")}


def content_digest(con, path: Path, cols: str) -> str:
    """Hash isi (bukan byte file) supaya bisa dibandingkan antar-run walau encoder Parquet berbeda."""
    rows = con.sql(f"SELECT {cols} FROM '{path}' ORDER BY id").fetchall()
    h = hashlib.sha256()
    for r in rows:
        h.update(repr(r).encode())
    return h.hexdigest()


def fetch_all(out: Path = C.RAW) -> dict:
    manifest = {"boundaries": fetch_boundaries(out), "places": fetch_places(out),
                "landuse": fetch_landuse(out)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
