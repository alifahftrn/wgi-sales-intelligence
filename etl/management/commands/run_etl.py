"""One command for MySQL ETL. Dry-run by default; explicit --apply."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from etl.services import extract
from etl.pipeline import pipeline_lock, prepare_run, load_atomic


class Command(BaseCommand):
    help = 'Run full MySQL ETL; preview by default. --apply atomically loads dimensions and facts.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--source', choices=['mysql'], default='mysql')
        parser.add_argument('--run-id', help='Reuse a real existing Extract run; no new extraction')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        stage = 'LOCK'
        def progress(name, message):
            nonlocal stage
            stage = name
            self.stdout.write(f'{name} | {message}')
        try:
            with pipeline_lock(settings.EXTRACT_ROOT.parent):
                p, summary = prepare_run(settings.EXTRACT_ROOT, o['run_id'], extract=extract, progress=progress)
                stage = 'LOAD'
                self.stdout.write('LOAD | START | dimensions_and_facts_same_transaction')
                with transaction.atomic(using='datamart', durable=True):
                    with connections['datamart'].cursor() as c:
                        c.execute("SET LOCAL statement_timeout = '60s'")
                        result = load_atomic(c, p, apply=o['apply'])
                # Report successful commit only after atomic context exits.
                stage = 'REPORT'
                d, f = result['dimensions'], result['facts']
                self.stdout.write(f'DIMENSIONS | {d["status"]} | rows_written={d["rows_written"]} | planned_writes={d.get("planned_writes",0)}')
                if f is None:
                    self.stdout.write('FACTS | DEFERRED_UNTIL_APPLY | rows_written=0')
                else:
                    self.stdout.write(f'FACTS | {f["status"]} | rows_written={f["rows_written"]} | cache_rows_removed={f["cache_rows_removed"]}')
                self.stdout.write(f'{result["status"]} | run-id={p["run_id"]} | source_coverage=NOT_VERIFIED | fact_db_check={result["fact_db_check"]}')
                self.stdout.write(f'actual_pack={summary["actual_pack"]} | actual_liter={summary["actual_liter"]} | actual_rupiah={summary["actual_rupiah"]}')
        except Exception as exc:
            # A report/connection interruption after commit can make status uncertain;
            # verify logs and rerun the same run-id, rather than claiming rollback.
            raise CommandError(f'ETL berhenti pada {stage}: {exc}. Periksa etl_log sebelum retry; gunakan run-id yang sama jika tersedia.') from exc
