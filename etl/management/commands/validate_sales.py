from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.quality.validator import read_run, validate
from etl.quality.demo import create_demo

class Command(BaseCommand):
    help='Read-only relationship validation; --demo creates isolated synthetic files only.'
    requires_system_checks=[]
    def add_arguments(self, parser):
        group=parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--run-id'); group.add_argument('--demo',action='store_true')
    def handle(self,*args,**options):
        try:
            if options['demo']:
                root=settings.EXTRACT_ROOT.parent/'quality_demo'
                run=create_demo(root); canonical=root/'canonical_v2'
                self.stdout.write(f'DEMO ONLY | run-id={run}')
            else:
                run=options['run_id']; canonical=settings.EXTRACT_ROOT.parent/'canonical_v2'
            result=validate(read_run(canonical,run))
        except Exception as exc:
            raise CommandError(f'Validasi gagal: {exc}') from exc
        for issue in result['issues']:
            self.stdout.write(f"{issue['level']} | {issue['rule']} | {issue['count']}")
        self.stdout.write(f"{result['status']} | rows={result['rows']} | transaction_rows={result['transaction_rows']} | errors={result['errors']} | warnings={result['warnings']} | load_ready=false")
        if result['status']=='FAIL': raise CommandError('Ada pelanggaran relasi; jangan load.')
