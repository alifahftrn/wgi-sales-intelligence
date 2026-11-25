from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.quality.demo import create_demo
from etl.transform.order_engine import run_preview

class Command(BaseCommand):
    help='Preview PO/DO and actual sales; no database writes.'
    requires_system_checks=[]

    def add_arguments(self, parser):
        group=parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--run-id')
        group.add_argument('--demo',action='store_true')

    def handle(self,*args,**options):
        base=settings.EXTRACT_ROOT.parent
        try:
            if options['demo']:
                run=create_demo(base/'quality_demo')
                canonical=base/'quality_demo'/'canonical_v2'
                self.stdout.write(f'DEMO ONLY | run-id={run}')
            else:
                run=options['run_id']; canonical=base/'canonical_v2'
            result,path=run_preview(canonical,base/'transform_v1',run,demo=options['demo'])
        except Exception as exc:
            raise CommandError(f'Transform preview ditolak: {exc}') from exc
        self.stdout.write('PREVIEW_ONLY | load_ready=false')
        for k,v in result['summary'].items(): self.stdout.write(f'{k}={v}')
        self.stdout.write(f'output={path}')
