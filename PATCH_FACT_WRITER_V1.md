# WGI Fact Writer V2B (implementasi V1)

## Pasang
Ekstrak ke root wgi_sales_extract. `etl/load/fact_planner.py` satu-satunya file lama yang diganti: parameter `test_only` untuk guard database. Enam file lain baru. Tidak ada dependensi baru.

## Pengujian sebelum apply
1. `python -m unittest discover -v` (106 tests pada rekonstruksi patch).
2. `python manage.py check`.
3. Di pgAdmin, pastikan `SELECT current_database();` = `sales_datamart_scd_test`. Jalankan `database/postgresql/04_Fact_Test_Foundation.sql` sekali pada database tersebut. Script diturunkan dari SQL fact asli, dengan guard database test; tidak mengisi dummy.
4. `python manage.py verify_fact_integration`. Enam skenario, semua fixture di-rollback; identitas sequence PostgreSQL dapat bertambah meskipun baris di-rollback.
5. `python manage.py load_facts --run-id 20261125T011526Z_fe5b47a2` (dry-run utama, tidak melakukan DML). Harus 0 planned writes bila snapshot dan fact kosong.
6. Jangan `--apply` sebelum hasil integrasi dan dry-run diverifikasi. CLI menyediakan `--apply` untuk tahap sesudahnya. Tidak ada opsi demo di CLI utama.

## Kontrak
- Gunakan snapshot MySQL penuh canonical yang terverifikasi dan dimensi yang sudah diload untuk run yang sama, dan yang terbaru. Seluruh fact ditulis pada satu transaksi.
- Log dimensi `DIM_V1:<run>` tetap PARTIAL; log fact `FACT_V1:<run>` SUCCESS hanya berarti proses fact berhasil, bukan coverage sumber lengkap. Log terpisah untuk mencegah konflik kontrak loader lama. Run yang sama tidak ditulis ulang.
- PO/DO upsert berdasarkan source + jenis_record + id_detail_sumber. Identitas lama yang hilang ditolak, bukan dihapus. Timestamp sumber mundur ditolak jika keduanya diketahui.
- Forecast history append-only; perubahan identitas/nilai/versi yang telah tersimpan ditolak. ASP lama diperiksa immutable; koreksi target perlu kebijakan eksplisit.
- Cache `fact_sales_monthly` untuk MYSQL dibangun ulang atomik (DELETE cache MYSQL + INSERT); surrogate key cache bisa berubah. Tidak menghapus PO/DO, forecast history, snapshot outstanding, atau data sumber lain. Konsumen BI harus memakai natural key, bukan ID cache sebagai identitas permanen.
- Snapshot outstanding append per cutoff. Versi dimensi menggunakan aturan planner: tanggal PO untuk outstanding; jika versi historis tidak teramati, NULL, tidak ditebak. Sumber atribut histori sebelum observasi belum tersedia.
- FK latest forecast memakai identitas history yang diperoleh dari PostgreSQL. Rekonsiliasi jumlah fact, actual pack/liter/rupiah pada detail DO dan cache, dan outstanding pada cutoff sebelum commit.
- Perubahan transaksi disimpan sebagai kondisi terkini, bukan histori bitemporal. Belum mendukung incremental ETL, as-known actual historis, penghapusan sumber, rekonsiliasi coverage periode lengkap, atau failure logging di transaksi terpisah. Lock tabel dan rebuild cache full-source perlu diukur kinerjanya sebelum production.
- Unit test 106 lulus pada rekonstruksi patch; PostgreSQL dan Django CLI tidak tersedia di lingkungan pembuat patch. Skenario integrasi PostgreSQL wajib dijalankan di laptop sebelum apply.
