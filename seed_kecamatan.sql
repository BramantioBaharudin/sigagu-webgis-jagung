-- Data 33 kecamatan Kabupaten Malang (kode wilayah Kemendagri 35.07.xx).
-- Jalankan di Supabase SQL Editor SETELAH schema.sql.
-- Silakan verifikasi kode/nama dengan sumber resmi (BPS / Kemendagri) bila diperlukan.

insert into public.kecamatan (kode_kecamatan, nama_kecamatan, geojson_id) values
  ('35.07.01', 'Donomulyo', '35.07.01'),
  ('35.07.02', 'Pagak', '35.07.02'),
  ('35.07.03', 'Bantur', '35.07.03'),
  ('35.07.04', 'Sumbermanjing Wetan', '35.07.04'),
  ('35.07.05', 'Dampit', '35.07.05'),
  ('35.07.06', 'Ampelgading', '35.07.06'),
  ('35.07.07', 'Poncokusumo', '35.07.07'),
  ('35.07.08', 'Wajak', '35.07.08'),
  ('35.07.09', 'Turen', '35.07.09'),
  ('35.07.10', 'Gondanglegi', '35.07.10'),
  ('35.07.11', 'Kalipare', '35.07.11'),
  ('35.07.12', 'Sumberpucung', '35.07.12'),
  ('35.07.13', 'Kepanjen', '35.07.13'),
  ('35.07.14', 'Bululawang', '35.07.14'),
  ('35.07.15', 'Tajinan', '35.07.15'),
  ('35.07.16', 'Tumpang', '35.07.16'),
  ('35.07.17', 'Jabung', '35.07.17'),
  ('35.07.18', 'Pakis', '35.07.18'),
  ('35.07.19', 'Pakisaji', '35.07.19'),
  ('35.07.20', 'Ngajum', '35.07.20'),
  ('35.07.21', 'Wagir', '35.07.21'),
  ('35.07.22', 'Dau', '35.07.22'),
  ('35.07.23', 'Karangploso', '35.07.23'),
  ('35.07.24', 'Singosari', '35.07.24'),
  ('35.07.25', 'Lawang', '35.07.25'),
  ('35.07.26', 'Pujon', '35.07.26'),
  ('35.07.27', 'Ngantang', '35.07.27'),
  ('35.07.28', 'Kasembon', '35.07.28'),
  ('35.07.29', 'Gedangan', '35.07.29'),
  ('35.07.30', 'Tirtoyudo', '35.07.30'),
  ('35.07.31', 'Kromengan', '35.07.31'),
  ('35.07.32', 'Wonosari', '35.07.32'),
  ('35.07.33', 'Pagelaran', '35.07.33')
on conflict (kode_kecamatan) do nothing;
