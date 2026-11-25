from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from etl.load.dimensions import prepare, execute

class Command(BaseCommand):
    help='Load dimensi MySQL ke datamart. Default dry-run; --apply untuk menulis. Tidak memuat facts.'
    requires_system_checks=[]
    def add_arguments(self, parser):
        parser.add_argument('--run-id',required=True)
        parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**o):
        try:
            p=prepare(settings.EXTRACT_ROOT,settings.EXTRACT_ROOT.parent/'canonical_v2',o['run_id'])
            with transaction.atomic(using='datamart'):
                with connections['datamart'].cursor() as cursor:
                    result=execute(cursor,p,apply=o['apply'])
        except Exception as exc:
            raise CommandError(f'Load dimensi ditolak; tidak ada commit dari proses gagal: {exc}') from exc
        self.stdout.write(f"{result['status']} | scope=DIMENSIONS_ONLY | fact_load_ready=false | cutoff={p['cutoff'].isoformat()}")
        for kind,counts in result['tables'].items():
            self.stdout.write(f"{kind}: insert={counts['insert']} | version={counts['version']} | unchanged={counts['unchanged']}")
        self.stdout.write(f"rows_written={result['rows_written']} | quality_warnings={p['warnings']}")
        if 'planned_writes' in result: self.stdout.write(f"planned_writes={result['planned_writes']}")
