"""Explicit offline recovery; never deletes pipeline locks or rolls back data."""
import re
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from etl.manual_jobs import Journal, BusyError


class Command(BaseCommand):
    help = 'Mark a stopped manual worker INTERRUPTED after manual verification.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--job-id', required=True)
        parser.add_argument('--confirm-stopped', action='store_true')

    def handle(self, *args, **options):
        job_id = options['job_id']
        if not options['confirm_stopped'] or not re.fullmatch(r'[0-9a-f]{32}', job_id):
            raise CommandError('Verify worker stopped, then use valid job ID and --confirm-stopped.')
        journal = Journal(settings.EXTRACT_ROOT.parent)
        if not journal.path.is_file():
            raise CommandError('Manual journal unavailable')
        try:
            changed = journal.interrupt(job_id)
        except BusyError as exc:
            raise CommandError(str(exc)) from exc
        if not changed:
            raise CommandError('No active job with this ID')
        self.stdout.write('INTERRUPTED | Verify PostgreSQL etl_log before retry; no rollback implied.')
