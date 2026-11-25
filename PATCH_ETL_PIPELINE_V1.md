# ETL Pipeline V1 — MySQL

Prasyarat: patch Fact Writer V1 dan SQL 03/04 pada database test sudah terpasang. Tidak perlu migrasi atau paket Python tambahan. Semua file patch ini baru.

## Pengujian

```
python -m unittest discover -v
python manage.py check
python manage.py verify_pipeline_integration
```

117 unit test lulus pada rekonstruksi patch. Django CLI dan PostgreSQL integration perlu diuji di laptop. Integration command hanya menuju PostgreSQL lokal `sales_datamart_scd_test` yang harus kosong (kecuali kalender). Empat skenario; semua fixture di-rollback, tetapi sequence identity PostgreSQL dapat maju.

## Penggunaan

```
python manage.py run_etl --source mysql --run-id 20261125T011526Z_fe5b47a2
python manage.py run_etl --source mysql
```

Perintah kedua mengambil snapshot baru, menghasilkan raw/canonical lokal, lalu memeriksa quality, menjalankan transform V2 dan dry-run dimensi. Untuk run baru, fact database check ditunda sampai apply (memerlukan versi dan log dimensi baru). Bukan simulasi lengkap seluruh SQL. Catat run-id yang dicetak. Periksa snapshot/hasil sebelum apply:

```
python manage.py run_etl --source mysql --run-id RUN_ID_BARU --apply
```

Ganti RUN_ID_BARU dengan ID hasil preview, bukan teks literal. Jalankan ulang ID sama untuk menguji idempotency. Tidak perlu extract ulang. `--apply` tanpa `--run-id` mengambil snapshot baru lalu memuatnya secara langsung; gunakan hanya setelah prosedur operasional siap. Data Mart tujuan dijaga oleh loader lama (`sales_datamart`).

## Batasan dan keputusan

- Atomic PostgreSQL menggabungkan dimension dan fact loader; kegagalan di tengah transaksi membatalkan perubahan run baru. Tidak membatalkan raw/canonical yang sudah diterbitkan. Run lama yang pernah di-commit terpisah tidak di-rollback retroaktif.
- Kedua log loader masih terpisah (`DIM_V1`, `FACT_V1`). Belum ada log kegagalan persisten atau penanda scheduler. Jika status commit tidak pasti, periksa etl_log dan retry ID yang sama. Jangan langsung membuat run baru.
- Lock lokal `.local/.pipeline.lock` mencegah dua orkestrator di folder sama; lock extract dan lock database tetap dipakai. Jika proses dihentikan paksa, periksa tidak ada proses aktif sebelum membersihkan lock. Jangan jalankan command loader standalone paralel dengan pipeline.
- Hanya full extract MySQL; Excel dan Sage belum diorkestrasi, belum incremental. Transform V3 adalah analisis periode sesuai permintaan, bukan output fact tambahan. Coverage belum terverifikasi. Tidak ada penulisan demo ke Data Mart utama.
- Default preview membuat file lokal dan menggunakan lock sementara pada PostgreSQL, tanpa DML. Pemeriksaan konflik fact baru berlangsung pada apply. SQL transaction timeout 60 detik per statement dari tahap sebelumnya; performa belum teruji pada skala besar.
- Scheduler, UI monitoring, backup/restore operasional, pengujian transaksi perusahaan dan observability lanjutan belum termasuk.
