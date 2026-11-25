"""Akun pengelola: login, registrasi Operator, dan validasi oleh Admin.

Menggunakan tabel `pengguna` di Supabase (lihat schema_tambahan.sql).
Bila tabel `pengguna` belum dibuat di Supabase, modul ini menyediakan
penyimpanan cadangan di memori agar seluruh fitur (login Admin, registrasi
Operator, dan validasi Operator) tetap dapat langsung diuji.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.]{4,30}$")
MIN_PASSWORD = 6

STATUS_LABEL = {
    "menunggu": "Menunggu Validasi",
    "disetujui": "Disetujui",
    "ditolak": "Ditolak",
    "nonaktif": "Nonaktif",
}

PESAN_STATUS_LOGIN = {
    "menunggu": "Akun Anda masih menunggu validasi Admin.",
    "ditolak": "Pendaftaran akun Anda ditolak oleh Admin.",
    "nonaktif": "Akun Anda sedang dinonaktifkan oleh Admin.",
}

TABEL_BELUM_ADA = (
    "Catatan: Tabel `pengguna` belum dibuat di Supabase (jalankan schema_tambahan.sql "
    "di Supabase SQL Editor agar data akun tersimpan permanen)."
)


def _hash(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Cadangan di memori apabila schema_tambahan.sql belum dijalankan di Supabase
_MEM_USERS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "nama_lengkap": "Administrator SIGAGU",
        "username": "admin",
        "password_hash": "pbkdf2:sha256:1000000$vhLEllsfLQilr2tr$64ad6e79c1c554a8191c8dc2784e922ce7ccc8c02391910271ee69dce13c9e2a",
        "role": "admin",
        "status": "disetujui",
        "dibuat_pada": "2026-11-10T00:00:00+00:00",
        "divalidasi_pada": "2026-11-10T00:00:00+00:00",
    }
]
_MEM_NEXT_ID = 2


def get_user(db, user_id: int) -> Optional[Dict[str, Any]]:
    if db:
        try:
            rows = db.table("pengguna").select("*").eq("id", user_id).execute().data or []
            if rows:
                return rows[0]
        except Exception:
            pass
    return next((u for u in _MEM_USERS if u["id"] == user_id), None)


def authenticate(db, username: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    uname = username.strip().lower()
    user = None

    if db:
        try:
            rows = (
                db.table("pengguna")
                .select("*")
                .eq("username", uname)
                .execute()
                .data
                or []
            )
            user = rows[0] if rows else None
        except Exception:
            user = next((u for u in _MEM_USERS if u["username"] == uname), None)
    else:
        user = next((u for u in _MEM_USERS if u["username"] == uname), None)

    if not user or not check_password_hash(user["password_hash"], password):
        return None, "Username atau password salah."
    if user["status"] != "disetujui":
        return None, PESAN_STATUS_LOGIN.get(user["status"], "Akun tidak dapat digunakan.")
    return user, None


def validate_password(password: str, konfirmasi: str) -> Optional[str]:
    if len(password) < MIN_PASSWORD:
        return f"Password minimal {MIN_PASSWORD} karakter."
    if password != konfirmasi:
        return "Konfirmasi password tidak sama."
    return None


def register_operator(db, nama: str, username: str, password: str, konfirmasi: str) -> Optional[str]:
    """Mengembalikan pesan error, atau None jika pendaftaran berhasil."""
    global _MEM_NEXT_ID
    nama = nama.strip()
    username = username.strip().lower()
    if len(nama) < 3:
        return "Nama lengkap minimal 3 karakter."
    if not USERNAME_PATTERN.match(username):
        return "Username 4–30 karakter, hanya huruf kecil, angka, titik, atau garis bawah."
    error = validate_password(password, konfirmasi)
    if error:
        return error

    if db:
        try:
            exists = db.table("pengguna").select("id").eq("username", username).execute().data
            if exists:
                return "Username sudah digunakan."
            db.table("pengguna").insert({
                "nama_lengkap": nama,
                "username": username,
                "password_hash": _hash(password),
                "role": "operator",
                "status": "menunggu",
            }).execute()
            return None
        except Exception:
            pass

    if any(u["username"] == username for u in _MEM_USERS):
        return "Username sudah digunakan."

    _MEM_USERS.append({
        "id": _MEM_NEXT_ID,
        "nama_lengkap": nama,
        "username": username,
        "password_hash": _hash(password),
        "role": "operator",
        "status": "menunggu",
        "dibuat_pada": _now(),
        "divalidasi_pada": None,
    })
    _MEM_NEXT_ID += 1
    return None


def list_operators(db) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if db:
        try:
            rows = (
                db.table("pengguna")
                .select("id,nama_lengkap,username,status,dibuat_pada,divalidasi_pada")
                .eq("role", "operator")
                .order("dibuat_pada", desc=True)
                .execute()
                .data
                or []
            )
            return rows, None
        except Exception:
            pass

    mem_ops = [u for u in _MEM_USERS if u["role"] == "operator"]
    mem_ops.sort(key=lambda x: x["dibuat_pada"], reverse=True)
    return mem_ops, TABEL_BELUM_ADA


def count_pending(db) -> int:
    if db:
        try:
            rows = (
                db.table("pengguna")
                .select("id")
                .eq("role", "operator")
                .eq("status", "menunggu")
                .execute()
                .data
                or []
            )
            return len(rows)
        except Exception:
            pass
    return sum(1 for u in _MEM_USERS if u["role"] == "operator" and u["status"] == "menunggu")


def set_operator_status(db, user_id: int, status: str) -> None:
    if status not in STATUS_LABEL:
        raise ValueError("Status tidak dikenal.")
    now_str = _now()
    if db:
        try:
            (
                db.table("pengguna")
                .update({"status": status, "divalidasi_pada": now_str})
                .eq("id", user_id)
                .eq("role", "operator")
                .execute()
            )
            return
        except Exception:
            pass
    for u in _MEM_USERS:
        if u["id"] == user_id and u["role"] == "operator":
            u["status"] = status
            u["divalidasi_pada"] = now_str


def delete_operator(db, user_id: int) -> None:
    if db:
        try:
            db.table("pengguna").delete().eq("id", user_id).eq("role", "operator").execute()
            return
        except Exception:
            pass
    _MEM_USERS[:] = [u for u in _MEM_USERS if not (u["id"] == user_id and u["role"] == "operator")]


def reset_password(db, user_id: int, password: str, konfirmasi: str, role: str = "operator") -> None:
    error = validate_password(password, konfirmasi)
    if error:
        raise ValueError(error)
    pw_hash = _hash(password)
    if db:
        try:
            (
                db.table("pengguna")
                .update({"password_hash": pw_hash})
                .eq("id", user_id)
                .eq("role", role)
                .execute()
            )
            return
        except Exception:
            pass
    for u in _MEM_USERS:
        if u["id"] == user_id and u["role"] == role:
            u["password_hash"] = pw_hash


def change_own_password(db, user_id: int, lama: str, baru: str, konfirmasi: str) -> None:
    user = get_user(db, user_id)
    if not user or not check_password_hash(user["password_hash"], lama):
        raise ValueError("Password lama salah.")
    error = validate_password(baru, konfirmasi)
    if error:
        raise ValueError(error)
    pw_hash = _hash(baru)
    if db:
        try:
            db.table("pengguna").update({"password_hash": pw_hash}).eq("id", user_id).execute()
            return
        except Exception:
            pass
    for u in _MEM_USERS:
        if u["id"] == user_id:
            u["password_hash"] = pw_hash
