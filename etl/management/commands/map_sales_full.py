from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.mapping.full_engine import map_full_run

class Command(BaseCommand):
    help = 'Canonical V2: map all 13 MySQL datasets without writing any database.'
    requires_system_checks = []
    def add_arguments(self, parser):
        parser.add_argument('--run-id', required=True)
    def handle(self, *args, **options):
        run_id = options['run_id']
        try:
            result = map_full_run(settings.EXTRACT_ROOT, settings.EXTRACT_ROOT.parent/'canonical_v2', run_id)
        except Exception as exc:
            raise CommandError(f'Mapping V2 gagal: {exc}') from exc
        for table, counts in result['tables'].items():
            self.stdout.write(f"{table}: read={counts['rows_read']} | ready={counts['ready']} | quarantine={counts['quarantine']}")
        self.stdout.write(f"{result['status']} | MYSQL_FULL | read={result['rows_read']} | ready={result['ready']} | quarantine={result['quarantine']}")
        self.stdout.write(f'.local/canonical_v2/mysql/{run_id}')
