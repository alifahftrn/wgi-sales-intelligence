# Transformation V2 — preview planning dan KPI

Pasang setelah Transformation V1. Empat file kode/konfigurasi/test baru dan dokumen ini; tidak mengganti file lama. Tidak membutuhkan library baru. Tidak menulis ke database.

## Jalankan

```powershell
python -m unittest discover -v
python manage.py check
python manage.py transform_sales_v2 --demo
python manage.py transform_sales_v2 --run-id 20261125T011526Z_fe5b47a2
```

Gunakan ID Extract yang tersedia. Untuk seleksi forecast historis (bukan rekonstruksi Actual):

```powershell
python manage.py transform_sales_v2 --demo --plan-cutoff 2026-11-05T23:59:59+07:00
```

Output `.local/transform_v2/demo/<run-id>/preview.json` atau `mysql/<run-id>/preview.json`, cutoff eksplisit diberi suffix. Output tidak ditimpa. `PREVIEW_ONLY`, `load_ready=false`. Demo tidak boleh dimuat ke Data Mart operasional. `source_coverage=NOT_VERIFIED`.

## Kebijakan dan batas

- Registry V1 tetap digunakan untuk actual dan outstanding. V2 menambahkan langkah rencana, metrik dan growth dengan urutan YAML tetap; bukan engine universal yang bisa menyusun langkah sembarang.
- Asumsi sementara DATETIME bisnis sumber adalah waktu WIB (UTC+7). Timestamp snapshot memang UTC. Konfirmasi sebelum produksi. Waktu penetapan tidak boleh lebih baru daripada snapshot.
- ASP Internal/External terpisah. Forecast history menyimpan baseline dan semua revisi yang tersedia pada snapshot; terbaru per source/SKU/distributor/bulan dipilih berdasarkan timestamp <= cutoff, revisi diutamakan bila seri, lalu ID detail teks secara leksikografis. Kebijakan tie-break ini keputusan desain sementara.
- Achievement menggunakan nilai sumber, bukan perkalian master harga/volume terkini. Rasio 0 denominator atau nilai hilang = null. Tidak ada record actual bukan bukti nol. Prorata ASP berdasarkan hari kalender inklusif sampai tanggal snapshot; hari snapshot bisa belum lengkap. Forecast dibandingkan dengan rencana satu bulan penuh.
- WAPE dihitung sebagai jumlah selisih absolut per natural key / jumlah actual absolut, terpisah per bulan/sumber/unit. Pasangan hilang atau denominator nol menghasilkan null; accuracy = 100 - WAPE (dapat negatif). Bulan berjalan bersifat provisional; kualitas/cakupan data belum diverifikasi.
- Growth MoM/YoY per natural key, periode lampau full month dan bulan berjalan same elapsed calendar days (dibatasi panjang bulan pembanding), bukan pembandingan jam yang sama. Pembanding yang hilang/zero = null. Tidak menjamin kelengkapan historis atau agregat lintas versi dimensi.
- Belum mencakup QoQ/YTD/period filter bebas, return, cross-source identity, UI, rekonstruksi histori as-known, SCD/load maupun pengujian database. Cutoff rencana bukan cutoff historis actual; actual tetap berasal dari snapshot yang sama. Tidak mengganti business rules resmi perusahaan.

## Hasil fixture (snapshot 25 Nov 2026)
- Actual 290 pack semua periode, November 2026 actual 90 pack.
- ASP Internal 100, External 120. Achievement penuh 90% dan 75%. Prorata 25/30: 108% dan 90%.
- Baseline 110, revisi 100 dan 95. Latest 95, achievement 94.74%, WAPE 5.56%, accuracy 94.44% provisional. Cutoff 5 Nov memilih 100.
- Growth November 2026 vs Oktober 2026 dan November 2025 = -10% masing-masing.
- 3 ACTUAL + 2 ASP + 1 FORECAST_LATEST = 6 monthly metric rows; history 3.

59 unit tests pass in reconstructed project (9 new); Django CLI/database not tested in authoring environment.
