import sys
from getpass import getpass
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction, DatabaseError
from accounts.models import User

class Command(BaseCommand):
    help = 'Create a NEW local ADMIN account; never overwrite an existing account.'
    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--name', required=True)

    def handle(self, *args, **opts):
        conn = connections['default']
        if not settings.DEBUG or conn.vendor != 'mysql' or conn.settings_dict['NAME'] != 'salesdashboard' or conn.settings_dict.get('HOST') not in {'127.0.0.1','localhost','::1'}:
            raise CommandError('Hanya MySQL salesdashboard development.')
        email, name = opts['email'].strip().lower(), opts['name'].strip()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError('Email tidak valid.') from exc
        if not name or len(name) > 100 or len(email) > 150:
            raise CommandError('Nama/email melebihi batas atau kosong.')
        if not sys.stdin.isatty():
            raise CommandError('Gunakan terminal interaktif agar password tidak masuk command history.')
        user = User(name=name, email=email, role='ADMIN')
        password = getpass('Password baru: ')
        if password != getpass('Ulangi password: '):
            raise CommandError('Password tidak sama.')
        if len(password) > 1024:
            raise CommandError('Password terlalu panjang.')
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        user.set_password(password)
        try:
            # Cooperative lock for this provisioning command; external SQL writers are not covered.
            with conn.cursor() as cur:
                cur.execute("SELECT GET_LOCK('wgi_create_local_admin_v1', 5)")
                if cur.fetchone()[0] != 1:
                    raise CommandError('Provisioning sedang berjalan.')
                try:
                    with transaction.atomic(using='default'):
                        if User.objects.using('default').filter(email__iexact=email).exists():
                            raise CommandError('Email sudah ada; akun lama tidak diubah.')
                        user.save(using='default', force_insert=True)
                finally:
                    cur.execute("SELECT RELEASE_LOCK('wgi_create_local_admin_v1')")
                    cur.fetchone()
        except DatabaseError as exc:
            raise CommandError('Gagal membuat akun; periksa izin INSERT dan koneksi MySQL lokal. Jangan ubah password lama secara langsung.') from exc
        self.stdout.write(self.style.SUCCESS('ADMIN_CREATED | role=ADMIN | password_hashed=true'))
