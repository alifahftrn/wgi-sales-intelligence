"""Exercise combined load transaction against the existing isolated PostgreSQL test DB."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.management.commands.verify_fact_integration import TEST_DB, ALL, counts, fixture_data, prepared, require
from etl.pipeline import load_atomic


def scenarios(c, integrity_error):
    c.execute('SELECT current_database()')
    require(c.fetchone()[0] == TEST_DB, 'Database bukan test')
    c.execute("SET LOCAL lock_timeout = '5s'")
    c.execute('LOCK TABLE '+', '.join('public.'+t for t in ALL)+' IN SHARE ROW EXCLUSIVE MODE')
    empty = (0,)*7
    require(counts(c) == empty, 'Tabel test harus kosong; tidak ada penghapusan otomatis')
    p = prepared(1, fixture_data())
    r = load_atomic(c,p,test_only=True)
    require(r['fact_db_check']=='DEFERRED_UNTIL_APPLY' and counts(c)==empty,'Preview mengubah database')
    yield 'PASS | pipeline_preview_no_writes'
    c.execute('SAVEPOINT pipeline_failure')
    # Fail in the last fact table, after dimension and earlier fact DML.
    c.execute('ALTER TABLE public.fact_outstanding_snapshot ADD CONSTRAINT pipeline_test_failure CHECK (qty_po_pack < 0)')
    try:
        load_atomic(c,p,apply=True,test_only=True)
    except integrity_error:
        c.execute('ROLLBACK TO SAVEPOINT pipeline_failure')
        c.execute('RELEASE SAVEPOINT pipeline_failure')
    else:
        raise RuntimeError('Expected PostgreSQL CHECK error not raised')
    require(counts(c)==empty,'Rollback gabungan dimensi dan fact gagal')
    yield 'PASS | combined_dimension_fact_rollback'
    r=load_atomic(c,p,apply=True,test_only=True)
    require(r['status']=='ETL_APPLIED' and counts(c)==(1,1,2,7,3,6,3),'Combined load gagal')
    yield 'PASS | combined_load'
    r=load_atomic(c,p,apply=True,test_only=True)
    require(r['status']=='ETL_ALREADY_APPLIED' and counts(c)==(1,1,2,7,3,6,3),'Combined idempotency gagal')
    yield 'PASS | combined_idempotency'


class Command(BaseCommand):
    help='Test combined dimension/fact load on local dedicated test database; rollback fixtures.'
    requires_system_checks=[]
    def handle(self,*args,**options):
        import psycopg
        cfg=settings.DATABASES['datamart']; host=cfg.get('HOST') or '127.0.0.1'
        if host not in ('127.0.0.1','localhost','::1'):
            raise CommandError('Hanya PostgreSQL lokal diizinkan')
        try:
            with psycopg.connect(dbname=TEST_DB,host=host,port=cfg.get('PORT') or 5432,user=cfg['USER'],password=cfg.get('PASSWORD',''),connect_timeout=5) as conn:
                try:
                    with conn.cursor() as c:
                        c.execute("SET LOCAL statement_timeout = '60s'")
                        for line in scenarios(c,psycopg.IntegrityError): self.stdout.write(line)
                finally:
                    conn.rollback()
                with conn.cursor() as c:
                    require(counts(c)==(0,)*7,'Database test tidak kosong setelah rollback')
                conn.rollback()
        except Exception as exc:
            raise CommandError(f'Pipeline integration gagal: {exc}') from exc
        self.stdout.write('PIPELINE_INTEGRATION_PASS | scenarios=4 | test_rows_persisted=0')
