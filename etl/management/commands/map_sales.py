from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.mapping.engine import map_run

class Command(BaseCommand):
    help = 'Map product only from a specific raw Extract run into canonical local staging.'
    requires_system_checks = []
    def add_arguments(self, parser):
        parser.add_argument('--source', choices=['mysql','excel'], required=True)
        parser.add_argument('--run-id', required=True)
    def handle(self, *args, **options):
        source, run_id = options['source'], options['run_id']
        root = settings.EXTRACT_ROOT if source == 'mysql' else settings.EXTRACT_ROOT.parent/'extracts_excel'
        try:
            result = map_run(root, settings.EXTRACT_ROOT.parent/'canonical', source, run_id)
        except Exception as exc:
            raise CommandError(f'Mapping gagal: {exc}') from exc
        self.stdout.write(f"{result['status']} | PRODUCT_ONLY | read={result['rows_read']} | ready={result['ready']} | incomplete={result['incomplete']} | quarantine={result['quarantine']}")
        self.stdout.write(f'.local/canonical/{source}/{run_id}')
        if result['unmapped_datasets']:
            self.stdout.write('Dataset lain belum dipetakan: ' + ', '.join(result['unmapped_datasets']))
