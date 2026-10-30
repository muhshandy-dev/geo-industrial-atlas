"""CLI: geo-atlas fetch | run."""

from __future__ import annotations

import argparse
import json

from . import config as C


def main(argv=None):
    ap = argparse.ArgumentParser(prog="geo-atlas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="unduh batas wilayah dan data Overture (rilis dikunci)")
    sub.add_parser("run", help="jalankan pipeline dan tulis file publikasi")
    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        from .fetch import fetch_all
        print(json.dumps(fetch_all(), indent=2))
    elif args.cmd == "run":
        from .analysis import run
        from .publish import write_all
        manifest = json.loads((C.RAW / "manifest.json").read_text())
        res = run()
        info = write_all(res, manifest)
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
