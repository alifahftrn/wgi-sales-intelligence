from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from etl.load.fact_planner import build_plan, inspect, report, prepare, SPECS
from etl.quality.demo import create_demo
from etl.quality.validator import read_run

class Command(BaseCommand):
    help='Read-only fact load planner; no --apply. Demo does not connect to DB.'
    requires_system_checks=[]
    def add_arguments(self,parser):
        g=parser.add_mutually_exclusive_group(required=True)
        g.add_argument('--run-id'); g.add_argument('--demo',action='store_true')
    def handle(self,*args,**o):
        try:
            base=settings.EXTRACT_ROOT.parent
            if o['demo']:
                root=base/'quality_demo'; run=create_demo(root); data=read_run(root/'canonical_v2',run)
                cutoff=datetime.fromisoformat('2026-11-25T10:00:00+07:00')
                hist={k:[dict(r,**{pk:i+1},berlaku_mulai=cutoff,berlaku_sampai=None,aktif=True) for i,r in enumerate(data[k])] for k,(_,pk,_,_) in SPECS.items()}
                plan,summary=build_plan(data,cutoff,hist); existing=None
                self.stdout.write(f'DEMO ONLY | run-id={run}')
            else:
                p=prepare(settings.EXTRACT_ROOT,base/'canonical_v2',o['run_id'])
                with transaction.atomic(using='datamart'):
                    with connections['datamart'].cursor() as cursor:
                        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                        cursor.execute("SET LOCAL statement_timeout = '30s'")
                        plan,summary,existing=inspect(cursor,p)
            r=report(plan,summary,existing)
        except Exception as exc:
            raise CommandError(f'Fact plan ditolak: {exc}') from exc
        self.stdout.write('FACT_PLAN_ONLY | rows_written=0 | fact_load_ready=false')
        for t,n in r['counts'].items(): self.stdout.write(f'{t}: planned_rows={n}'+(f' | existing_rows={existing[t]}' if existing is not None else ''))
        for k in ('unresolved_version_refs','actual_pack','actual_liter','actual_rupiah'): self.stdout.write(f'{k}={r[k]}')
