"""Integration test against a dedicated, empty local PostgreSQL database."""
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.load.dimensions import execute

TEST_DB = 'sales_datamart_scd_test'
T = datetime(2026, 1, 1, tzinfo=timezone.utc)
P = dict(kode_produk='SCD-TEST-P', kode_apc_lama=None, nama_produk='Synthetic product', brand='Brand A', jenis_produk='2W', segment='Top', kemasan_liter='0.800', isi_karton=12, liter_per_karton='9.600')
D = dict(kode_distributor='SCD-TEST-D', nama_distributor='Synthetic distributor', area='Jawa', region='Region 1', wilayah='Test')


def prepared(n, day, brand='Brand A', region='Region 1'):
    return dict(run_id=f'SCD_TEST_{n}', digest=f'{n:064x}', cutoff=T+timedelta(days=day), data={'produk':[{**P,'brand':brand}], 'distributor':[{**D,'region':region}]})


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def counts(c):
    result=[]
    for name in ('dim_produk','dim_distributor','etl_log'):
        c.execute(f'SELECT count(*) FROM public.{name}')
        result.append(c.fetchone()[0])
    return tuple(result)


def histories(c):
    c.execute('SELECT brand, berlaku_mulai, berlaku_sampai, aktif FROM public.dim_produk ORDER BY berlaku_mulai')
    p=c.fetchall()
    c.execute('SELECT region, berlaku_mulai, berlaku_sampai, aktif FROM public.dim_distributor ORDER BY berlaku_mulai')
    return p,c.fetchall()


def scenarios(c, integrity_error):
    c.execute('SELECT current_database()')
    require(c.fetchone()[0]==TEST_DB,'Database bukan khusus test')
    c.execute("SET LOCAL lock_timeout = '5s'")
    c.execute('LOCK TABLE public.dim_produk, public.dim_distributor, public.etl_log IN SHARE ROW EXCLUSIVE MODE')
    require(counts(c)==(0,0,0),'Tabel test harus kosong; tidak ada data yang dihapus')
    r=execute(c,prepared(1,0),test_only=True)
    require(r['planned_writes']==2 and counts(c)==(0,0,0),'Dry run gagal')
    r=execute(c,prepared(1,0),True,test_only=True)
    require(r['rows_written']==2 and counts(c)==(1,1,1),'Initial load gagal')
    yield 'PASS | initial_load'
    r=execute(c,prepared(1,0),True,test_only=True)
    require(r['status']=='ALREADY_APPLIED' and counts(c)==(1,1,1),'Idempotency gagal')
    yield 'PASS | idempotency'
    r=execute(c,prepared(2,1),True,test_only=True)
    require(r['rows_written']==0 and counts(c)==(1,1,2),'Unchanged snapshot gagal')
    yield 'PASS | unchanged_snapshot'
    r=execute(c,prepared(3,2,'Brand B','Region 2'),True,test_only=True)
    require(r['rows_written']==4 and counts(c)==(2,2,3),'Version load gagal')
    cut=T+timedelta(days=2)
    expected_p=[('Brand A',T,cut,False),('Brand B',cut,None,True)]
    expected_d=[('Region 1',T,cut,False),('Region 2',cut,None,True)]
    require(histories(c)==(expected_p,expected_d),'Interval atau status aktif salah')
    yield 'PASS | product_brand_history'
    yield 'PASS | distributor_region_history'
    try:
        execute(c,prepared(4,1),True,test_only=True)
    except ValueError as exc:
        require('snapshot tidak lebih baru' in str(exc),'Penolakan snapshot bukan karena cutoff')
    else:
        raise RuntimeError('Snapshot lama tidak ditolak')
    require(counts(c)==(2,2,3),'Snapshot lama mengubah data')
    yield 'PASS | stale_snapshot_rejected'
    c.execute('SAVEPOINT scd_failure_test')
    try:
        # The product is written first; NULL region then triggers a real PG NOT NULL error.
        execute(c,prepared(5,3,'Brand C',None),True,test_only=True)
    except integrity_error:
        c.execute('ROLLBACK TO SAVEPOINT scd_failure_test')
        c.execute('RELEASE SAVEPOINT scd_failure_test')
    else:
        raise RuntimeError('Expected PostgreSQL integrity error not raised')
    require(counts(c)==(2,2,3) and histories(c)==(expected_p,expected_d),'Rollback tidak mengembalikan histori')
    yield 'PASS | database_failure_rollback'


class Command(BaseCommand):
    help='Uji SCD2 dengan fixture sintetik di sales_datamart_scd_test lokal; semua data test di-rollback.'
    requires_system_checks=[]

    def handle(self,*args,**options):
        import psycopg
        cfg=settings.DATABASES['datamart']
        host=cfg.get('HOST') or '127.0.0.1'
        if host not in ('127.0.0.1','localhost','::1'):
            raise CommandError('Hanya server PostgreSQL lokal yang diizinkan.')
        try:
            with psycopg.connect(dbname=TEST_DB, host=host, port=cfg.get('PORT') or 5432, user=cfg['USER'], password=cfg.get('PASSWORD',''), connect_timeout=5) as conn:
                try:
                    with conn.cursor() as c:
                        for message in scenarios(c,psycopg.IntegrityError):
                            self.stdout.write(message)
                finally:
                    conn.rollback()
                with conn.cursor() as c:
                    require(counts(c)==(0,0,0),'Database test tidak kosong setelah rollback')
                conn.rollback()
        except Exception as exc:
            raise CommandError(f'SCD integration gagal: {exc}') from exc
        self.stdout.write(self.style.SUCCESS('SCD_INTEGRATION_PASS | scenarios=7 | test_rows_persisted=0'))
