# Transformation V3 — period analysis preview

Pasang setelah V2. Empat file baru, tidak mengganti kode lama, tidak membutuhkan library baru, tidak menulis MySQL/PostgreSQL. 70 unit test lulus pada rekonstruksi project (11 baru). Django CLI belum diuji di lingkungan pembuat karena Django tidak terpasang.

```powershell
python -m unittest discover -v
python manage.py check
python manage.py transform_sales_v3 --demo --period month --year 2026 --index 11 --compare yoy
python manage.py transform_sales_v3 --demo --period quarter --year 2026 --index 4 --compare previous
python manage.py transform_sales_v3 --demo --period ytd --year 2026 --compare yoy
python manage.py transform_sales_v3 --demo --period semester --year 2026 --index 2 --compare yoy
python manage.py transform_sales_v3 --demo --period custom --start 2026-11-02 --end 2026-11-02 --compare none --product 99001 --region "Region 1"
python manage.py transform_sales_v3 --run-id 20261125T011526Z_fe5b47a2 --period month --year 2026 --index 11 --compare yoy
```

`--index` = bulan 1..12, kuartal 1..4, semester 1..2. `year` dan `ytd` tidak memakai index; `custom` hanya start/end, inklusif. Year/YTD menggunakan rentang kalender tahun terpilih dan dibatasi tanggal snapshot; YTD previous berarti tahun sebelumnya. `--mode elapsed` default: periode berjalan dibandingkan dengan jumlah hari kalender sama (kedua periode dipendekkan bila pembanding lebih pendek); jika periode selesai, pembanding penuh. `--mode full`: periode berjalan sampai snapshot vs periode pembanding penuh, bukan estimasi penjualan masa depan. `--compare previous`: periode kalender sebelumnya, atau custom window sebelumnya dengan panjang sama. `--compare yoy`: periode tahun sebelumnya, tanggal 29 Februari dijepit ke akhir Februari jika perlu. Hari snapshot mungkin belum lengkap. `--plan-cutoff` hanya memengaruhi seleksi rencana V2, bukan actual.

Filter `--product`, `--distributor`, `--region`, `--area`, `--brand` berlaku AND, nilai persis sesuai kode/atribut master canonical saat snapshot. Tidak membuktikan atribut historis SCD. `--compare none` tidak menampilkan pembanding. Semua unit pack/liter/rupiah dikembalikan sekaligus, pilihan tampilan nantinya di BI Service. Tidak ada baris = None/null; growth denominator nol = None. Actual berdasarkan DO valid dan tanggal DO. Tidak menjumlahkan PO dengan DO. Rasio dihitung dari total tanpa pembulatan dini. Output angka desimal ditampilkan sampai 6 tempat desimal, rasio 2. ASP prorata per bulan berdasarkan hari kalender inklusif. ASP Internal dan External terpisah. Pack target prorata boleh pecahan karena analitik, bukan kuantitas transaksi input. Achievement periode None jika pasangan natural key/bulan actual dan target tidak lengkap; ini bukan bukti cakupan data menyeluruh. Growth atas baris teramati, source_coverage=NOT_VERIFIED. Fixture 2025 hanya untuk testing, bukan penjualan perusahaan. Forecast/WAPE dan outstanding tetap pada V1/V2, belum ada perhitungan period-wide forecast accuracy atau snapshot historis di V3. Return belum diintegrasikan. Belum ada UI, SCD, load, atau scheduler. V3 menggunakan pipeline V2 yang tetap, bukan registry universal.

Hasil fixture snapshot 25 Nov 2026 WIB: Nov actual 90 pack, pembanding Nov 2025 100, growth -10%; ASP internal prorata 83.333333, achievement 108%; external prorata 100, achievement 90%. Q4 actual 190, Q3 pembanding tidak tersedia, growth None. YTD actual 190 vs 100, growth 90% (data fixture tidak lengkap). Custom 2 Nov actual 40 pack, target internal 3.333333, achievement 1200%. MySQL snapshot tanpa transaksi: actual, growth, target None, bukan nol. Output `.local/transform_v3/{demo,mysql}/<run-id>_<query-hash>/preview.json`; query identik untuk run sama tidak ditimpa. Demo run baru tiap invocation. Status tetap PREVIEW_ONLY dan load_ready=false.
