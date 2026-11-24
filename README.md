# WGI Sales Intelligence — tahap 01 Extract

Starter Django Full Stack (Django Templates + HTML/CSS/JavaScript). Bukan aplikasi production atau implementasi 19 menu lengkap. Tujuan tahap ini adalah membuktikan koneksi dan ekstraksi nyata dari MySQL `salesdashboard` tanpa mengubah database. Konfigurasi PostgreSQL `sales_datamart` tersedia, tetapi tidak digunakan, tidak dibuat tabel, dan tidak diisi.

## 1. Persiapan Windows

Gunakan Python 3.12 atau 3.13 64-bit. MySQL 8 sudah berjalan di port 3306. Buka folder ini di VS Code, gunakan terminal PowerShell. Jika belum ada Python, instal dari python.org. Periksa dengan `py --list`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Jika hanya ada Python 3.13, ganti `py -3.12` dengan `py -3.13`. Perintah di atas menggunakan executable virtual environment secara langsung, jadi tidak perlu mengaktifkan script PowerShell. `mysqlclient` adalah driver resmi yang direkomendasikan Django; jika instalasi gagal, kirim error dan pastikan Python 64-bit serta wheel yang cocok tersedia.

Buka `.env` di VS Code. Isi `MYSQL_USER` dan `MYSQL_PASSWORD` dengan akun MySQL yang benar. `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=3306`, `MYSQL_DATABASE=salesdashboard`. Password kosong hanya jika memang akun lokal tidak memiliki password. Akun baca-saja dianjurkan: admin dapat memakai contoh SQL opsional di `database/mysql/optional_readonly_account.sql` setelah mengganti password placeholder, **bukan** migrasi schema. Bila akun belum dibuat, gunakan akun MySQL lokal yang sudah ada untuk pengujian saja. Jangan mengirim password ke chat atau menyimpan ke GitHub.

Ganti `DJANGO_SECRET_KEY` dengan nilai acak dari:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
```

Masukkan output ke `.env`. Pengaturan PG dapat dibiarkan sampai tahap Load. Jangan jalankan `manage.py migrate`, karena database bisnis existing tidak dikelola oleh starter ini.

## 2. Jalankan Extract pertama (CLI)

```powershell
.\.venv\Scripts\python.exe manage.py extract_sales
```

Jika sukses, terminal menampilkan jumlah baris per tabel dan folder output. Berdasarkan audit sebelumnya (belum diverifikasi langsung oleh program): produk 5, distributor 5, harga_produk 5, 10 tabel transaksi kosong. Total yang diharapkan 15 baris dari 13 tabel apabila belum ada perubahan. Satu baris pengguna sengaja tidak diambil. Kolom `dibuatOleh` juga tidak diambil. Peringatan kolom/tabel histori belum ada adalah normal sebelum migrasi V3.

Output:

```text
.local/extracts/<run_id>/
  manifest.json
  produk.jsonl
  distributor.jsonl
  harga_produk.jsonl
  asp.jsonl
  asp_detail.jsonl
  forecast.jsonl
  forecast_detail.jsonl
  revisi_forecast.jsonl
  revisi_forecast_detail.jsonl
  purchase_order.jsonl
  purchase_order_detail.jsonl
  delivery_order.jsonl
  delivery_order_detail.jsonl
```

JSONL = satu baris JSON per baris sumber; tabel kosong menghasilkan file kosong. Manifest berisi nama kolom, tipe MySQL, jumlah baris, checksum SHA-256, waktu UTC, dan peringatan. Nilai DECIMAL disimpan sebagai string supaya presisi tidak berubah. DATETIME lama tetap disimpan sebagaimana di database; penetapan zona waktu historis dilakukan saat Transform. TIMESTAMP menggunakan session UTC.

## 3. Jalankan frontend Django

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Buka http://127.0.0.1:8000/ di browser. Halaman ETL Monitoring menampilkan manifest terakhir. Tombol **Jalankan Extract** menggunakan POST + CSRF dan menjalankan kode yang sama dengan CLI. Untuk data besar, gunakan CLI (tombol ini sinkron dan hanya untuk development). Sidebar BI dan Sales Operations masih placeholder nonaktif; belum ada login. Jangan membuka aplikasi ke jaringan, internet, reverse proxy, atau mengubah bind address. Production memerlukan autentikasi, RBAC dan background worker terpisah.

## 4. Cara kerja dan batasan

- Allowlist berdasarkan DDL `salesdashboard (2).sql`, dengan kolom opsional dari migrasi MySQL V3. Tabel histori ikut diambil bila tersedia. Tidak ada SELECT * atau ekstraksi akun/password.
- Menggunakan transaksi read-only InnoDB REPEATABLE READ dengan consistent snapshot. Hindari menjalankan migrasi/DDL bersamaan dengan Extract. Waktu observasi snapshot bukan watermark incremental.
- Query keyset pagination per primary key, batch default 1000. Semua tabel dibaca dari satu snapshot. File lengkap dipublikasikan secara atomik melalui rename direktori; kegagalan tidak menimpa hasil terakhir.
- Semua Extract adalah FULL_EXTRACT. `updated_at` ikut diambil jika ada, tetapi incremental belum dibuat. Tidak ada Transform, Load, penghitungan PPN, WAPE, snapshot outstanding, ETL schedule, atau validasi bisnis penuh di tahap ini.
- Lock direktori `.local/extracts/.extract.lock` mencegah dua proses extract pada mesin/folder yang sama. Jika komputer mati paksa, pastikan tidak ada proses extract berjalan sebelum menghapus direktori lock kosong secara manual. Folder `.partial-*` dapat dibersihkan setelah memastikan proses berhenti.
- File staging mungkin berisi informasi internal perusahaan. Jangan unggah `.env`, `.local`, atau raw export ke GitHub. `.gitignore` sudah disiapkan; batasi izin folder, retensi, dan backup sesuai kebijakan IT.
- Setelah extract berhasil, tahap berikutnya: uji migrasi V3 pada salinan database, Transform (Liter, PPN, histori, ASP/forecast), Load PostgreSQL, rekonsiliasi dan scheduling 00.00 WIB.

## 5. Jika muncul error

| Pesan | Pemeriksaan |
| --- | --- |
| `Access denied` | Username/password dan host MySQL; pastikan SELECT diberikan. |
| `Can't connect` / `2003` | MySQL berjalan? Host dan port benar? |
| `Unknown database` | Nama database di .env. |
| Kolom wajib tidak ditemukan | Struktur sumber berbeda dari DDL; jangan ubah database sembarangan. |
| `No module named django` | Gunakan executable `.venv` dan instal requirements. |
| Peringatan histori V3 belum ada | Normal sebelum migrasi, bukan kegagalan Extract. |

## 6. Pengujian

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tes unit memakai cursor simulasi (bukan MySQL asli) untuk memeriksa pagination, presisi, tabel kosong, kolom V3, lock, dan kegagalan publikasi. Uji koneksi nyata harus dilakukan pada MySQL lokal pengguna. Django dan driver perlu diinstal di laptop; tidak ada kredensial atau data asli dalam ZIP.
