"""Versi data yang dikunci dan definisi asumsi.

Semua angka publikasi berasal dari file yang tercantum di sini. Mengganti rilis atau hash
berarti hasil berubah dan harus dilaporkan ulang.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
RESULTS = ROOT / "results"
WEB_DATA = ROOT / "web" / "public" / "data"

# Batas wilayah: geoBoundaries gbOpen IDN. Hash = oid Git LFS di repo geoBoundaries (isi file).
GEOBOUNDARIES_BASE = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/IDN"
BOUNDARY_FILES = {
    "adm2_full": ("ADM2/geoBoundaries-IDN-ADM2.geojson",
                  "947cedc058888c0c2b2628071d289956c85fe279adb369dcf1327ce2236a5602"),
    "adm2_simplified": ("ADM2/geoBoundaries-IDN-ADM2_simplified.geojson",
                        "146653d488331086ddc43d159a261b01ea6dd08c7ed422e34a9886c3c690430c"),
    "adm1_full": ("ADM1/geoBoundaries-IDN-ADM1.geojson",
                  "9a2c93ed5c956d7b9afeab4882e9aab9c3fceb8be4cafaae6e198223c2cbb3af"),
}
BOUNDARY_META = {
    "adm2": {"source": "Badan Pusat Statistik (BPS), World Food Programme, OCHA ROAP", "year": 2020,
             "license": "CC BY 3.0 IGO", "geoboundaries_id": "IDN-ADM2-22746128"},
    "adm1": {"source": "OpenStreetMap, Wambacher", "year": 2017,
             "license": "ODbL 1.0", "geoboundaries_id": "IDN-ADM1-65028918"},
}

# Overture Maps: rilis dikunci.
OVERTURE_RELEASE = "2026-10-21.0"
OVERTURE_BUCKET = "https://overturemaps-us-west-2.s3.amazonaws.com"
# Kotak pembatas Indonesia (lebih luas dari daratan). Titik di negara tetangga dibuang oleh spatial join.
BBOX = {"xmin": 94.5, "xmax": 141.5, "ymin": -11.5, "ymax": 6.5}

# Unit ADM2 di geoBoundaries yang bukan kabupaten/kota (danau, waduk, hutan).
NON_ADMIN_UNITS = {"Danau", "Danau Toba", "Hutan", "Waduk Cirata", "Wadung Kedungombo"}

# Kategori Overture Places.
INDUSTRY_NARROW_BASIC = {"manufacturer"}
INDUSTRY_BROAD_EXTRA_PRIMARY = {"industrial_company", "commercial_industrial"}
HOSPITAL_BASIC = {"hospital"}
FIRE_BASIC = {"fire_station"}
# Saring nama rumah sakit: hanya nama yang jelas menyebut rumah sakit.
HOSPITAL_NAME_RE = re.compile(
    r"(?:rumah\s*sakit|\bRS[A-Z]{0,4}\b|\bRSU\w*|hospital|\bR\.S\.)", re.IGNORECASE)

# OSM land use (via Overture base) sebagai pembanding independen.
OSM_INDUSTRY_CLASSES = {"industrial", "works"}
OSM_HOSPITAL_CLASSES = {"hospital"}

# Grid sensitivitas.
CONFIDENCE_LEVELS = (0.0, 0.5, 0.7)
RADII_KM = (5, 10, 20)
INDUSTRY_DEFS = ("sempit", "luas")
HOSPITAL_DEFS = ("mentah", "nama", "osm")
BOUNDARY_DEFS = ("penuh", "sederhana")
OUTSIDE_POLICIES = ("buang", "terdekat_1km")
BASE_SCENARIO = {"industri": "sempit", "conf": 0.5, "rs": "nama", "radius": 10,
                 "batas": "penuh", "luar": "buang"}
MIN_POINTS_FOR_RANK = 10  # kab/kota dengan titik industri lebih sedikit tidak diperingkat
NEAREST_TOLERANCE_M = 1000.0

EARTH_RADIUS_M = 6_371_008.8  # radius rata-rata IUGG
# Proyeksi sama-luas untuk Indonesia (Lambert Azimuthal Equal Area di tengah wilayah).
EQUAL_AREA_CRS = "+proj=laea +lat_0=-2 +lon_0=118 +datum=WGS84 +units=m +no_defs"

# Normalisasi provinsi dari alamat titik ke kode ISO 3166-2 (34 provinsi lapisan ADM1 2017).
PROVINCE_ALIASES = {
    "ID-AC": ["aceh", "nanggroe aceh darussalam", "nad"],
    "ID-SU": ["sumatera utara", "north sumatra", "north sumatera", "sumut"],
    "ID-SB": ["sumatera barat", "west sumatra", "west sumatera", "sumbar"],
    "ID-RI": ["riau"],
    "ID-JA": ["jambi"],
    "ID-SS": ["sumatera selatan", "south sumatra", "south sumatera", "sumsel"],
    "ID-BE": ["bengkulu"],
    "ID-LA": ["lampung"],
    "ID-BB": ["kepulauan bangka belitung", "bangka belitung", "bangka belitung islands",
              "bangka-belitung islands", "babel"],
    "ID-KR": ["kepulauan riau", "riau islands", "kepri"],
    "ID-JK": ["dki jakarta", "jakarta", "daerah khusus ibukota jakarta", "jakarta capital region",
              "jakarta raya", "jakarta jakarta raya", "special capital region of jakarta",
              "jakarta special capital region", "daerah khusus jakarta"],
    "ID-JB": ["jawa barat", "west java", "jabar", "west java jawa barat"],
    "ID-JT": ["jawa tengah", "central java", "jateng", "central java jawa tengah"],
    "ID-YO": ["di yogyakarta", "daerah istimewa yogyakarta", "yogyakarta",
              "special region of yogyakarta", "diy"],
    "ID-JI": ["jawa timur", "east java", "jatim", "east java jawa timur"],
    "ID-BT": ["banten"],
    "ID-BA": ["bali"],
    "ID-NB": ["nusa tenggara barat", "west nusa tenggara", "ntb"],
    "ID-NT": ["nusa tenggara timur", "east nusa tenggara", "ntt"],
    "ID-KB": ["kalimantan barat", "west kalimantan", "kalbar"],
    "ID-KT": ["kalimantan tengah", "central kalimantan", "kalteng"],
    "ID-KS": ["kalimantan selatan", "south kalimantan", "kalsel"],
    "ID-KI": ["kalimantan timur", "east kalimantan", "kaltim"],
    "ID-KU": ["kalimantan utara", "north kalimantan", "kaltara"],
    "ID-SA": ["sulawesi utara", "north sulawesi", "sulut"],
    "ID-ST": ["sulawesi tengah", "central sulawesi", "sulteng"],
    "ID-SN": ["sulawesi selatan", "south sulawesi", "sulsel"],
    "ID-SG": ["sulawesi tenggara", "southeast sulawesi", "south east sulawesi", "sultra"],
    "ID-GO": ["gorontalo"],
    "ID-SR": ["sulawesi barat", "west sulawesi", "sulbar"],
    "ID-MA": ["maluku"],
    "ID-MU": ["maluku utara", "north maluku"],
    # Pemekaran Papua 2022 dipetakan ke provinsi induk pada lapisan 2017.
    "ID-PA": ["papua", "papua selatan", "south papua", "papua tengah", "central papua",
              "papua pegunungan", "highland papua"],
    "ID-PB": ["papua barat", "west papua", "papua barat daya", "southwest papua"],
}
ISO_CODES = set(PROVINCE_ALIASES)
# Nama resmi berbahasa Indonesia (lapisan ADM1 geoBoundaries memakai nama Inggris OSM).
PROVINCE_NAME_ID = {
    "ID-AC": "Aceh", "ID-SU": "Sumatera Utara", "ID-SB": "Sumatera Barat", "ID-RI": "Riau",
    "ID-JA": "Jambi", "ID-SS": "Sumatera Selatan", "ID-BE": "Bengkulu", "ID-LA": "Lampung",
    "ID-BB": "Kepulauan Bangka Belitung", "ID-KR": "Kepulauan Riau", "ID-JK": "DKI Jakarta",
    "ID-JB": "Jawa Barat", "ID-JT": "Jawa Tengah", "ID-YO": "DI Yogyakarta", "ID-JI": "Jawa Timur",
    "ID-BT": "Banten", "ID-BA": "Bali", "ID-NB": "Nusa Tenggara Barat", "ID-NT": "Nusa Tenggara Timur",
    "ID-KB": "Kalimantan Barat", "ID-KT": "Kalimantan Tengah", "ID-KS": "Kalimantan Selatan",
    "ID-KI": "Kalimantan Timur", "ID-KU": "Kalimantan Utara", "ID-SA": "Sulawesi Utara",
    "ID-ST": "Sulawesi Tengah", "ID-SN": "Sulawesi Selatan", "ID-SG": "Sulawesi Tenggara",
    "ID-GO": "Gorontalo", "ID-SR": "Sulawesi Barat", "ID-MA": "Maluku", "ID-MU": "Maluku Utara",
    "ID-PA": "Papua", "ID-PB": "Papua Barat",
}


def _norm(s: str) -> str:
    s = s.lower().replace("-", " ").replace(".", " ")
    s = re.sub(r"\b(provinsi|province|prov)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_ALIAS = {_norm(a): iso for iso, names in PROVINCE_ALIASES.items() for a in names}


def normalize_province(raw: str | None) -> str | None:
    """Ubah teks provinsi di alamat ke kode ISO. None bila kosong atau tidak dikenali.

    Kode dua huruf (mis. "JB") dianggap kode ISO 3166-2:ID tanpa awalan.
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    up = s.upper()
    if up.startswith("ID-") and up in ISO_CODES:
        return up
    if len(up) == 2 and f"ID-{up}" in ISO_CODES:
        return f"ID-{up}"
    return _ALIAS.get(_norm(s))
