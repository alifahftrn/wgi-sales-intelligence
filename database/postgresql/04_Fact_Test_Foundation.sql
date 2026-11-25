-- WGI Sales Intelligence | Tahap 2 | PostgreSQL sales_datamart_scd_test
-- Jalankan sekali setelah 01_PostgreSQL_Fondasi_Data_Mart.sql berhasil.
-- Tidak mengubah MySQL. Tidak mengisi transaksi dummy. Tidak DROP/DELETE.
-- BIGINT pack harus dalam rentang signed PostgreSQL; loader menolak overflow.
-- Identitas sumber dan relasi versi dimensi diperiksa loader, termasuk histori yang belum diketahui.
BEGIN;
DO $$
BEGIN
    IF current_database() <> 'sales_datamart_scd_test' THEN
        RAISE EXCEPTION 'Database salah: %. Gunakan sales_datamart_scd_test.', current_database();
    END IF;
    IF to_regclass('public.dim_tanggal') IS NULL OR
       to_regclass('public.dim_produk') IS NULL OR
       to_regclass('public.dim_distributor') IS NULL OR
       to_regclass('public.etl_log') IS NULL THEN
        RAISE EXCEPTION 'Jalankan SQL fondasi dahulu.';
    END IF;
END;
$$;

-- 1. Detail PO/DO: satu baris per detail sumber, bukan hasil JOIN PO x DO.
-- PO: tanggal transaksi = tanggal PO. DO: tanggal transaksi = tanggal kirim.
-- Kode sumber dipertahankan walaupun versi historis dimensi belum diketahui.
CREATE TABLE public.fact_order_delivery (
    id_order_delivery bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    jenis_record text NOT NULL CHECK (jenis_record IN ('PO','DO')),
    id_detail_sumber text NOT NULL CHECK (btrim(id_detail_sumber) <> ''),
    id_po_detail_sumber text NOT NULL,
    id_po_sumber text NOT NULL,
    no_po text NOT NULL,
    id_do_sumber text,
    no_do text,
    tanggal_po date NOT NULL REFERENCES public.dim_tanggal(tanggal),
    tanggal_transaksi date NOT NULL REFERENCES public.dim_tanggal(tanggal),
    kode_produk text NOT NULL,
    kode_distributor text NOT NULL,
    id_produk_versi bigint REFERENCES public.dim_produk(id_produk_versi),
    id_distributor_versi bigint REFERENCES public.dim_distributor(id_distributor_versi),
    status_sumber text,
    valid_analitik boolean NOT NULL,
    qty_pack bigint NOT NULL CHECK (qty_pack > 0),
    qty_batal_pack bigint CHECK (qty_batal_pack >= 0 AND qty_batal_pack <= qty_pack),
    id_harga_sumber text,
    liter_per_pack numeric(12,3) CHECK (liter_per_pack > 0),
    harga_dasar_pack numeric(18,2) CHECK (harga_dasar_pack >= 0),
    tarif_ppn numeric(7,6) CHECK (tarif_ppn BETWEEN 0 AND 1),
    harga_pack_setelah_ppn numeric(22,2) CHECK (harga_pack_setelah_ppn >= 0),
    total_liter numeric(32,3) GENERATED ALWAYS AS (qty_pack * liter_per_pack) STORED,
    total_rupiah numeric(42,2) GENERATED ALWAYS AS (qty_pack * harga_pack_setelah_ppn) STORED,
    alasan_outstanding text,
    keterangan_outstanding text,
    source_updated_at timestamptz,
    id_run bigint NOT NULL REFERENCES public.etl_log(id_run),
    UNIQUE (source_system, jenis_record, id_detail_sumber),
    CHECK (tanggal_transaksi >= tanggal_po),
    CHECK ((jenis_record = 'PO' AND id_detail_sumber = id_po_detail_sumber
            AND id_do_sumber IS NULL AND no_do IS NULL AND tanggal_transaksi = tanggal_po)
        OR (jenis_record = 'DO' AND id_do_sumber IS NOT NULL AND no_do IS NOT NULL
            AND qty_batal_pack IS NULL AND alasan_outstanding IS NULL AND keterangan_outstanding IS NULL))
);
CREATE INDEX ix_order_delivery_date ON public.fact_order_delivery(tanggal_transaksi, jenis_record) WHERE valid_analitik;
CREATE INDEX ix_order_delivery_po ON public.fact_order_delivery(source_system, id_po_detail_sumber);
CREATE INDEX ix_order_delivery_product ON public.fact_order_delivery(kode_produk, kode_distributor, tanggal_transaksi);
COMMENT ON TABLE public.fact_order_delivery IS 'Grain satu detail PO atau satu detail DO; actual hanya DO valid. Jangan menjumlah qty PO dan DO sebagai satu metrik. Loader memvalidasi relasi DO-PO, status, sumber dimensi, dan overdelivery.';
COMMENT ON COLUMN public.fact_order_delivery.liter_per_pack IS 'Snapshot volume transaksi terverifikasi; DO mengikuti aturan snapshot volume DO, harga mengikuti PO. NULL bila belum diketahui; jangan mengganti dengan master saat ini tanpa bukti.';
COMMENT ON COLUMN public.fact_order_delivery.qty_batal_pack IS 'Hanya untuk PO. NULL berarti belum diketahui, bukan nol.';

-- 2. Forecast history: baseline dan setiap revisi sumber disimpan terpisah.
CREATE TABLE public.fact_forecast_history (
    id_forecast_history bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    jenis_forecast text NOT NULL CHECK (jenis_forecast IN ('BASELINE','REVISI')),
    id_detail_sumber text NOT NULL,
    id_forecast_sumber text NOT NULL,
    id_revisi_sumber text,
    bulan date NOT NULL REFERENCES public.dim_tanggal(tanggal),
    kode_produk text NOT NULL,
    kode_distributor text NOT NULL,
    id_produk_versi bigint REFERENCES public.dim_produk(id_produk_versi),
    id_distributor_versi bigint REFERENCES public.dim_distributor(id_distributor_versi),
    minggu_ke integer,
    waktu_penetapan timestamptz NOT NULL,
    teramati_at timestamptz NOT NULL,
    qty_pack bigint NOT NULL CHECK (qty_pack >= 0),
    total_liter numeric(32,3) NOT NULL CHECK (total_liter >= 0),
    total_rupiah numeric(42,2) NOT NULL CHECK (total_rupiah >= 0),
    id_run bigint NOT NULL REFERENCES public.etl_log(id_run),
    UNIQUE (source_system, jenis_forecast, id_detail_sumber),
    CHECK (EXTRACT(DAY FROM bulan) = 1),
    CHECK ((jenis_forecast = 'BASELINE' AND id_revisi_sumber IS NULL AND minggu_ke IS NULL)
        OR (jenis_forecast = 'REVISI' AND id_revisi_sumber IS NOT NULL AND minggu_ke IS NOT NULL AND minggu_ke > 0))
);
CREATE UNIQUE INDEX uq_forecast_baseline ON public.fact_forecast_history(source_system, bulan, kode_produk, kode_distributor) WHERE jenis_forecast = 'BASELINE';
CREATE UNIQUE INDEX uq_forecast_revisi_produk ON public.fact_forecast_history(source_system, id_revisi_sumber, kode_produk) WHERE jenis_forecast = 'REVISI';
CREATE INDEX ix_forecast_cutoff ON public.fact_forecast_history(source_system, bulan, kode_produk, kode_distributor, waktu_penetapan DESC);
COMMENT ON TABLE public.fact_forecast_history IS 'Grain detail baseline atau detail revisi. Pilih revisi terakhir per SKU/distributor/bulan berdasarkan cutoff bisnis, carry-forward baseline/revisi sebelumnya; jangan SUM seluruh revisi. Loader menjaga urutan timestamp dan tie-break ID sumber yang deterministik serta menolak konflik data immutable.';
COMMENT ON COLUMN public.fact_forecast_history.teramati_at IS 'Waktu pertama kali record teramati ETL, berbeda dari waktu penetapan sumber; untuk laporan as-known gunakan kedua cutoff sesuai definisi.';

-- 3. Agregasi bulanan. Satu baris per jenis metrik dan versi dimensi.
-- ACTUAL dapat terdiri dari beberapa versi dimensi. Target tiap jenis hanya sekali
-- per natural key. Forecast terakhir juga satu kali per natural key.
CREATE TABLE public.fact_sales_monthly (
    id_sales_monthly bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    bulan date NOT NULL REFERENCES public.dim_tanggal(tanggal),
    kode_produk text NOT NULL,
    kode_distributor text NOT NULL,
    id_produk_versi bigint REFERENCES public.dim_produk(id_produk_versi),
    id_distributor_versi bigint REFERENCES public.dim_distributor(id_distributor_versi),
    jenis_metrik text NOT NULL CHECK (jenis_metrik IN ('ACTUAL','ASP_INTERNAL','ASP_EXTERNAL','FORECAST_LATEST')),
    qty_pack bigint CHECK (qty_pack >= 0),
    total_liter numeric(32,3) CHECK (total_liter >= 0),
    total_rupiah numeric(42,2) CHECK (total_rupiah >= 0),
    id_asp_detail_sumber text,
    waktu_penetapan_asp timestamptz,
    id_forecast_history bigint REFERENCES public.fact_forecast_history(id_forecast_history),
    cutoff_at timestamptz NOT NULL,
    id_run bigint NOT NULL REFERENCES public.etl_log(id_run),
    UNIQUE NULLS NOT DISTINCT (source_system, bulan, kode_produk, kode_distributor, jenis_metrik, id_produk_versi, id_distributor_versi),
    CHECK (EXTRACT(DAY FROM bulan) = 1),
    CHECK ((jenis_metrik IN ('ASP_INTERNAL','ASP_EXTERNAL') AND id_asp_detail_sumber IS NOT NULL AND id_forecast_history IS NULL)
        OR (jenis_metrik = 'FORECAST_LATEST' AND id_forecast_history IS NOT NULL AND id_asp_detail_sumber IS NULL AND waktu_penetapan_asp IS NULL)
        OR (jenis_metrik = 'ACTUAL' AND id_asp_detail_sumber IS NULL AND waktu_penetapan_asp IS NULL AND id_forecast_history IS NULL))
);
CREATE UNIQUE INDEX uq_sales_monthly_plan ON public.fact_sales_monthly(source_system, bulan, kode_produk, kode_distributor, jenis_metrik) WHERE jenis_metrik <> 'ACTUAL';
CREATE INDEX ix_sales_monthly_period ON public.fact_sales_monthly(bulan, jenis_metrik);
COMMENT ON TABLE public.fact_sales_monthly IS 'Cache agregasi bulanan terkini, bukan seluruh versi forecast. ASP Internal dan External tidak dijumlahkan menjadi satu target. Bandingkan actual dan target/forecast pada natural key sebelum rollup, bukan join banyak versi dimensi. Periode parsial dihitung dari detail DO, target prorata kalender, forecast dari history sesuai cutoff.';
COMMENT ON COLUMN public.fact_sales_monthly.total_rupiah IS 'NULL jika nilai tidak lengkap/tidak diketahui. Loader tidak boleh SUM sebagian nilai seolah lengkap. ASP/forecast sesuai nilai sumber yang telah divalidasi.';

-- 4. Outstanding snapshot: satu detail PO per cutoff ETL.
-- Snapshot bukan transaksi tambahan, tidak dijumlah antar tanggal.
CREATE TABLE public.fact_outstanding_snapshot (
    id_snapshot bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    cutoff_at timestamptz NOT NULL,
    tanggal_snapshot date NOT NULL REFERENCES public.dim_tanggal(tanggal),
    id_po_detail_sumber text NOT NULL,
    id_po_sumber text NOT NULL,
    no_po text NOT NULL,
    tanggal_po date NOT NULL REFERENCES public.dim_tanggal(tanggal),
    kode_produk text NOT NULL,
    kode_distributor text NOT NULL,
    id_produk_versi bigint REFERENCES public.dim_produk(id_produk_versi),
    id_distributor_versi bigint REFERENCES public.dim_distributor(id_distributor_versi),
    status_po text,
    valid_analitik boolean NOT NULL,
    qty_po_pack bigint NOT NULL CHECK (qty_po_pack > 0),
    qty_do_pack bigint NOT NULL CHECK (qty_do_pack >= 0 AND qty_do_pack <= qty_po_pack),
    qty_batal_pack bigint CHECK (qty_batal_pack >= 0 AND qty_batal_pack <= qty_po_pack - qty_do_pack),
    qty_outstanding_bod bigint GENERATED ALWAYS AS (CASE WHEN valid_analitik THEN qty_po_pack - qty_do_pack ELSE 0 END) STORED,
    qty_outstanding_eligible bigint GENERATED ALWAYS AS (CASE WHEN valid_analitik THEN qty_po_pack - qty_do_pack - qty_batal_pack ELSE 0 END) STORED,
    liter_per_pack numeric(12,3) CHECK (liter_per_pack > 0),
    harga_pack_setelah_ppn numeric(22,2) CHECK (harga_pack_setelah_ppn >= 0),
    aging_hari integer GENERATED ALWAYS AS (tanggal_snapshot - tanggal_po) STORED,
    alasan_outstanding text,
    keterangan_outstanding text,
    id_run bigint NOT NULL REFERENCES public.etl_log(id_run),
    UNIQUE (source_system, cutoff_at, id_po_detail_sumber),
    CHECK (tanggal_snapshot = (cutoff_at AT TIME ZONE 'Asia/Jakarta')::date),
    CHECK (tanggal_snapshot >= tanggal_po)
);
CREATE INDEX ix_outstanding_cutoff ON public.fact_outstanding_snapshot(source_system, cutoff_at DESC);
CREATE INDEX ix_outstanding_po ON public.fact_outstanding_snapshot(source_system, id_po_detail_sumber, cutoff_at DESC);
COMMENT ON TABLE public.fact_outstanding_snapshot IS 'Snapshot saldo detail PO pada cutoff WIB. Pilih satu cutoff lengkap per sumber, bukan SUM lintas cutoff. Loader memasukkan juga saldo nol/PO tidak valid sesuai aturan bisnis dan menangani kehilangan record sumber. Pembatalan seluruh PO sebelum kirim dikecualikan dari PO valid; pembatalan sisa setelah kirim tetap outstanding BOD tetapi tidak fulfillment-eligible.';
COMMENT ON COLUMN public.fact_outstanding_snapshot.qty_outstanding_eligible IS 'NULL jika kuantitas pembatalan belum diketahui untuk PO valid. Jangan COALESCE menjadi nol tanpa bukti.';

COMMIT;

-- Verifikasi: 8 tabel Data Mart; fact table kosong hingga Load Engine berjalan.
SELECT 'dim_tanggal' AS nama_tabel, count(*) AS jumlah_baris FROM public.dim_tanggal
UNION ALL SELECT 'dim_produk', count(*) FROM public.dim_produk
UNION ALL SELECT 'dim_distributor', count(*) FROM public.dim_distributor
UNION ALL SELECT 'etl_log', count(*) FROM public.etl_log
UNION ALL SELECT 'fact_order_delivery', count(*) FROM public.fact_order_delivery
UNION ALL SELECT 'fact_forecast_history', count(*) FROM public.fact_forecast_history
UNION ALL SELECT 'fact_sales_monthly', count(*) FROM public.fact_sales_monthly
UNION ALL SELECT 'fact_outstanding_snapshot', count(*) FROM public.fact_outstanding_snapshot;
