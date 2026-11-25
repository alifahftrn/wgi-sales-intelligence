# WGI — Data Quality V1

Patch tambahan; tidak mengganti file lama. Berlaku setelah Mapping V2. Tidak mengakses database, tidak mengubah .env, dan tidak membuat fact table.

1. `python -m unittest discover -v`
2. `python manage.py check`
3. `python manage.py validate_sales --run-id 20261125T011526Z_fe5b47a2`
4. `python manage.py validate_sales --demo`

Run asli memeriksa hasil Mapping V2 di `.local/canonical_v2/mysql`. Demo menciptakan data fiktif di `.local/quality_demo/extracts` dan `.local/quality_demo/canonical_v2/mysql` dengan run-id baru; tidak memakai master perusahaan. Output demo dipisahkan dari jalur normal, tidak boleh di-load ke Data Mart. Raw demo adalah simulasi kontrak manifest Extract, bukan hasil koneksi MySQL.

Status PASS = tidak ditemukan masalah dalam cakupan pemeriksaan ini; REVIEW = perlu pemeriksaan; FAIL = pelanggaran terdeteksi. Mapping PARTIAL, checksum salah, atau jumlah baris berbeda menghentikan proses. `load_ready=false` selalu dipertahankan. Pesan tidak memuat nilai transaksi. Validasi ini membaca data ke memori; optimasi untuk volume besar ditunda.

Demo berisi 27 baris, 24 transaksi/target/forecast (header dan detail), penjualan 2025/2026, dua target ASP, baseline + 2 revisi, PO penuh/sebagian, pembatalan sebagian, dua DO pada satu PO. Harga dan PPN 11% fiktif. Hasil REVIEW, 0 error, 1 warning karena status PO COMPLETED hanya asumsi fixture, bukan status produksi yang sudah dikonfirmasi. CONFIRMED dan PARTIAL teramati pada audit sebelumnya, tetapi definisi bisnis lengkap status belum diverifikasi. Uji pengiriman menjumlah DO CONFIRMED saja sebagai pemeriksaan awal, bukan klasifikasi actual final. Pembulatan snapshot harga menggunakan HALF_UP sebagai aturan sementara.

Belum mencakup mapping Excel kompleks, KPI, versi SCD, aturan zona waktu final, validasi semua status, histori master, return, data hilang lintas snapshot, atau Load Engine. Jangan menganggap PASS sebagai persetujuan load. Hanya subset relasi dan aturan bisnis yang diuji.
