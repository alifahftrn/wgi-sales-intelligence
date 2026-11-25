-- WGI Sales Intelligence | sales_datamart | Tahap 1
-- Jalankan sekali di Query Tool database sales_datamart (PostgreSQL).
-- Hanya membuat 4 tabel baru di PostgreSQL dan mengisi kalender.
-- Tidak mengakses MySQL. Tidak membuat database baru.
BEGIN;

DO $$
BEGIN
    IF current_database() <> 'sales_datamart' THEN
        RAISE EXCEPTION 'Database salah: %. Gunakan sales_datamart.', current_database();
    END IF;
END;
$$;

CREATE TABLE public.dim_tanggal (
    tanggal date PRIMARY KEY,
    hari smallint NOT NULL CHECK (hari BETWEEN 1 AND 31),
    bulan smallint NOT NULL CHECK (bulan BETWEEN 1 AND 12),
    kuartal smallint NOT NULL CHECK (kuartal BETWEEN 1 AND 4),
    semester smallint NOT NULL CHECK (semester BETWEEN 1 AND 2),
    tahun integer NOT NULL,
    nama_bulan varchar(15) NOT NULL
);

CREATE TABLE public.dim_produk (
    id_produk_versi bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    kode_produk text NOT NULL CHECK (btrim(kode_produk) <> ''),
    kode_apc_lama text,
    nama_produk varchar(150) NOT NULL,
    brand varchar(50) NOT NULL,
    jenis_produk varchar(10) NOT NULL,
    segment varchar(20) NOT NULL,
    kemasan_liter numeric(10,3) NOT NULL CHECK (kemasan_liter > 0),
    isi_karton integer NOT NULL CHECK (isi_karton > 0),
    liter_per_karton numeric(12,3) NOT NULL CHECK (liter_per_karton > 0),
    berlaku_mulai timestamptz NOT NULL,
    berlaku_sampai timestamptz,
    aktif boolean NOT NULL DEFAULT true,
    UNIQUE (source_system, kode_produk, berlaku_mulai),
    CHECK (berlaku_sampai IS NULL OR berlaku_sampai > berlaku_mulai),
    CHECK (aktif = (berlaku_sampai IS NULL))
);
CREATE UNIQUE INDEX uq_dim_produk_aktif
    ON public.dim_produk (source_system, kode_produk) WHERE aktif;

CREATE TABLE public.dim_distributor (
    id_distributor_versi bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    kode_distributor text NOT NULL CHECK (btrim(kode_distributor) <> ''),
    nama_distributor varchar(120) NOT NULL,
    area varchar(20) NOT NULL,
    region varchar(50) NOT NULL,
    wilayah varchar(80) NOT NULL,
    berlaku_mulai timestamptz NOT NULL,
    berlaku_sampai timestamptz,
    aktif boolean NOT NULL DEFAULT true,
    UNIQUE (source_system, kode_distributor, berlaku_mulai),
    CHECK (berlaku_sampai IS NULL OR berlaku_sampai > berlaku_mulai),
    CHECK (aktif = (berlaku_sampai IS NULL))
);
CREATE UNIQUE INDEX uq_dim_distributor_aktif
    ON public.dim_distributor (source_system, kode_distributor) WHERE aktif;

CREATE TABLE public.etl_log (
    id_run bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_system text NOT NULL CHECK (btrim(source_system) <> ''),
    run_key text NOT NULL UNIQUE,
    extract_ref text,
    mulai_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    selesai_at timestamptz,
    cutoff_at timestamptz NOT NULL,
    trigger varchar(10) NOT NULL CHECK (trigger IN ('MANUAL','SCHEDULED')),
    status varchar(20) NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING','SUCCESS','FAILED','PARTIAL')),
    rows_read bigint CHECK (rows_read >= 0),
    rows_written bigint CHECK (rows_written >= 0),
    rows_quarantine bigint CHECK (rows_quarantine >= 0),
    pesan_error text,
    ref_karantina text,
    CHECK (selesai_at IS NULL OR selesai_at >= mulai_at),
    CHECK ((status = 'RUNNING') = (selesai_at IS NULL))
);
CREATE INDEX ix_etl_log_cutoff ON public.etl_log (source_system, cutoff_at DESC);

COMMENT ON TABLE public.dim_produk IS 'SCD2: satu versi per kode sumber; batas [mulai,sampai). Validasi overlap seluruh interval wajib pada loader.';
COMMENT ON TABLE public.dim_distributor IS 'SCD2: satu versi per kode sumber; batas [mulai,sampai). Validasi overlap seluruh interval wajib pada loader.';
COMMENT ON COLUMN public.dim_produk.berlaku_mulai IS 'Waktu versi teramati sejak ETL, bukan otomatis tanggal historis sebelum ETL.';
COMMENT ON COLUMN public.dim_distributor.berlaku_mulai IS 'Waktu versi teramati sejak ETL, bukan otomatis tanggal historis sebelum ETL.';
COMMENT ON TABLE public.etl_log IS 'Satu baris per eksekusi ETL. Waktu disimpan sebagai timestamptz; cutoff bisnis ditentukan dalam WIB.';

-- Kalender saja, bukan data penjualan. Tahun dapat diperluas nanti.
INSERT INTO public.dim_tanggal (tanggal,hari,bulan,kuartal,semester,tahun,nama_bulan)
SELECT d,
       EXTRACT(DAY FROM d)::smallint,
       EXTRACT(MONTH FROM d)::smallint,
       EXTRACT(QUARTER FROM d)::smallint,
       CASE WHEN EXTRACT(MONTH FROM d) <= 6 THEN 1 ELSE 2 END,
       EXTRACT(YEAR FROM d)::integer,
       (ARRAY['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'])[EXTRACT(MONTH FROM d)::integer]
FROM (
    SELECT DATE '2020-01-01' + n AS d
    FROM generate_series(0, DATE '2035-12-31' - DATE '2020-01-01') AS s(n)
) AS kalender;

COMMIT;

-- Verifikasi: 4 tabel fondasi; kalender 5844 baris; tiga tabel lain kosong.
SELECT 'dim_tanggal' AS nama_tabel, COUNT(*) AS jumlah_baris FROM public.dim_tanggal
UNION ALL SELECT 'dim_produk', COUNT(*) FROM public.dim_produk
UNION ALL SELECT 'dim_distributor', COUNT(*) FROM public.dim_distributor
UNION ALL SELECT 'etl_log', COUNT(*) FROM public.etl_log;
