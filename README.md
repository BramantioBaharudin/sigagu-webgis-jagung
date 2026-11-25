# Web GIS Jagung — Flask Starter

## Teknologi
- Flask + Jinja, HTML/CSS/JavaScript
- Supabase PostgreSQL
- K-Medoids PAM (scikit-learn-extra)
- Leaflet + GeoJSON

## Menjalankan lokal
1. Buat virtual environment dan aktifkan.
2. `pip install -r requirements.txt`
3. Salin `.env.example` menjadi `.env`, isi semua variabel.
4. Jalankan `schema.sql` di Supabase SQL Editor.
5. Masukkan 33 kecamatan pada tabel `kecamatan`, lalu data jagung.
6. Jalankan `python app.py`, buka `http://127.0.0.1:5000`.

Jangan commit `.env` ke GitHub. Service role key hanya boleh digunakan di backend, jangan pernah di frontend.

## GeoJSON
Tambahkan `static/geojson/kecamatan.geojson`. Setiap feature perlu memiliki properti `kecamatan_id` yang cocok dengan `kecamatan.id` di Supabase. Gunakan GeoJSON WGS84/EPSG:4326.

## Batasan starter
- Impor Excel/CSV dan edit/hapus data belum dibuat.
- Login menggunakan satu set kredensial dari environment variables; ini prototipe, belum sistem multi-akun produksi.
- Proses clustering memeriksa tepat 33 baris per tahun.
- Operasi simpan hasil menggunakan delete lalu insert; sebelum deployment publik, ganti dengan transaksi/RPC atomik agar hasil lama tidak hilang bila penyimpanan gagal.
- Interpretasi kelas gabungan tiga variabel belum diterapkan karena aturan matematisnya perlu disepakati.
- Uji kompatibilitas scikit-learn-extra, NumPy, dan versi Python sebelum deployment.
- Vercel perlu diuji untuk kompatibilitas Python Functions, dependensi, dan batas waktu eksekusi.
- Tambahkan CSRF protection, validasi keamanan, dan kebijakan RLS sebelum produksi.
