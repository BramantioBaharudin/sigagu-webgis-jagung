# PROJECT_CONTEXT.md — SIGAGU (WebGIS Clustering Produksi Jagung Kab. Malang)

Dokumentasi peta konteks arsitektur (context map) untuk agen AI / MCP. Padat, teknis, dan hemat token.

---

## 1. Tech Stack & Environment

### Backend & Machine Learning
- **Bahasa**: Python 3.10+
- **Web Framework**: `Flask >=3.0, <4.0` (Jinja2 SSR + REST JSON API)
- **Database Client**: `supabase >=2.0` (PostgreSQL via Supabase PostgREST API)
- **Machine Learning / AI**:
  - `numpy >=1.26`
  - `scikit-learn >=1.4, <1.10` (`MinMaxScaler`, `silhouette_score`, `davies_bouldin_score`)
  - `scikit-learn-extra >=0.3.0` (`KMedoids` metode PAM)
- **Data & Utilitas**: `openpyxl` (baca `.xlsx`), `python-dotenv >=1.0`, `werkzeug.security` (hash password `pbkdf2:sha256`), `httpx` (unduh GADM di script utilitas)

### Frontend
- **Styling**: Tailwind CSS (via CDN) + custom stylesheet `static/css/harvest_theme.css` (tema *Harvest Earthy Green & Corn Gold*)
- **GIS / Peta**: Leaflet.js 1.9.4 + OpenStreetMap TileLayer + poligon GeoJSON 33 Kecamatan Kab. Malang (GADM v4.1)
- **Visualisasi Grafik**: Chart.js (grafik garis multi-tahun produksi, luas panen, produktivitas, dan Silhouette Coefficient)
- **Typography**: Google Fonts (`Plus Jakarta Sans`)

### Konfigurasi Environment (`.env`)
| Variabel | Fungsi | Default / Contoh |
| :--- | :--- | :--- |
| `FLASK_SECRET_KEY` | Secret key penandatanganan cookie `session` Flask | `change-this-secret` |
| `FLASK_DEBUG` | Mode debug server pengembangan (`true`/`false`) | `true` |
| `SUPABASE_URL` | Endpoint project Supabase | `https://PROJECT_ID.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Kunci Service Role Supabase (hanya diakses di sisi server) | `eyJ...` |

- **Batas Upload**: `MAX_CONTENT_LENGTH = 5 MB` (diatur di `app.py`).
- **Rentang Tahun Aktif**: `2018` s.d. `2025` (`YEARS = list(range(2018, 2026))`), jumlah wilayah wajib **33 kecamatan** per tahun untuk eksekusi clustering.

---

## 2. Directory Tree (Inti)

```text
webgis-jagung-flask/
├── app.py                        # Entrypoint Flask: routing publik/auth/admin/operator, decorator RBAC, context processor, dan endpoint JSON API.
├── requirements.txt              # Daftar dependensi paket Python dan batasan versinya.
├── .env.example                  # Template variabel environment untuk koneksi Flask dan Supabase.
├── schema.sql                    # DDL tabel inti Supabase: kecamatan, data_jagung, dan hasil_clustering.
├── schema_tambahan.sql           # DDL tabel tambahan SIGAGU: pengguna, pengaturan_peta, dan keterangan_klaster beserta seed Admin.
├── seed_kecamatan.sql            # Seed 33 kecamatan Kabupaten Malang (kode Kemendagri 35.07.01 - 35.07.33).
├── convert_excel.py              # Script CLI konversi file Excel multi-sheet (2018–2025) menjadi data_jagung.csv.
├── import_data.py                # Script CLI bulk upsert data_jagung.csv ke tabel data_jagung di Supabase.
├── build_geojson.py              # Script CLI ekstraksi batas 33 kecamatan Kab. Malang dari GADM v4.1 ke kecamatan.geojson.
├── services/
│   ├── auth_service.py           # Logika autentikasi, registrasi operator, validasi akun oleh Admin, ganti/reset password, plus fallback in-memory.
│   ├── clustering.py             # Modul AI/ML inti: normalisasi MinMaxScaler dan pengelompokan K-Medoids (PAM, k=3, Euclidean).
│   ├── data_service.py           # Orkestrasi query/mutasi Supabase, pengurutan label klaster (1=Tinggi, 2=Sedang, 3=Rendah), profil & legenda klaster.
│   └── import_service.py         # Parser upload file dataset (.csv dan .xlsx) dari halaman Admin beserta validasi baris.
├── static/
│   ├── css/harvest_theme.css     # Stylesheet komponen kartu, tombol, badge klaster, dan tata letak tema SIGAGU.
│   ├── js/map_gis.js             # Modul peta Leaflet: fetch GeoJSON + API map-data, pewarnaan poligon klaster, tooltip, dan event klik kecamatan.
│   └── geojson/kecamatan.geojson # Poligon batas wilayah 33 kecamatan Kab. Malang dengan properti kecamatan_id.
└── templates/
    ├── base_public.html          # Layout induk halaman publik (navbar publik, flash alert, footer, load CDN).
    ├── index.html                # Halaman utama publik: peta interaktif, kartu detail kecamatan, legenda klaster, grafik tren & tabel riwayat.
    ├── auth/
    │   ├── login.html            # Halaman login terpadu satu pintu untuk Admin dan Operator.
    │   ├── register.html         # Halaman pendaftaran mandiri calon Operator (status awal: menunggu validasi).
    │   └── ganti_password.html   # Halaman ubah password akun sendiri untuk Admin maupun Operator.
    ├── admin/
    │   ├── layout_admin.html     # Layout panel Admin dengan sidebar navigasi dan badge jumlah operator menunggu validasi.
    │   ├── dashboard.html        # Ringkasan KPI Admin, grafik Silhouette Coefficient 2018–2025, dan tabel distribusi klaster.
    │   ├── data_pertanian.html   # Manajemen CRUD penuh data jagung (tambah, edit, hapus, dan import CSV/XLSX).
    │   ├── clustering.html       # Eksekusi K-Medoids per tahun/semua tahun, kartu profil klaster, medoid, dan tabel hasil.
    │   ├── pemetaan.html         # Pratinjau peta GIS Admin beserta form kustomisasi warna/label legenda dan penjelasan manual klaster.
    │   └── validasi_operator.html# Manajemen akun Operator: setujui, tolak, nonaktifkan, aktifkan, reset password, dan hapus.
    └── operator/
        ├── layout_operator.html  # Layout panel Operator dengan sidebar khusus hak akses Operator.
        ├── dashboard.html        # Ringkasan KPI Operator dan grafik tren Silhouette Coefficient 2018–2025.
        ├── data_pertanian.html   # Tabel data pertanian untuk Operator (hanya lihat & edit nilai; tanpa tambah/hapus/import).
        ├── clustering.html       # Eksekusi ulang K-Medoids dan tampilan hasil pengelompokan untuk Operator.
        └── pemetaan.html         # Peta GIS interaktif dan legenda klaster mode baca untuk Operator.
```

---

## 3. Arsitektur & Data Flow

1. **Request & Routing (`app.py`)**:
   - Request HTTP masuk ke `app.py`.
   - Route berproteksi melewati decorator `@login_required(role)` yang memverifikasi `session["user_id"]`, mengecek status akun (`status == 'disetujui'`) di `auth_service.get_user()`, dan memastikan kecocokan `role` (`admin` atau `operator`).
   - Context processor `inject_globals()` menyuntikkan `current_user`, `pending_operator`, `db_ready`, dan `status_label` ke seluruh template Jinja2.
2. **Service Layer (`services/`)**:
   - `data_service.load_records(db)` membaca `kecamatan`, `data_jagung`, dan `hasil_clustering` dari Supabase.
   - **Transformasi Urutan Klaster (Display Layer)**: Label mentah model (`cluster_label` `0..2`) diurutkan ulang per tahun oleh `_urutan_klaster_per_tahun()` berdasarkan rata-rata produksi tertinggi ke terendah menjadi `klaster` `1` (Tinggi), `2` (Sedang), dan `3` (Rendah).
   - `data_service.cluster_profiles()` menghitung rata-rata variabel tiap klaster, mendeteksi medoid, dan menyusun deskripsi karakteristik otomatis (`_ringkasan()`), yang digabung dengan teks override manual Admin (`keterangan_klaster`) oleh `legend_items()`.
3. **Alur Proses Clustering**:
   - Admin/Operator men-trigger `POST /admin/clustering` atau `POST /operator/clustering` -> `handle_run_clustering()` -> `data_service.run_clustering(db, tahun)`.
   - `run_clustering()` mengambil 33 baris `data_jagung` pada tahun terkait (gagal jika `!= 33`), memanggil `clustering.cluster_year(rows, k=3)`, lalu menghapus hasil lama tahun tersebut di `hasil_clustering` dan menyimpan hasil baru.
4. **Alur Render & Interaksi Peta (Frontend)**:
   - Browser memuat halaman dan memanggil `initSigaguMap(mapElementId, tahun, onKecamatanClick)` di `static/js/map_gis.js`.
   - `map_gis.js` melakukan `Promise.all` ke `/static/geojson/kecamatan.geojson` dan `/api/map-data/<tahun>`, mencocokkan `feature.properties.kecamatan_id` dengan data klaster, dan merender poligon dengan warna sesuai `map_config`.
   - Saat poligon diklik di halaman publik (`index.html`), callback memanggil `GET /api/kecamatan/<id>/riwayat` untuk memperbarui kartu metrik, grafik tren Chart.js, dan tabel riwayat tanpa reload halaman.

---

## 4. Daftar Endpoint / Route & Kontrak Data

Semua route didefinisikan di `app.py` (memanggil fungsi di `services/`).

| Route / Endpoint | Method | Akses | Parameter Utama (Query / Form / Path) | Fungsi & Kontrak Response |
| :--- | :--- | :--- | :--- | :--- |
| `/` | `GET` | Publik | Query: `tahun` (int, default `2025`), `kecamatan` (int, opsional) | Render `index.html` (Peta GIS, detail kecamatan, grafik riwayat, legenda). |
| `/peta`, `/data` | `GET` | Publik | Query: `tahun` | Redirect legacy ke `/` (`index`). |
| `/login` | `GET, POST` | Publik | Form: `username`, `password` | Autentikasi Admin/Operator; set `session` dan redirect ke dashboard sesuai role. |
| `/register` | `GET, POST` | Publik | Form: `nama_lengkap`, `username`, `password`, `konfirmasi` | Registrasi akun Operator baru dengan status `menunggu`. |
| `/logout` | `GET` | Semua | - | Hapus `session` dan redirect ke `/login`. |
| `/akun/password` | `GET, POST` | Admin / Operator | Form: `password_lama`, `password_baru`, `konfirmasi` | Ganti password akun yang sedang login. |
| `/admin` | `GET` | Admin | - | Redirect ke `/admin/dashboard`. |
| `/admin/dashboard` | `GET` | Admin | - | Render dashboard Admin (KPI, grafik & tabel Silhouette 2018–2025). |
| `/admin/data-pertanian` | `GET, POST` | Admin | Query: `tahun`. Form: `action` (`simpan` \| `hapus` \| `import`), `kecamatan_id`, `tahun`, `luas_panen`, `produksi`, `produktivitas`, `file_dataset` | CRUD penuh data pertanian & bulk import file `.csv`/`.xlsx`. |
| `/admin/clustering` | `GET, POST` | Admin | Query: `tahun`. Form: `target` (`<tahun>` \| `semua`) | Tampilkan hasil atau jalankan ulang K-Medoids tahun tertentu / seluruh tahun. |
| `/admin/pemetaan` | `GET, POST` | Admin | Query: `tahun`. Form: `action` (`warna` \| `keterangan`), `c1_color..c3_color`, `c1_label..c3_label`, `keterangan_1..3` | Peta Admin & simpan pengaturan warna/label legenda serta penjelasan manual klaster. |
| `/admin/validasi-operator` | `GET, POST` | Admin | Query: `status`. Form: `action` (`setujui` \| `tolak` \| `nonaktifkan` \| `aktifkan` \| `hapus` \| `reset`), `user_id`, `password_baru`, `konfirmasi` | Kelola siklus hidup akun Operator dan reset password Operator. |
| `/operator` | `GET` | Operator | - | Redirect ke `/operator/dashboard`. |
| `/operator/dashboard` | `GET` | Operator | - | Render dashboard Operator (KPI & grafik Silhouette). |
| `/operator/data-pertanian` | `GET, POST` | Operator | Query: `tahun`. Form: `kecamatan_id`, `tahun`, `luas_panen`, `produksi`, `produktivitas` | Lihat & update nilai data pertanian yang sudah ada (tanpa tambah/hapus/import). |
| `/operator/clustering` | `GET, POST` | Operator | Query: `tahun`. Form: `target` (`<tahun>` \| `semua`) | Lihat hasil & jalankan perhitungan K-Medoids. |
| `/operator/pemetaan` | `GET` | Operator | Query: `tahun` | Peta interaktif & legenda klaster (read-only). |
| `/api/map-data/<int:tahun>` | `GET` | Publik (API) | Path: `tahun` (`2018`–`2025`) | JSON: `{ "tahun": int, "map_config": {...}, "data": { "<kecamatan_id>": { kecamatan_id, kecamatan, tahun, luas_panen, produksi, produktivitas, klaster, is_medoid, silhouette } } }`. |
| `/api/kecamatan/<int:kecamatan_id>/riwayat` | `GET` | Publik (API) | Path: `kecamatan_id` | JSON: `{ "kecamatan_id": int, "riwayat": [ { tahun, luas_panen, produksi, produktivitas, klaster, is_medoid, silhouette }, ... ] }`. |
| `/health` | `GET` | Publik (API) | - | JSON: `{ "status": "ok", "supabase_configured": bool }`. |

---

## 5. Skema Database / Model (Supabase PostgreSQL)

### A. Tabel Inti (`schema.sql`)
1. **`public.kecamatan`**
   - Kolom: `id` (PK, bigint), `kode_kecamatan` (text, unique, contoh `'35.07.01'`), `nama_kecamatan` (text), `geojson_id` (text, unique).
   - Berisi 33 kecamatan di Kabupaten Malang.
2. **`public.data_jagung`**
   - Kolom: `id` (PK), `kecamatan_id` (FK -> `kecamatan.id`), `tahun` (int, `2018..2025`), `luas_panen` (float8, `>=0`), `produksi` (float8, `>=0`), `produktivitas` (float8, `>=0`).
   - Constraint: `UNIQUE (kecamatan_id, tahun)`.
3. **`public.hasil_clustering`**
   - Kolom: `id` (PK), `tahun` (int, `2018..2025`), `kecamatan_id` (FK -> `kecamatan.id`), `cluster_label` (int, `0..2`), `is_medoid` (bool), `luas_panen` (float8), `produksi` (float8), `produktivitas` (float8), `silhouette` (float8), `dbi` (float8), `total_dissimilarity` (float8), `processed_at` (timestamptz).
   - Constraint: `UNIQUE (tahun, kecamatan_id)`.

### B. Tabel Tambahan Frontend SIGAGU (`schema_tambahan.sql`)
4. **`public.pengguna`**
   - Kolom: `id` (PK), `nama_lengkap` (text), `username` (text, unique), `password_hash` (text), `role` (`'admin'` \| `'operator'`), `status` (`'menunggu'` \| `'disetujui'` \| `'ditolak'` \| `'nonaktif'`), `dibuat_pada` (timestamptz), `divalidasi_pada` (timestamptz).
   - Partial Unique Index: `idx_pengguna_satu_admin ON pengguna(role) WHERE role = 'admin'` (menjamin hanya ada 1 Admin).
5. **`public.pengaturan_peta`**
   - Kolom: `id` (PK, `CHECK (id = 1)`), `c1_color`, `c2_color`, `c3_color`, `c1_label`, `c2_label`, `c3_label`, `diperbarui_pada`.
   - Menyimpan konfigurasi global warna hex dan nama label untuk Klaster 1–3.
6. **`public.keterangan_klaster`**
   - Kolom: `id` (PK), `tahun` (int, `2018..2025`), `klaster` (int, `1..3`), `keterangan` (text), `diperbarui_pada` (timestamptz).
   - Constraint: `UNIQUE (tahun, klaster)`. Menyimpan deskripsi manual per klaster per tahun yang diinput Admin.

---

## 6. Integrasi AI / Machine Learning & Konvensi Kode

### A. Modul AI / Machine Learning (`services/clustering.py`)
- **Lokasi**: `services/clustering.py` -> fungsi `cluster_year(rows, k=3)` yang dipanggil melalui satu pintu `services/data_service.py::run_clustering(db, tahun)`.
- **Cara Kerja**:
  1. Mengekstrak matriks fitur 3 dimensi `X` dari `["luas_panen", "produksi", "produktivitas"]` untuk 33 kecamatan pada satu tahun.
  2. Memvalidasi seluruh elemen numerik finite dan non-negatif.
  3. Menormalisasi fitur ke rentang `[0, 1]` dengan `MinMaxScaler().fit_transform(X)`.
  4. Menjalankan algoritma **K-Medoids** (`sklearn_extra.cluster.KMedoids(n_clusters=3, metric="euclidean", method="pam", init="k-medoids++", random_state=42)`).
  5. Mengembalikan dictionary berisi `labels` (`0..2`), `medoid_kecamatan_ids`, dan metrik evaluasi (`silhouette`, `dbi`, `total_dissimilarity`).
- **Aturan Isolasi Model**:
  - **Jangan mengubah `services/clustering.py`** kecuali diminta secara eksplisit untuk mengganti rumus/algoritma clustering.
  - Pengurutan label klaster agar konsisten (**Klaster 1 = Produksi Tinggi**, **Klaster 2 = Produksi Sedang**, **Klaster 3 = Produksi Rendah**) dilakukan sepenuhnya di layer pembacaan data (`services/data_service.py::_urutan_klaster_per_tahun`), bukan dengan memodifikasi output mentah di `clustering.py`.

### B. Aturan Metrik Evaluasi di UI
- **Hanya Gunakan Silhouette Coefficient**: Seluruh tampilan antarmuka (KPI card, grafik evaluasi tahunan, tabel evaluasi, dan tooltip peta) **wajib hanya menampilkan Silhouette Coefficient**.
- Kolom `dbi` dan `total_dissimilarity` tetap diisi saat insert ke tabel `hasil_clustering` demi kompatibilitas constraint `NOT NULL` pada `schema.sql`, tetapi **dilarang ditampilkan di UI**.

### C. Konvensi Kode & Pola Arsitektur Wajib
1. **Penamaan (Naming Convention)**:
   - Python: `snake_case` untuk fungsi/variabel, `UPPER_SNAKE_CASE` untuk konstanta, istilah domain dalam Bahasa Indonesia (`luas_panen`, `produksi`, `produktivitas`, `kecamatan_id`, `klaster`, `tahun`).
   - JavaScript: `camelCase` (`initSigaguMap`, `selectKecamatan`, `openEditModal`).
2. **Pemisahan Jinja2 dan JavaScript di Template HTML**:
   - **Dilarang menulis ekspresi Jinja `{{ ... }}` secara mentah di dalam blok `<script>` atau di dalam atribut `onclick="..."`** karena memicu error parser/linter JS di IDE.
   - Selalu injeksikan data server ke atribut HTML `data-*` (mis. `data-years='{{ years | tojson }}'`, `data-row='{{ r | tojson }}'`) atau `<script type="application/json">`, lalu baca di JavaScript menggunakan `JSON.parse(el.dataset.years)`.
3. **State Management & Fallback Memori**:
   - Autentikasi menggunakan Flask signed cookie `session` (`user_id`, `username`, `nama`, `role`).
   - `auth_service.py` (`_MEM_USERS`) dan `data_service.py` (`_MEM_MAP_CONFIG`, `_MEM_KETERANGAN`) menyediakan fallback di memori apabila tabel pada `schema_tambahan.sql` belum dieksekusi di Supabase, sehingga aplikasi tidak crash saat pengujian lokal.
4. **Error Handling & Formatting**:
   - Validasi input form/import melempar `ValueError` dengan pesan Bahasa Indonesia yang ramah pengguna, ditangkap di route `app.py` dan ditampilkan via `flash(pesan, "danger")`.
   - Format angka di template wajib menggunakan custom filter Jinja `| angka(decimals)` (format Indonesia: titik pemisah ribuan, koma desimal, contoh `43.718,50`).

