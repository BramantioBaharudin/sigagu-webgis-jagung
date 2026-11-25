"""Impor data jagung dari CSV ke tabel Supabase `data_jagung`.

Format CSV (header wajib, pemisah koma atau titik koma):
    nama_kecamatan,tahun,luas_panen,produksi,produktivitas
    Donomulyo,2018,1234.5,6789.0,55.0

Pemakaian:
    python import_data.py data_jagung.csv
"""
import csv
import os
import sys

from dotenv import load_dotenv
from supabase import create_client


def norm(name: str) -> str:
    return "".join(name.lower().split())


def to_float(value: str) -> float:
    return float(str(value).strip().replace(",", "."))


def main(path: str) -> None:
    load_dotenv()
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    kec = db.table("kecamatan").select("id,nama_kecamatan").execute().data or []
    by_name = {norm(k["nama_kecamatan"]): k["id"] for k in kec}

    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        reader = csv.DictReader(f, dialect=dialect)
        payload, errors = [], []
        for line_no, row in enumerate(reader, start=2):
            kid = by_name.get(norm(row["nama_kecamatan"]))
            if kid is None:
                errors.append(f"Baris {line_no}: kecamatan '{row['nama_kecamatan']}' tidak ditemukan")
                continue
            try:
                item = {
                    "kecamatan_id": kid,
                    "tahun": int(row["tahun"]),
                    "luas_panen": to_float(row["luas_panen"]),
                    "produksi": to_float(row["produksi"]),
                    "produktivitas": to_float(row["produktivitas"]),
                }
            except (ValueError, KeyError) as e:
                errors.append(f"Baris {line_no}: nilai tidak valid ({e})")
                continue
            payload.append(item)

    if errors:
        print("Ditemukan kesalahan, impor dibatalkan:")
        print("\n".join(errors))
        sys.exit(1)

    db.table("data_jagung").upsert(payload, on_conflict="kecamatan_id,tahun").execute()
    print(f"Berhasil mengimpor {len(payload)} baris.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
