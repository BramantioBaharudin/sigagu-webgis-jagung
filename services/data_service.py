"""Lapisan data untuk tampilan SIGAGU.

Membaca data dari Supabase dan menyiapkannya untuk template:
- menggabungkan data_jagung + hasil_clustering + kecamatan,
- mengurutkan nomor klaster berdasarkan rata-rata produksi (hanya untuk tampilan),
- menyusun profil rata-rata dan ringkasan otomatis tiap klaster,
- membaca/menyimpan pengaturan peta dan penjelasan klaster.

Model clustering ada di services/clustering.py dan tidak diubah oleh modul ini.
"""
import os
from typing import Any, Dict, List, Optional

from supabase import create_client

YEARS = list(range(2018, 2026))

# Jumlah klaster (k) yang boleh dipilih. Bawaan 3 bila tidak diisi.
MIN_K = 2
MAX_K = 5
DEFAULT_K = 3
KLASTER_IDS = list(range(1, MAX_K + 1))  # nomor klaster maksimum (untuk form penjelasan)

# Warna & tingkat klaster per k, berurutan dari produksi tertinggi ke terendah.
WARNA_PER_K: Dict[int, List[str]] = {
    2: ["#15803d", "#ea580c"],
    3: ["#15803d", "#a3e635", "#ea580c"],
    4: ["#15803d", "#a3e635", "#facc15", "#dc2626"],
    5: ["#15803d", "#a3e635", "#facc15", "#ea580c", "#dc2626"],
}
TINGKAT_PER_K: Dict[int, List[str]] = {
    2: ["Tinggi", "Rendah"],
    3: ["Tinggi", "Sedang", "Rendah"],
    4: ["Sangat Tinggi", "Tinggi", "Sedang", "Rendah"],
    5: ["Sangat Tinggi", "Tinggi", "Sedang", "Rendah", "Sangat Rendah"],
}
LABEL_K3 = [
    "Klaster 1: Produksi Tinggi (Sentra Utama)",
    "Klaster 2: Produksi Sedang (Potensial)",
    "Klaster 3: Produksi Rendah (Non-Sentra)",
]


def default_map_config(k: int = DEFAULT_K) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {"k": k}
    for n in range(1, k + 1):
        cfg[f"c{n}_color"] = WARNA_PER_K[k][n - 1]
        cfg[f"c{n}_label"] = (
            LABEL_K3[n - 1] if k == 3 else f"Klaster {n}: Produksi {TINGKAT_PER_K[k][n - 1]}"
        )
    return cfg


def warna_klaster(k: Optional[int], nomor: int) -> str:
    """Warna bawaan klaster `nomor` untuk jumlah klaster k (dipakai di template)."""
    palet = WARNA_PER_K.get(k or DEFAULT_K, WARNA_PER_K[DEFAULT_K])
    return palet[nomor - 1] if 1 <= nomor <= len(palet) else "#cbd5e1"


def validasi_k(nilai: Any) -> int:
    """Kosong -> 3. Selain itu harus bilangan bulat MIN_K..MAX_K."""
    teks = str(nilai if nilai is not None else "").strip()
    if not teks:
        return DEFAULT_K
    try:
        k = int(teks)
    except ValueError:
        raise ValueError(f"Nilai k harus berupa bilangan bulat {MIN_K}–{MAX_K}.")
    if not MIN_K <= k <= MAX_K:
        raise ValueError(f"Nilai k harus antara {MIN_K} dan {MAX_K}.")
    return k


# Penyimpanan cadangan di memori jika tabel di schema_k_dinamis.sql belum dijalankan
_MEM_MAP_CONFIG: Dict[int, Dict[str, str]] = {}
_MEM_KETERANGAN: Dict[int, Dict[int, str]] = {}

VARIABEL = [
    ("produksi", "Produksi", "Ton"),
    ("luas_panen", "Luas panen", "Ha"),
    ("produktivitas", "Produktivitas", "Kw/Ha"),
]


def get_db():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


# ---------------------------------------------------------------------
# Kecamatan & data pertanian
# ---------------------------------------------------------------------
def get_kecamatan(db) -> List[Dict[str, Any]]:
    if not db:
        return []
    try:
        return (
            db.table("kecamatan")
            .select("id,kode_kecamatan,nama_kecamatan")
            .order("nama_kecamatan")
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def load_records(db) -> List[Dict[str, Any]]:
    """Seluruh data pertanian 2018-2025 beserta hasil clustering (jika ada).

    Nomor `klaster` (1-3) diurutkan per tahun dari rata-rata produksi tertinggi
    ke terendah. Bernilai None jika tahun tersebut belum diproses.
    """
    if not db:
        return []

    kecamatan = get_kecamatan(db)
    nama_by_id = {int(k["id"]): k["nama_kecamatan"] for k in kecamatan}

    try:
        data_rows = (
            db.table("data_jagung")
            .select("kecamatan_id,tahun,luas_panen,produksi,produktivitas")
            .execute()
            .data
            or []
        )
    except Exception:
        return []

    try:
        hasil_rows = (
            db.table("hasil_clustering")
            .select("tahun,kecamatan_id,cluster_label,is_medoid,silhouette,produksi")
            .execute()
            .data
            or []
        )
    except Exception:
        hasil_rows = []

    hasil_by_key = {
        (int(h["tahun"]), int(h["kecamatan_id"])): h for h in hasil_rows
    }
    urutan = _urutan_klaster_per_tahun(hasil_rows)

    records = []
    for d in data_rows:
        tahun = int(d["tahun"])
        kid = int(d["kecamatan_id"])
        hasil = hasil_by_key.get((tahun, kid))

        klaster = None
        is_medoid = False
        silhouette = None
        if hasil:
            klaster = urutan.get(tahun, {}).get(int(hasil["cluster_label"]))
            is_medoid = bool(hasil.get("is_medoid"))
            silhouette = float(hasil["silhouette"])

        records.append({
            "kecamatan_id": kid,
            "kecamatan": nama_by_id.get(kid, f"Kecamatan {kid}"),
            "tahun": tahun,
            "luas_panen": float(d["luas_panen"]),
            "produksi": float(d["produksi"]),
            "produktivitas": float(d["produktivitas"]),
            "klaster": klaster,
            "k": len(urutan[tahun]) if tahun in urutan else None,
            "is_medoid": is_medoid,
            "silhouette": silhouette,
        })

    records.sort(key=lambda r: (r["tahun"], r["kecamatan"]))
    return records


def _urutan_klaster_per_tahun(hasil_rows) -> Dict[int, Dict[int, int]]:
    """{tahun: {label_asli: nomor_klaster}} berdasarkan rata-rata produksi."""
    produksi: Dict[int, Dict[int, List[float]]] = {}
    for h in hasil_rows:
        tahun = int(h["tahun"])
        label = int(h["cluster_label"])
        produksi.setdefault(tahun, {}).setdefault(label, []).append(
            float(h.get("produksi") or 0)
        )

    return {
        tahun: {
            label: nomor + 1
            for nomor, label in enumerate(
                sorted(per_label, key=lambda l: -_mean(per_label[l]))
            )
        }
        for tahun, per_label in produksi.items()
    }


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def records_for_year(records, tahun: int) -> List[Dict[str, Any]]:
    return [r for r in records if r["tahun"] == tahun]


def history_for_kecamatan(records, kecamatan_id: int) -> List[Dict[str, Any]]:
    return sorted(
        [r for r in records if r["kecamatan_id"] == kecamatan_id],
        key=lambda r: r["tahun"],
    )


# ---------------------------------------------------------------------
# Profil klaster & ringkasan otomatis
# ---------------------------------------------------------------------
def year_k(year_records) -> int:
    """Jumlah klaster yang dipakai pada hasil satu tahun (bawaan 3 bila belum diproses)."""
    nomor = {r["klaster"] for r in year_records if r["klaster"] is not None}
    return len(nomor) if nomor else DEFAULT_K


def cluster_profiles(year_records) -> List[Dict[str, Any]]:
    """Profil rata-rata tiap klaster pada satu tahun + ringkasan otomatis."""
    profiles = []
    for k in range(1, year_k(year_records) + 1):
        anggota = [r for r in year_records if r["klaster"] == k]
        if not anggota:
            continue
        profiles.append({
            "klaster": k,
            "jumlah": len(anggota),
            "anggota": [r["kecamatan"] for r in anggota],
            "medoid": [r["kecamatan"] for r in anggota if r["is_medoid"]],
            "luas_panen": _mean([r["luas_panen"] for r in anggota]),
            "produksi": _mean([r["produksi"] for r in anggota]),
            "produktivitas": _mean([r["produktivitas"] for r in anggota]),
        })

    for p in profiles:
        p["ringkasan"] = _ringkasan(p, profiles)
    return profiles


def _ringkasan(profile, profiles) -> str:
    if len(profiles) < 2:
        return "Belum dapat dibandingkan (hanya satu klaster)."

    bagian = []
    for field, nama, _ in VARIABEL:
        urut = sorted(profiles, key=lambda p: -p[field])
        posisi = next(i for i, p in enumerate(urut) if p["klaster"] == profile["klaster"])
        if posisi == 0:
            tingkat = "tertinggi"
        elif posisi == len(urut) - 1:
            tingkat = "terendah"
        else:
            tingkat = "menengah"
        bagian.append(f"{nama} {tingkat}")

    teks = ", ".join(bagian)
    return teks[0].upper() + teks[1:] + "."


def yearly_summary(records) -> Dict[int, Dict[str, Any]]:
    """Ringkasan per tahun: Silhouette, jumlah anggota tiap klaster, medoid."""
    summary = {}
    for tahun in YEARS:
        rows = records_for_year(records, tahun)
        diproses = [r for r in rows if r["klaster"] is not None]
        k = year_k(rows) if diproses else None
        counts = [
            sum(1 for r in diproses if r["klaster"] == n) for n in range(1, (k or 0) + 1)
        ]
        summary[tahun] = {
            "jumlah_data": len(rows),
            "diproses": bool(diproses),
            "k": k,
            "counts": counts,
            "silhouette": diproses[0]["silhouette"] if diproses else None,
            "c1": counts[0] if len(counts) > 0 else 0,
            "c2": counts[1] if len(counts) > 1 else 0,
            "c3": counts[2] if len(counts) > 2 else 0,
            "c4": counts[3] if len(counts) > 3 else 0,
            "c5": counts[4] if len(counts) > 4 else 0,
            "medoid": [r["kecamatan"] for r in diproses if r["is_medoid"]],
        }
    return summary


# ---------------------------------------------------------------------
# Pengaturan peta & penjelasan klaster
# ---------------------------------------------------------------------
def get_map_config(db, k: int = DEFAULT_K) -> Dict[str, Any]:
    """Warna & label klaster untuk k tertentu: bawaan -> memori -> database."""
    cfg = default_map_config(k)
    cfg.update(_MEM_MAP_CONFIG.get(k, {}))
    if not db:
        return cfg
    try:
        rows = (
            db.table("pengaturan_klaster").select("nomor,warna,label").eq("k", k).execute().data or []
        )
        for r in rows:
            n = int(r["nomor"])
            if 1 <= n <= k:
                if r.get("warna"):
                    cfg[f"c{n}_color"] = r["warna"]
                if r.get("label"):
                    cfg[f"c{n}_label"] = r["label"]
        if rows:
            _MEM_MAP_CONFIG[k] = {key: v for key, v in cfg.items() if key != "k"}
            return cfg
    except Exception:
        pass

    # Kompatibilitas: pengaturan lama (3 klaster) di tabel pengaturan_peta
    if k == 3:
        try:
            rows = db.table("pengaturan_peta").select("*").eq("id", 1).execute().data or []
            if rows:
                for key in default_map_config(3):
                    if key != "k" and rows[0].get(key):
                        cfg[key] = rows[0][key]
        except Exception:
            pass
    return cfg


def save_map_config(db, form, k: int = DEFAULT_K) -> bool:
    """Mengembalikan True jika tersimpan di Supabase, False jika hanya di memori."""
    default = default_map_config(k)
    mem: Dict[str, str] = {}
    payload = []
    for n in range(1, k + 1):
        warna = (form.get(f"c{n}_color") or default[f"c{n}_color"]).strip()
        label = (form.get(f"c{n}_label") or default[f"c{n}_label"]).strip()
        mem[f"c{n}_color"] = warna
        mem[f"c{n}_label"] = label
        payload.append({"k": k, "nomor": n, "warna": warna, "label": label})
    _MEM_MAP_CONFIG[k] = mem
    if not db:
        return False
    try:
        db.table("pengaturan_klaster").upsert(payload, on_conflict="k,nomor").execute()
        return True
    except Exception:
        return False

def get_keterangan(db, tahun: int) -> Dict[int, str]:
    mem = dict(_MEM_KETERANGAN.get(tahun, {}))
    if not db:
        return mem
    try:
        rows = (
            db.table("keterangan_klaster")
            .select("klaster,keterangan")
            .eq("tahun", tahun)
            .execute()
            .data
            or []
        )
        res = {int(r["klaster"]): r["keterangan"] for r in rows}
        _MEM_KETERANGAN[tahun] = dict(res)
        return res
    except Exception:
        return mem


def save_keterangan(db, tahun: int, form) -> bool:
    """Mengembalikan True jika tersimpan di Supabase, False jika hanya di memori."""
    _MEM_KETERANGAN.setdefault(tahun, {})
    for k in KLASTER_IDS:
        teks = (form.get(f"keterangan_{k}") or "").strip()
        if teks:
            _MEM_KETERANGAN[tahun][k] = teks
        else:
            _MEM_KETERANGAN[tahun].pop(k, None)

    if not db:
        return False
    try:
        for k in KLASTER_IDS:
            teks = (form.get(f"keterangan_{k}") or "").strip()
            if teks:
                db.table("keterangan_klaster").upsert(
                    {"tahun": tahun, "klaster": k, "keterangan": teks},
                    on_conflict="tahun,klaster",
                ).execute()
            else:
                db.table("keterangan_klaster").delete().eq("tahun", tahun).eq("klaster", k).execute()
        return True
    except Exception:
        return False


def legend_items(map_config, profiles, keterangan) -> List[Dict[str, Any]]:
    """Item legenda untuk Homepage & Pemetaan: warna, label, penjelasan, profil."""
    by_k = {p["klaster"]: p for p in profiles}
    items = []
    for k in range(1, int(map_config.get("k", DEFAULT_K)) + 1):
        profil = by_k.get(k)
        manual = keterangan.get(k, "")
        items.append({
            "klaster": k,
            "warna": map_config[f"c{k}_color"],
            "label": map_config[f"c{k}_label"],
            "profil": profil,
            "ringkasan": profil["ringkasan"] if profil else "",
            "manual": manual,
            "penjelasan": manual or (profil["ringkasan"] if profil else ""),
        })
    return items


# ---------------------------------------------------------------------
# Data pertanian (tulis)
# ---------------------------------------------------------------------
def parse_data_form(form) -> Dict[str, Any]:
    tahun = int(form["tahun"])
    payload = {
        "kecamatan_id": int(form["kecamatan_id"]),
        "tahun": tahun,
        "luas_panen": float(form["luas_panen"]),
        "produksi": float(form["produksi"]),
        "produktivitas": float(form["produktivitas"]),
    }
    if tahun not in YEARS:
        raise ValueError("Tahun harus antara 2018 dan 2025.")
    if min(payload["luas_panen"], payload["produksi"], payload["produktivitas"]) < 0:
        raise ValueError("Nilai tidak boleh negatif.")
    return payload


def upsert_data(db, payload) -> None:
    if isinstance(payload, dict):
        payload = [payload]
    db.table("data_jagung").upsert(payload, on_conflict="kecamatan_id,tahun").execute()


def update_data(db, payload) -> None:
    db.table("data_jagung").update({
        "luas_panen": payload["luas_panen"],
        "produksi": payload["produksi"],
        "produktivitas": payload["produktivitas"],
    }).eq("kecamatan_id", payload["kecamatan_id"]).eq("tahun", payload["tahun"]).execute()


def delete_data(db, kecamatan_id: int, tahun: int) -> None:
    db.table("hasil_clustering").delete().eq("kecamatan_id", kecamatan_id).eq("tahun", tahun).execute()
    db.table("data_jagung").delete().eq("kecamatan_id", kecamatan_id).eq("tahun", tahun).execute()


# ---------------------------------------------------------------------
# Menjalankan model clustering (satu titik pemanggilan)
# ---------------------------------------------------------------------
def run_clustering(db, tahun: int, k: int = DEFAULT_K) -> None:
    """Memanggil model di services/clustering.py dengan jumlah klaster k, lalu menyimpan hasilnya."""
    from services.clustering import cluster_year

    k = validasi_k(k)
    rows = (
        db.table("data_jagung")
        .select("kecamatan_id,luas_panen,produksi,produktivitas")
        .eq("tahun", tahun)
        .execute()
        .data
        or []
    )
    if len(rows) != 33:
        raise ValueError(f"Tahun {tahun} memiliki {len(rows)} baris; dibutuhkan 33 kecamatan.")

    # Nama kecamatan dibutuhkan model agar urutan data sama dengan Excel
    nama_by_id = {int(k["id"]): k["nama_kecamatan"] for k in get_kecamatan(db)}
    rows_model = [
        {**r, "kecamatan": nama_by_id.get(int(r["kecamatan_id"]), "")} for r in rows
    ]
    result = cluster_year(rows_model, k=k, tahun=tahun)

    payload = []
    for i, row in enumerate(rows):
        payload.append({
            "tahun": tahun,
            "kecamatan_id": int(row["kecamatan_id"]),
            "cluster_label": int(result["labels"][i]),
            "is_medoid": int(row["kecamatan_id"]) in result["medoid_kecamatan_ids"],
            "luas_panen": float(row["luas_panen"]),
            "produksi": float(row["produksi"]),
            "produktivitas": float(row["produktivitas"]),
            "silhouette": result["silhouette"],
            # Kolom wajib di schema.sql; DBI tidak dipakai (selalu 0) dan tidak ditampilkan.
            "dbi": 0.0,
            "total_dissimilarity": result.get("total_dissimilarity", 0.0),
        })

    # TODO produksi: ganti delete+insert dengan transaksi/RPC atomik.
    k_lama = None
    try:
        lama = db.table("hasil_clustering").select("cluster_label").eq("tahun", tahun).execute().data or []
        k_lama = len({int(x["cluster_label"]) for x in lama}) or None
    except Exception:
        pass

    # Gunakan upsert terlebih dahulu agar data lama tahun tersebut TIDAK hilang jika constraint DB menolak
    try:
        db.table("hasil_clustering").upsert(payload, on_conflict="tahun,kecamatan_id").execute()
    except Exception as exc:
        if "hasil_clustering_cluster_label_check" in str(exc):
            raise ValueError(
                "Database belum mendukung k > 3 (cluster_label masih dibatasi 0–2). "
                "Silakan jalankan isi file schema_k_dinamis.sql di Supabase SQL Editor terlebih dahulu."
            ) from exc
        raise

    # Penjelasan manual klaster tidak lagi relevan bila jumlah klaster berubah
    if k_lama is not None and k_lama != k:
        _MEM_KETERANGAN.pop(tahun, None)
        try:
            db.table("keterangan_klaster").delete().eq("tahun", tahun).execute()
        except Exception:
            pass
