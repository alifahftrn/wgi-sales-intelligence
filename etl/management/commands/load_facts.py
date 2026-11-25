from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from etl.load.dimensions import prepare
from etl.load.fact_writer import execute

class Command(BaseCommand):
    help='Load facts from verified real MySQL snapshot. Default dry-run; --apply writes atomically.'
    requires_system_checks=[]
    def add_arguments(self,parser):
        parser.add_argument('--run-id',required=True)
        parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**o):
        try:
            p=prepare(settings.EXTRACT_ROOT,settings.EXTRACT_ROOT.parent/'canonical_v2',o['run_id'])
            with transaction.atomic(using='datamart'):
                with connections['datamart'].cursor() as c:
                    c.execute("SET LOCAL statement_timeout = '60s'")
                    r=execute(c,p,o['apply'])
        except Exception as exc:
            raise CommandError(f'Fact load ditolak; transaksi gagal tidak di-commit: {exc}') from exc
        self.stdout.write(f"{r['status']} | scope=FACTS_ONLY | source_coverage=NOT_VERIFIED | cutoff={p['cutoff'].isoformat()}")
        for t,n in r.get('counts',{}).items(): self.stdout.write(f"{t}: planned_rows={n} | existing_rows={r['existing'][t]}")
        for k in ('unresolved_version_refs','actual_pack','actual_liter','actual_rupiah','planned_writes','planned_cache_removals','rows_written','cache_rows_removed'):
            if k in r: self.stdout.write(f'{k}={r[k]}')
