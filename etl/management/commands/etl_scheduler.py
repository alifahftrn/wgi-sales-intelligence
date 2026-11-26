"""Run scheduler independently from Django HTTP server."""
import json
import sqlite3
import time
from django.conf import settings
from django.db import connections
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from etl.scheduler import Scheduler


class Command(BaseCommand):
    help = 'Local daily WIB ETL scheduler. Disabled by default. Never run Windows task concurrently.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['status','configure','run','tick','recover'])
        parser.add_argument('--time', dest='clock')
        parser.add_argument('--mode', choices=['PREVIEW','APPLY'])
        enabled = parser.add_mutually_exclusive_group()
        enabled.add_argument('--enable', action='store_true')
        enabled.add_argument('--disable', action='store_true')
        parser.add_argument('--confirm-apply', action='store_true')
        parser.add_argument('--slot')
        parser.add_argument('--confirm-stopped', action='store_true')

    def handle(self, *args, **o):
        scheduler = Scheduler(settings.EXTRACT_ROOT.parent)
        action = o['action']
        try:
            if action == 'configure':
                if not (o['enable'] or o['disable']) or not o['clock'] or not o['mode']:
                    raise ValueError('Specify --time HH:MM --mode PREVIEW/APPLY and --enable or --disable')
                scheduler.configure(enabled=o['enable'],clock=o['clock'],mode=o['mode'],confirm_apply=o['confirm_apply'])
                self.stdout.write('SCHEDULE_CONFIGURED')
            elif action == 'status':
                config, jobs = scheduler.status()
                self.stdout.write(json.dumps({'config':config,'history':jobs}, indent=2))
            elif action == 'recover':
                if not o['slot'] or not scheduler.recover(o['slot'],confirmed=o['confirm_stopped']):
                    raise ValueError('No recoverable RUNNING slot; inspect journal')
                self.stdout.write('SCHEDULE_INTERRUPTED')
            else:
                def run(*, apply, stdout):
                    connections.close_all()
                    try:
                        call_command('run_etl',source='mysql',apply=apply,stdout=stdout,no_color=True)
                    finally:
                        connections.close_all()
                if action == 'tick':
                    result = scheduler.tick(run)
                    self.stdout.write(result)
                    if result in {'FAILED','STATUS_UNCONFIRMED','ACTIVE_OR_INTERRUPTED'}:
                        raise CommandError('Inspect status and etl_log; no automatic retry')
                else:
                    self.stdout.write('SCHEDULER_RUNNING | WIB | poll=10s | Ctrl+C to stop while idle')
                    previous = None
                    while True:
                        result = scheduler.tick(run)
                        if result != previous:
                            self.stdout.write(result)
                            previous = result
                        time.sleep(10)
        except KeyboardInterrupt:
            self.stdout.write('SCHEDULER_STOPPED | Inspect status if interrupted during ETL')
        except (sqlite3.Error,OSError,ValueError) as exc:
            # Do not expose local path or DB error details.
            raise CommandError('Scheduler rejected or unavailable. Check arguments, local journal and locks.') from None
