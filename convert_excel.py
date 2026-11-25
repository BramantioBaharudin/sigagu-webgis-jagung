"""Konversi 'Dataset Jagung 2018-2025.xlsx' (1 sheet per tahun) menjadi data_jagung.csv.

Menangani dua format sheet yang berbeda:
- 2018-2022: Kecamatan | Luas Panen | Produksi | Produktivitas
- 2023-2025: Kecamatan BPS ("010 Donomulyo") | Luas Panen | Produktivitas | Produksi
Kolom dipetakan berdasarkan teks header, bukan posisi.

Pemakaian:
    python convert_excel.py "Dataset Jagung 2018-2025.xlsx"
"""
import csv
import re
import sys

import openpyxl

OUT = "data_jagung.csv"


def find_header(ws):
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        cells = [str(c).strip().lower() if c is not None else "" for c in row]
        if "no" in cells and any(c.startswith("kecamatan") for c in cells):
            return r, cells
    raise ValueError(f"Header tidak ditemukan di sheet {ws.title}")


def col_index(cells, keyword):
    for i, c in enumerate(cells):
        if c.startswith(keyword):
            return i
    raise ValueError(f"Kolom '{keyword}' tidak ditemukan")


def main(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    rows_out = []
    for ws in wb.worksheets:
        tahun = int(ws.title.strip())
        header_row, cells = find_header(ws)
        i_kec = col_index(cells, "kecamatan")
        i_luas = col_index(cells, "luas panen")
        i_prod = col_index(cells, "produksi")
        i_pvt = col_index(cells, "produktivitas")
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            no = row[0]
            if not isinstance(no, (int, float)):
                continue  # lewati baris Total / tanda tangan
            nama = re.sub(r"^\d+\s+", "", str(row[i_kec]).strip())
            rows_out.append([nama, tahun, row[i_luas], row[i_prod], row[i_pvt]])
            count += 1
        print(f"Sheet {tahun}: {count} kecamatan")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nama_kecamatan", "tahun", "luas_panen", "produksi", "produktivitas"])
        w.writerows(rows_out)
    print(f"Tersimpan {len(rows_out)} baris ke {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Dataset Jagung 2018-2025.xlsx")
