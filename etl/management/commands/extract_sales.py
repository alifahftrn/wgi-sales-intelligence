from django.core.management.base import BaseCommand, CommandError
from etl.services import extract

class Command(BaseCommand):
    help = 'Extract MySQL or configured Excel dataset to local staging; no database writes.'
    requires_system_checks = []
    def add_arguments(self, parser):
        parser.add_argument('--source', choices=['mysql', 'excel'], default='mysql')
        parser.add_argument('--file', help='Path to .xlsx for Excel source')
    def handle(self, *args, **options):
        source = options['source']
        try:
            result = extract(source=source, file=options['file'])
        except Exception as exc:
            raise CommandError(f'Extract gagal: {exc}') from exc
        for table in result['tables']:
            self.stdout.write(f"{table['table']}: {table['rows']} baris")
        for warning in result['warnings']:
            self.stdout.write(self.style.WARNING(warning))
        root = 'extracts' if source == 'mysql' else 'extracts_excel'
        self.stdout.write(self.style.SUCCESS(f"SUCCESS: {result['total_rows']} baris | .local/{root}/{result['run_id']}"))
