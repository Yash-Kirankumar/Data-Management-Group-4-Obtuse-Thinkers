"""EXTRACT: download the two source files into data/raw/ exactly as published.

    python tools/download_data.py

Nothing is changed in the files. A manifest records URL, size, SHA-256 and licence,
so anyone can later prove that data/raw/ still holds exactly what was downloaded.
"""
import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SOURCES = [
    {"file": "online_retail_II.xlsx",
     "url": "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip",
     "licence": "CC BY 4.0 - Chen, D. (2012/2019). Online Retail II. UCI Machine Learning Repository. "
                "https://doi.org/10.24432/C5CG6D",
     "in_zip": True},
    {"file": "countryInfo.txt",
     "url": "https://download.geonames.org/export/dump/countryInfo.txt",
     "licence": "CC BY 4.0 - GeoNames (geonames.org)",
     "in_zip": False},
]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    for s in SOURCES:
        target = RAW / s["file"]
        if not target.exists():  # raw files are written once and never overwritten
            print("downloading", s["url"])
            data = urllib.request.urlopen(s["url"]).read()
            if s["in_zip"]:
                data = zipfile.ZipFile(io.BytesIO(data)).read(s["file"])
            target.write_bytes(data)
        manifest.append({"file": s["file"], "url": s["url"], "licence": s["licence"],
                         "bytes": target.stat().st_size,
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    (RAW / "_download_manifest.json").write_text(
        json.dumps({"checked_on": str(date.today()), "files": manifest}, indent=2) + "\n")
    for m in manifest:
        print(f"{m['file']}: {m['bytes']:,} bytes, sha256 {m['sha256'][:16]}...")


if __name__ == "__main__":
    main()
