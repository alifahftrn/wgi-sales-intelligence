"""Internal worker: only a previously reserved PENDING job can execute."""
import re
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from etl.manual_jobs import Journal, execute_job


class Command(BaseCommand):
    help = 'Execute one reserved manual ETL job; not a public trigger.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--job-id', required=True)

    def handle(self, *args, **options):
        job_id = options['job_id']
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            raise CommandError('Invalid job ID')
        journal = Journal(settings.EXTRACT_ROOT.parent)
        if not journal.path.is_file():
            raise CommandError('Manual journal unavailable')

        def run(*, apply, stdout):
            call_command('run_etl', source='mysql', apply=apply, stdout=stdout, no_color=True)

        if not execute_job(journal, job_id, run):
            raise CommandError('Manual job not completed; check status and etl_log before retry.')
