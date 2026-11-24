-- OPSIONAL: jalankan sebagai admin MySQL, BUKAN sebagai akun aplikasi.
-- Ubah placeholder password sebelum menjalankan. Jangan gunakan password contoh.
-- Hanya untuk MySQL lokal. Jika akun sudah ada, jangan jalankan CREATE ulang.
CREATE USER 'wgi_extract'@'127.0.0.1' IDENTIFIED BY 'GANTI_PASSWORD_UNIK';
GRANT SELECT ON `salesdashboard`.`asp` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`asp_detail` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`delivery_order` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`delivery_order_detail` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`distributor` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`forecast` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`forecast_detail` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`harga_produk` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`produk` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`purchase_order` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`purchase_order_detail` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`revisi_forecast` TO 'wgi_extract'@'127.0.0.1';
GRANT SELECT ON `salesdashboard`.`revisi_forecast_detail` TO 'wgi_extract'@'127.0.0.1';

-- Jalankan GRANT berikut hanya setelah tabel histori V3 benar-benar dibuat:
-- GRANT SELECT ON `salesdashboard`.`riwayat_master_produk` TO 'wgi_extract'@'127.0.0.1';
-- GRANT SELECT ON `salesdashboard`.`riwayat_master_distributor` TO 'wgi_extract'@'127.0.0.1';
-- GRANT SELECT ON `salesdashboard`.`riwayat_outstanding` TO 'wgi_extract'@'127.0.0.1';
