"""Buat static/geojson/kecamatan.geojson (33 kecamatan Kabupaten Malang) dari GADM 4.1.

Sumber batas wilayah: GADM v4.1, Indonesia level 3 (kecamatan) - https://gadm.org
Setiap feature diberi properti `kecamatan_id` yang cocok dengan tabel `kecamatan` di Supabase.

Pemakaian:
    python build_geojson.py
"""
import io
import json
import os
import re
import sys
import zipfile

import httpx
from dotenv import load_dotenv
from supabase import create_client

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IDN_3.json.zip"
CACHE = os.path.join("data_mentah", "gadm41_IDN_3.json.zip")
OUT = os.path.join("static", "geojson", "kecamatan.geojson")
ALIAS = {"sumbermanjing": "sumbermanjingwetan"}  # penamaan GADM -> nama BPS


def norm(s):
    s = re.sub(r"[^a-z]", "", s.lower())
    return ALIAS.get(s, s)


def load_gadm():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        print("Mengunduh", GADM_URL)
        r = httpx.get(GADM_URL, timeout=600, follow_redirects=True)
        r.raise_for_status()
        with open(CACHE, "wb") as f:
            f.write(r.content)
    z = zipfile.ZipFile(CACHE)
    return json.load(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8"))


def round_coords(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 5), round(c[1], 5)]
    return [round_coords(x) for x in c]


def format_geojson(data):
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    return re.sub(
        r"\[\s+(-?\d+(?:\.\d+)?),\s+(-?\d+(?:\.\d+)?)\s+\]",
        r"[\1, \2]",
        raw,
    )


def main():
    load_dotenv()
    db = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
    kec = (
        db.table("kecamatan")
        .select("id,kode_kecamatan,nama_kecamatan")
        .execute()
        .data
    )
    by_name = {norm(k["nama_kecamatan"]): k for k in kec}

    gadm = load_gadm()
    features, matched = [], set()
    for f in gadm["features"]:
        p = f["properties"]
        if p.get("NAME_1") != "JawaTimur" or p.get("NAME_2") != "Malang":
            continue
        k = by_name.get(norm(p["NAME_3"]))
        if not k:
            print("  tidak cocok:", p["NAME_3"])
            continue
        matched.add(k["id"])
        features.append({
            "type": "Feature",
            "properties": {
                "kecamatan_id": k["id"],
                "kode_kecamatan": k["kode_kecamatan"],
                "kode_bps": p.get("CC_3"),
                "nama_kecamatan": k["nama_kecamatan"],
            },
            "geometry": {
                "type": f["geometry"]["type"],
                "coordinates": round_coords(f["geometry"]["coordinates"]),
            },
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    geojson_data = {
        "type": "FeatureCollection",
        "features": features,
    }
    with open(OUT, "w", encoding="utf-8") as fo:
        fo.write(format_geojson(geojson_data) + "\n")

    print(f"Tersimpan {len(features)} kecamatan ke {OUT} ({os.path.getsize(OUT) // 1024} KB)")
    missing = [k["nama_kecamatan"] for k in kec if k["id"] not in matched]
    if missing:
        print("Belum ditemukan:", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
