"""K10: bandingkan data unduhan dan file publikasi dengan versi yang di-commit.

Dipakai di workflow real-data:
  python tools/check_reproducible.py snapshot   # simpan hash yang di-commit
  geo-atlas fetch && geo-atlas run
  python tools/check_reproducible.py compare    # gagal bila isi berubah
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "raw" / "_committed_snapshot.json"


def current():
    pm = json.loads((ROOT / "results" / "publish_manifest.json").read_text())
    res = json.loads((ROOT / "results" / "results.json").read_text())
    man = res["provenance"]["manifest"]
    return {"publish_sha256": pm["sha256"],
            "places_digest": man["places"]["content_digest"], "landuse_digest": man["landuse"]["content_digest"],
            "boundaries": {k: v["sha256"] for k, v in man["boundaries"].items()}}


def main(cmd):
    if cmd == "snapshot":
        SNAP.write_text(json.dumps(current(), indent=2))
        print("snapshot disimpan")
        return 0
    old = json.loads(SNAP.read_text())
    raw = json.loads((ROOT / "data" / "raw" / "manifest.json").read_text())
    new = current()
    problems = []
    if raw["places"]["content_digest"] != old["places_digest"]:
        problems.append("isi Overture Places berbeda dari yang di-commit")
    if raw["landuse"]["content_digest"] != old["landuse_digest"]:
        problems.append("isi Overture land_use berbeda dari yang di-commit")
    for k, v in new["publish_sha256"].items():
        if old["publish_sha256"].get(k) != v:
            problems.append(f"file publikasi berubah: {k}")
    for p in problems:
        print("BEDA:", p)
    print("identik" if not problems else f"{len(problems)} perbedaan")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
