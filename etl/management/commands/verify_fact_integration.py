"""Dedicated local PostgreSQL only; no fixture data committed."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.load.dimensions import execute as load_dim
from etl.load.fact_writer import execute, TABLES
from etl.quality.demo import create_demo
from etl.quality.validator import read_run

TEST_DB='sales_datamart_scd_test'
CUT=datetime.fromisoformat('2026-11-25T10:00:00+07:00')
ALL=('dim_produk','dim_distributor','etl_log',*TABLES)


def require(ok,message):
    if not ok: raise RuntimeError(message)


def counts(c):
    result=[]
    for t in ALL:
        c.execute(f'SELECT count(*) FROM public.{t}'); result.append(c.fetchone()[0])
    return tuple(result)


def fixture_data():
    with TemporaryDirectory() as d:
        root=Path(d); return read_run(root/'canonical_v2',create_demo(root))


def prepared(n,data):
    return dict(run_id=f'FACT_TEST_{n}',digest=f'{n:064x}',cutoff=CUT+timedelta(days=n-1),data=data)


def scenarios(c, integrity_error):
    c.execute('SELECT current_database()'); require(c.fetchone()[0]==TEST_DB,'Database bukan test')
    c.execute("SET LOCAL lock_timeout = '5s'")
    c.execute('LOCK TABLE '+', '.join('public.'+t for t in ALL)+' IN SHARE ROW EXCLUSIVE MODE')
    require(counts(c)==(0,)*7,'Tabel test harus kosong; tidak ada penghapusan otomatis')
    data=fixture_data(); p=prepared(1,data)
    load_dim(c,p,True,test_only=True)
    baseline=counts(c); r=execute(c,p,test_only=True)
    require(r['planned_writes']==19 and counts(c)==baseline,'Dry run tidak cocok')
    yield 'PASS | dry_run'
    r=execute(c,p,True,test_only=True)
    require(r['rows_written']==19 and r['unresolved_version_refs']==38 and counts(c)==(1,1,2,7,3,6,3),'Initial fact load gagal')
    c.execute("SELECT f.id_detail_sumber FROM public.fact_sales_monthly m JOIN public.fact_forecast_history f ON f.id_forecast_history=m.id_forecast_history WHERE m.jenis_metrik='FORECAST_LATEST'")
    require(c.fetchall()==[('2',)],'FK latest forecast salah')
    yield 'PASS | initial_load_and_forecast_fk'
    r=execute(c,p,True,test_only=True); require(r['status']=='ALREADY_APPLIED' and counts(c)==(1,1,2,7,3,6,3),'Idempotency gagal')
    yield 'PASS | idempotency'
    new=deepcopy(data); new['delivery_order_detail'][-2]['qty_pack']=45
    p2=prepared(2,new); load_dim(c,p2,True,test_only=True)
    before=counts(c)
    # Genuine PostgreSQL CHECK error after orders/forecast/cache operations.
    c.execute('SAVEPOINT fact_failure_test')
    c.execute('ALTER TABLE public.fact_outstanding_snapshot ADD CONSTRAINT test_failure CHECK (qty_do_pack <> 95)')
    try: execute(c,p2,True,test_only=True)
    except integrity_error:
        c.execute('ROLLBACK TO SAVEPOINT fact_failure_test'); c.execute('RELEASE SAVEPOINT fact_failure_test')
    else: raise RuntimeError('Expected PostgreSQL constraint error not raised')
    require(counts(c)==before,'Rollback count gagal')
    c.execute("SELECT sum(qty_pack) FROM public.fact_order_delivery WHERE jenis_record='DO' AND valid_analitik")
    require(c.fetchone()[0]==290,'Rollback perubahan DO gagal')
    yield 'PASS | database_failure_rollback'
    r=execute(c,p2,True,test_only=True)
    require(r['actual_pack']==295 and r['cache_rows_removed']==6 and counts(c)==(1,1,4,7,3,6,6),'Koreksi DO/cache atau snapshot gagal')
    c.execute('SELECT cutoff_at,sum(qty_outstanding_bod) FROM public.fact_outstanding_snapshot GROUP BY cutoff_at ORDER BY cutoff_at')
    require([r[1] for r in c.fetchall()]==[80,75],'Snapshot lama berubah')
    yield 'PASS | order_correction_and_snapshot_history'
    altered=deepcopy(new); altered['forecast_detail'][0]['forecast_pack']+=1
    # Mutate corresponding measures too so transformation stays internally consistent.
    from decimal import Decimal
    for k,delta in [('forecast_liter','9.600'),('forecast_rupiah','111000.00')]: altered['forecast_detail'][0][k]=str(Decimal(altered['forecast_detail'][0][k])+Decimal(delta))
    p3=prepared(3,altered); load_dim(c,p3,True,test_only=True)
    before=counts(c)
    try: execute(c,p3,True,test_only=True)
    except ValueError as exc: require('forecast immutable' in str(exc),'Penolakan bukan karena forecast immutable')
    else: raise RuntimeError('Forecast lama dapat diubah')
    require(counts(c)==before,'Penolakan forecast mengubah fact')
    yield 'PASS | immutable_forecast_rejected'


class Command(BaseCommand):
    help='Uji fact writer pada PostgreSQL lokal khusus test; rollback seluruh fixture.'
    requires_system_checks=[]
    def handle(self,*args,**options):
        import psycopg
        cfg=settings.DATABASES['datamart']; host=cfg.get('HOST') or '127.0.0.1'
        if host not in ('127.0.0.1','localhost','::1'): raise CommandError('Hanya PostgreSQL lokal diizinkan')
        try:
            with psycopg.connect(dbname=TEST_DB,host=host,port=cfg.get('PORT') or 5432,user=cfg['USER'],password=cfg.get('PASSWORD',''),connect_timeout=5) as conn:
                try:
                    with conn.cursor() as c:
                        c.execute("SET LOCAL statement_timeout = '60s'")
                        for line in scenarios(c,psycopg.IntegrityError): self.stdout.write(line)
                finally: conn.rollback()
                with conn.cursor() as c: require(counts(c)==(0,)*7,'Database test tidak kosong setelah rollback')
                conn.rollback()
        except Exception as exc: raise CommandError(f'Fact integration gagal: {exc}') from exc
        self.stdout.write('FACT_INTEGRATION_PASS | scenarios=6 | test_rows_persisted=0')
