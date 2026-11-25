"""Membaca file import data pertanian (CSV atau XLSX) dari halaman Admin.

Format yang didukung sama dengan import_data.py dan convert_excel.py:
- CSV  : nama_kecamatan,tahun,luas_panen,produksi,produktivitas
- XLSX : satu sheet per tahun (judul sheet = tahun), kolom dipetakan dari teks header.
"""
import csv
import io
import re
from typing import Any, Dict, List, Tuple

import openpyxl

ALIAS = {"sumbermanjing": "sumbermanjingwetan"}


def _norm(name: str) -> str:
    key = re.sub(r"[^a-z]", "", str(name).lower())
    return ALIAS.get(key, key)


def _to_float(value) -> float:
    return float(str(value).strip().replace(",", "."))


def parse_file(file_storage, kecamatan, years) -> Tuple[List[Dict[str, Any]], List[str]]:
    id_by_name = {_norm(k["nama_kecamatan"]): int(k["id"]) for k in kecamatan}
    filename = (file_storage.filename or "").lower()
    content = file_storage.read()

    if filename.endswith(".csv"):
        raw_rows = _read_csv(content)
    elif filename.endswith(".xlsx"):
        raw_rows = _read_xlsx(content)
    else:
        return [], ["Format file harus .csv atau .xlsx."]

    payload, errors = [], []
    for sumber, nama, tahun, luas, prod, pvt in raw_rows:
        kid = id_by_name.get(_norm(nama))
        if kid is None:
            errors.append(f"{sumber}: kecamatan '{nama}' tidak dikenal")
            continue
        try:
            item = {
                "kecamatan_id": kid,
                "tahun": int(tahun),
                "luas_panen": _to_float(luas),
                "produksi": _to_float(prod),
                "produktivitas": _to_float(pvt),
            }
        except (TypeError, ValueError):
            errors.append(f"{sumber}: nilai angka tidak valid")
            continue
        if item["tahun"] not in years:
            errors.append(f"{sumber}: tahun {item['tahun']} di luar 2018–2025")
            continue
        if min(item["luas_panen"], item["produksi"], item["produktivitas"]) < 0:
            errors.append(f"{sumber}: nilai negatif")
            continue
        payload.append(item)

    if not payload and not errors:
        errors.append("Tidak ada baris data yang terbaca dari file.")
    return payload, errors


def _read_csv(content: bytes):
    text = content.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    for line_no, row in enumerate(reader, start=2):
        yield (
            f"Baris {line_no}",
            row.get("nama_kecamatan", ""),
            row.get("tahun"),
            row.get("luas_panen"),
            row.get("produksi"),
            row.get("produktivitas"),
        )


def _read_xlsx(content: bytes):
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    for ws in wb.worksheets:
        title = ws.title.strip()
        if not title.isdigit():
            continue
        header_row, cells = _find_header(ws)
        if header_row is None:
            continue
        try:
            i_kec = _col(cells, "kecamatan")
            i_luas = _col(cells, "luas panen")
            i_prod = _col(cells, "produksi")
            i_pvt = _col(cells, "produktivitas")
        except ValueError:
            continue

        for r_idx, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True),
                                    start=header_row + 1):
            if not isinstance(row[0], (int, float)):
                continue  # lewati baris Total / tanda tangan
            nama = re.sub(r"^\d+\s+", "", str(row[i_kec]).strip())
            yield (
                f"Sheet {title} baris {r_idx}",
                nama,
                int(title),
                row[i_luas],
                row[i_prod],
                row[i_pvt],
            )


def _find_header(ws):
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        cells = [str(c).strip().lower() if c is not None else "" for c in row]
        if "no" in cells and any(c.startswith("kecamatan") for c in cells):
            return r, cells
    return None, []


def _col(cells, keyword) -> int:
    for i, c in enumerate(cells):
        if c.startswith(keyword):
            return i
    raise ValueError(keyword)

