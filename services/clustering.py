"""Model K-Medoids (PAM) SIGAGU: hasil akhir klaster, medoid, dan Silhouette Coefficient.

Algoritma identik dengan perhitungan manual Excel dan Notebook Colab (2018-2025):
  1. Normalisasi Min-Max per tahun ke rentang [0, 1].
  2. Matriks jarak Euclidean 33 x 33.
  3. Fase BUILD : pemilihan k medoid awal secara greedy (deterministik).
  4. Fase SWAP  : pertukaran medoid dengan non-medoid hingga biaya tidak turun lagi.
  5. Silhouette Coefficient dihitung manual dari matriks jarak yang sama.

Urutan 33 kecamatan mengikuti urutan kanonik dataset tahunan (2018-2022 dan
2023-2025) agar tie-breaking BUILD/SWAP identik dengan Excel dan Colab.

Titik masuk dari sistem: cluster_year(rows, k=3, tahun=None). Penomoran
Klaster 1/2/3 (Tinggi/Sedang/Rendah) ditentukan di services/data_service.py.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

K_FINAL_DEFAULT: int = 3
FITUR: List[str] = ["luas_panen", "produksi", "produktivitas"]

URUTAN_KECAMATAN_2018_2022: List[str] = [
    "Donomulyo", "Pagak", "Bantur", "Sumbermanjing Wetan", "Dampit",
    "Ampelgading", "Poncokusumo", "Wajak", "Turen", "Gondanglegi",
    "Kalipare", "Sumberpucung", "Kepanjen", "Bululawang", "Tajinan",
    "Tumpang", "Jabung", "Pakis", "Pakisaji", "Ngajum",
    "Wagir", "Dau", "Karangploso", "Singosari", "Lawang",
    "Pujon", "Ngantang", "Kasembon", "Gedangan", "Tirtoyudo",
    "Kromengan", "Wonosari", "Pagelaran",
]

URUTAN_KECAMATAN_2023_2025: List[str] = [
    "Donomulyo", "Kalipare", "Pagak", "Bantur", "Gedangan",
    "Sumbermanjing Wetan", "Dampit", "Tirtoyudo", "Ampelgading", "Poncokusumo",
    "Wajak", "Turen", "Bululawang", "Gondanglegi", "Pagelaran",
    "Kepanjen", "Sumberpucung", "Kromengan", "Ngajum", "Wonosari",
    "Wagir", "Pakisaji", "Tajinan", "Tumpang", "Pakis",
    "Jabung", "Lawang", "Singosari", "Karangploso", "Dau",
    "Pujon", "Ngantang", "Kasembon",
]


# ---------------------------------------------------------------------------
# Fungsi matematis inti
# ---------------------------------------------------------------------------
def minmax_manual(X: np.ndarray) -> np.ndarray:
    """x' = (x - min) / (max - min) per kolom."""
    x_min = X.min(axis=0)
    rentang = X.max(axis=0) - x_min
    if (rentang == 0).any():
        raise ValueError("Variasi data tidak cukup: ada variabel yang nilainya konstan.")
    return (X - x_min) / rentang


def hitung_matriks_jarak(X: np.ndarray) -> np.ndarray:
    """Jarak Euclidean n x n."""
    n = X.shape[0]
    D = np.zeros((n, n), dtype=float)
    for p in range(n):
        D[p] = np.sqrt(np.sum((X[p] - X) ** 2, axis=1))
    return D


def hitung_biaya(D: np.ndarray, medoid: Sequence[int]) -> float:
    """Total dissimilarity J(M) = sum_i min_{m in M} d(i, m)."""
    return float(D[:, list(medoid)].min(axis=1).sum())


def pam_build(D: np.ndarray, k: int) -> List[int]:
    """Fase BUILD: k medoid awal secara greedy dan deterministik."""
    medoid = [int(np.argmin(D.sum(axis=1)))]
    while len(medoid) < k:
        d_terdekat = D[:, medoid].min(axis=1)
        gain = np.maximum(d_terdekat[:, None] - D, 0).sum(axis=0)
        gain[medoid] = -np.inf
        medoid.append(int(np.argmax(gain)))
    return medoid


def pam_swap(D: np.ndarray, medoid: Sequence[int], max_iter: int = 100) -> Tuple[List[int], float, int]:
    """Fase SWAP: tukar medoid dengan non-medoid selama biaya J(M) masih turun."""
    n = D.shape[0]
    medoid_aktif = list(medoid)
    k = len(medoid_aktif)
    biaya = hitung_biaya(D, medoid_aktif)

    for iterasi in range(1, max_iter + 1):
        biaya_terbaik = biaya
        tukar_terbaik: Optional[Tuple[int, int]] = None
        for posisi in range(k):
            for h in range(n):
                if h in medoid_aktif:
                    continue
                kandidat = medoid_aktif.copy()
                kandidat[posisi] = h
                biaya_kandidat = hitung_biaya(D, kandidat)
                if biaya_kandidat < biaya_terbaik - 1e-12:
                    biaya_terbaik = biaya_kandidat
                    tukar_terbaik = (posisi, h)

        if tukar_terbaik is None:
            return medoid_aktif, biaya, iterasi - 1

        posisi, h = tukar_terbaik
        medoid_aktif[posisi] = h
        biaya = biaya_terbaik

    return medoid_aktif, biaya, max_iter


def silhouette_manual(D: np.ndarray, labels: Sequence[int]) -> float:
    """Rata-rata Silhouette Coefficient s(i) = (b - a) / max(a, b)."""
    labels_arr = np.asarray(labels, dtype=int)
    n = len(labels_arr)
    daftar_klaster = np.unique(labels_arr)
    s_arr = np.zeros(n, dtype=float)

    for i in range(n):
        sendiri = labels_arr == labels_arr[i]
        n_sendiri = int(sendiri.sum())
        if n_sendiri <= 1:
            continue
        a = float(D[i, sendiri].sum() / (n_sendiri - 1))
        b = min(
            float(D[i, labels_arr == c].mean())
            for c in daftar_klaster
            if c != labels_arr[i]
        )
        penyebut = max(a, b)
        s_arr[i] = 0.0 if penyebut == 0 else (b - a) / penyebut

    return float(s_arr.mean())


# ---------------------------------------------------------------------------
# Titik masuk untuk sistem
# ---------------------------------------------------------------------------
def _norm_nama(nama: Any) -> str:
    teks = str(nama or "").strip()
    bagian = teks.split(maxsplit=1)
    if len(bagian) == 2 and bagian[0].isdigit():  # buang kode angka, mis. "010 Donomulyo"
        teks = bagian[1]
    return teks.lower()


def _urutan_kanonik(rows: Sequence[Dict[str, Any]], tahun: Optional[int]) -> List[int]:
    """Indeks baris rows yang diurutkan sesuai urutan kanonik Excel untuk tahun tersebut."""
    if tahun is None or not all("kecamatan" in r for r in rows):
        return list(range(len(rows)))

    daftar = URUTAN_KECAMATAN_2018_2022 if int(tahun) <= 2022 else URUTAN_KECAMATAN_2023_2025
    posisi = {nama.lower(): i for i, nama in enumerate(daftar)}
    return sorted(
        range(len(rows)),
        key=lambda i: (posisi.get(_norm_nama(rows[i]["kecamatan"]), 999), i),
    )


def cluster_year(rows: Sequence[Dict[str, Any]], k: int = K_FINAL_DEFAULT,
                 tahun: Optional[int] = None) -> Dict[str, Any]:
    """Menjalankan K-Medoids PAM untuk satu tahun.

    rows : list dict berisi kecamatan_id, luas_panen, produksi, produktivitas
           (dan `kecamatan` = nama, agar urutan sama dengan Excel).
    Mengembalikan:
      labels               : label mentah 0..k-1, selaras dengan urutan `rows`
      medoid_kecamatan_ids : kecamatan_id tiap medoid
      silhouette           : rata-rata Silhouette Coefficient
      total_dissimilarity  : biaya akhir J(M)
    """
    if len(rows) < k:
        raise ValueError(f"Jumlah data kecamatan ({len(rows)}) kurang dari nilai k ({k}).")

    X = np.array([[float(r[f]) for f in FITUR] for r in rows], dtype=float)
    if not np.isfinite(X).all() or (X < 0).any():
        raise ValueError("Data mengandung nilai kosong, tidak valid, atau negatif.")

    urutan = _urutan_kanonik(rows, tahun)
    X_norm = minmax_manual(X[urutan])
    D = hitung_matriks_jarak(X_norm)

    medoid_awal = pam_build(D, k)
    medoid, biaya, _ = pam_swap(D, medoid_awal)
    medoid = sorted(medoid)

    labels_urut = np.argmin(D[:, medoid], axis=1)
    if len(set(labels_urut.tolist())) < 2:
        raise ValueError("Model menghasilkan kurang dari dua klaster.")

    # Kembalikan label ke urutan asli `rows`
    labels = np.zeros(len(rows), dtype=int)
    for pos_urut, idx_asli in enumerate(urutan):
        labels[idx_asli] = labels_urut[pos_urut]

    return {
        "labels": labels,
        "medoid_kecamatan_ids": [int(rows[urutan[m]]["kecamatan_id"]) for m in medoid],
        "silhouette": silhouette_manual(D, labels_urut),
        "total_dissimilarity": float(biaya),
    }
