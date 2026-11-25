# Load Engine V2A — Fact Load Planner

Patch read-only. Tidak mengganti file lama, tidak mengubah SQL, .env, MySQL atau PostgreSQL. Tidak ada opsi --apply. Mode demo membuat fixture lokal melalui helper lama, tanpa koneksi database. Mode MySQL memeriksa manifest, checksum, data quality, log dimension load, dimensi aktif, kalender dan jumlah fact yang sudah ada pada transaksi PostgreSQL REPEATABLE READ READ ONLY. Preview V2 dihitung ulang dari canonical pada cutoff snapshot, bukan menggunakan file preview yang dapat diedit. Actual bulanan dikelompokkan ulang berdasarkan versi dimensi, dan pack/liter/rupiah direkonsiliasi dengan ringkasan V2. Forecast latest membawa referensi natural key sampai ID history tersedia. ID dimensi historis yang tidak diketahui adalah NULL; tanggal PO/DO tanpa jam hanya di-resolve bila versi meliputi satu hari penuh WIB. Snapshot outstanding menggunakan versi pada tanggal PO; kebijakan ini perlu disepakati sebelum implementasi penulisan. Tidak menebak histori sebelum ETL. Demo sengaja menggunakan histori mulai 25 November 2026 untuk menunjukkan kondisi ini. 38 referensi versi tidak diketahui (19 baris x 2); bukan 38 transaksi gagal. Tidak ada baris fact yang ditulis. Planner belum memeriksa konflik fact existing, immutable forecast/ASP, kehilangan transaksi, idempotency penulisan, teramati_at, id_run, transaksi write, rollback write, atau integrasi database fact. Pemeriksaan skema SQL aktual pada laptop tetap diperlukan.

## Perintah

```powershell
python -m unittest discover -v
python manage.py check
python manage.py plan_fact_load --demo
python manage.py plan_fact_load --run-id 20261125T011526Z_fe5b47a2
```

96 unit test lulus pada rekonstruksi project dari ZIP lama, bukan laptop pengguna. Target demo counts 7, 3, 6, 3; actual 290 pack, 2784.000 liter, 32190000.00 rupiah. Target snapshot MySQL lama semua planned_rows=0, existing_rows=0 bila fact table masih kosong. Jangan menafsirkan data kosong sebagai penjualan perusahaan nol. Pengujian PostgreSQL dan Django CLI belum dilakukan di lingkungan pembuat patch.
