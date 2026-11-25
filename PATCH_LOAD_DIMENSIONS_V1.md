# Load Engine V1 — dimensi MySQL ke PostgreSQL

Tambahkan isi patch ke root project. Tidak ada perubahan schema atau dependency. Gunakan venv dan alias Django `datamart` yang sudah terhubung ke `sales_datamart`.

1. `python -m unittest discover -v` (85 test pada rekonstruksi project).
2. `python manage.py check`.
3. `python manage.py load_dimensions --run-id 20261125T011526Z_fe5b47a2` (dry-run, tanpa INSERT/UPDATE; mengambil lock singkat).
4. Jika hasil benar dan database tujuan development sudah diverifikasi, `python manage.py load_dimensions --run-id 20261125T011526Z_fe5b47a2 --apply`.
5. Ulangi perintah apply dengan run sama: `ALREADY_APPLIED`, tidak menambah baris.

Cakupan: `dim_produk`, `dim_distributor`, `etl_log`. Tidak ada perubahan `dim_tanggal`, fact tables atau MySQL. Tidak ada opsi demo; manifest extract full asli `salesdashboard` diwajibkan, synthetic ditolak. Checksum manifest raw dan output canonical diperiksa, error relasi menolak proses. Warning Data Quality dicetak; bukan izin memuat fact. `PARTIAL` pada etl_log berarti hanya fase dimensi, bukan ETL keseluruhan selesai. `rows_read` jumlah master dimensi, `rows_written` jumlah INSERT dimensi + UPDATE penutupan versi, tidak termasuk log. `DIM_V1:` prefix memisahkan run fase dimensi dari pipeline selanjutnya. Log sukses dan perubahan dimensi satu transaksi; jika gagal rollback, belum ada pencatatan FAILED terpisah. Dry-run tidak membuat log. Ulang run sama dengan identitas yang sama dilewati; tidak melakukan perbaikan manual atas data yang diubah di luar loader.

SCD2: waktu observasi snapshot UTC, bukan source_updated_at atau tanggal transaksi. Interval [mulai,sampai), atribut sama tidak menambah versi; perubahan menutup versi lama dan insert versi baru. Snapshot lama, overlap, master kosong dan kode lama hilang ditolak. Tidak menutup versi secara otomatis karena data hilang. Tidak merekonstruksi histori sebelum snapshot pertama. Fact historis belum boleh dihubungkan ke versi masa depan; kebijakan resolusi dimensi sebelum observasi pertama masih diperlukan.

SQL asli `01_PostgreSQL_Fondasi_Data_Mart.sql` digunakan sebagai acuan. Uji di lingkungan pembuatan: 85 unit test, termasuk 15 test baru dengan fake cursor dan fixture lokal. Tidak tersedia server PostgreSQL atau Django di lingkungan tersebut; SQL execution, atomic rollback dan locking nyata belum teruji. Jalankan dry-run dahulu pada PostgreSQL lokal development, jangan langsung di production.
