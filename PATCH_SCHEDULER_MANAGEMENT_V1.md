# Scheduler Management V1

Basis: source Authentication V1 + Manual ETL V1 + Scheduler V2 Engine yang telah diuji. Tambahan ini tidak mengubah scheduler.py, run_etl, mekanisme lock, database bisnis, atau autentikasi.

## Pemasangan
- Pastikan working tree bersih, tidak ada perubahan frontend pada file yang diganti, scheduler V2 berhenti dan disabled, serta Windows task lama disabled.
- Extract ZIP ke root project. Empat file baru: etl/scheduler_views.py, etl/scheduler_django_checks.py, templates/etl_scheduler_settings_v1.html, templates/etl_scheduler_status_v1.html. Satu dokumentasi baru. Tiga file diperbarui: config/urls.py, etl/monitoring_views.py, templates/etl_monitor_v1.html.
- `python -m unittest discover -v` (157 tests)
- `python manage.py check`
- `python manage.py test accounts.django_checks etl.manual_django_checks etl.scheduler_django_checks -v 2` (26 tests expected, 12 new)
- `python manage.py runserver 127.0.0.1:8000`

## Uji lokal
1. Login ADMIN, buka /etl/monitoring/, cek panel Scheduler V2 dan riwayat Preview 26 November. Windows Scheduler lama ditampilkan terpisah.
2. Buka /etl/scheduler/, ubah jam ke 01:00, pilih Nonaktif dan PREVIEW, simpan. Cek `python manage.py etl_scheduler status` di terminal kedua. Config harus enabled=0, clock=01:00, mode=PREVIEW; riwayat lama tetap ada.
3. Kembalikan jam 00:00, Nonaktif, PREVIEW. Verifikasi terminal lagi. Tidak perlu menyalakan scheduler atau melakukan APPLY.
4. Coba logout dan akses langsung /etl/scheduler/; harus redirect login. Pengujian endpoint menggunakan akun simulasi dan SQLite sementara, bukan database bisnis.

## Cara kerja dan batasan
- GET membaca status dan 20 riwayat terakhir dari Scheduler.status(); tidak menciptakan file SQLite bila belum ada. POST hanya mengubah konfigurasi via Scheduler.configure(); CSRF, localhost, ADMIN, validasi field, dan konfirmasi eksplisit.
- Konfirmasi Windows task dinonaktifkan adalah pernyataan operator, bukan verifikasi sistem. Konfirmasi APPLY wajib saat jadwal aktif dalam mode APPLY.
- Form tidak menjalankan atau menghentikan worker; pengaturan aktif tidak sama dengan proses hidup. Worker terpisah `python manage.py etl_scheduler run` membaca konfigurasi pada tick berikutnya. Menonaktifkan jadwal tidak membatalkan job yang sudah diklaim.
- Satu percobaan terjadwal per tanggal WIB tetap berlaku. Jangan hapus riwayat untuk melakukan percobaan APPLY pada tanggal yang sama. Tidak ada autostart, heartbeat worker, audit identitas perubahan konfigurasi, atau retry otomatis pada versi ini. Belum production-ready.
- SQLite jurnal yang sudah ada tetap digunakan (.local/scheduler_v2.sqlite3), tanpa migrasi atau library tambahan. Jangan commit data lokal atau .env.

## Verifikasi pembuat patch
157 unit test existing lulus dalam lingkungan Linux Python dan syntax check lulus. Django tidak tersedia di lingkungan tersebut; 12 test endpoint baru, rendering template Django, dan koneksi database asli harus diuji oleh developer di lingkungan lokal. Kompatibilitas runtime scheduler pada Linux dengan DB asli belum teruji.
