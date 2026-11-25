from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.quality.demo import create_demo
from etl.transform.plan_engine import run_preview

class Command(BaseCommand):
    help='Preview ASP, forecast, achievement and monthly growth; no DB writes.'
    requires_system_checks=[]
    def add_arguments(self,parser):
        group=parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--run-id'); group.add_argument('--demo',action='store_true')
        parser.add_argument('--plan-cutoff',help='ISO 8601 with offset; filters plans only')
    def handle(self,*args,**options):
        base=settings.EXTRACT_ROOT.parent
        try:
            cutoff=datetime.fromisoformat(options['plan_cutoff']) if options['plan_cutoff'] else None
            if options['demo']:
                run=create_demo(base/'quality_demo'); canonical=base/'quality_demo'/'canonical_v2'; self.stdout.write(f'DEMO ONLY | run-id={run}')
            else:
                run=options['run_id']; canonical=base/'canonical_v2'
            result,path=run_preview(canonical,base/'transform_v2',run,demo=options['demo'],plan_cutoff=cutoff)
        except Exception as exc:
            raise CommandError(f'Transform V2 ditolak: {exc}') from exc
        self.stdout.write('PREVIEW_ONLY | load_ready=false')
        for k,v in result['summary'].items(): self.stdout.write(f'{k}={v}')
        self.stdout.write(f'output={path}')
