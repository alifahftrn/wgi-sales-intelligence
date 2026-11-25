# Authentication V1 — local development

Prerequisite: ETL Monitoring V1. All files new except templates/etl_monitor_v1.html (adds portal link). The existing MySQL pengguna table is unmanaged and no migrations are required. PostgreSQL remains untouched. No new packages. Existing passwords and accounts are not changed; only Django-compatible password hashes authenticate. Unknown roles and duplicate emails are rejected. Role codes ADMIN, SALES, BOD are proposed project codes; verify company role policy later. Existing database email has no UNIQUE constraint; resolve duplicates with authorized DBA before production.

1. Backup current config files / commit previous work. Extract at project root. Inspect git status. Replace only the monitoring template. Add at end of config/settings.py:

```python
from accounts.settings import configure as configure_accounts
configure_accounts(globals())
```

2. Add at end of config/urls.py, after existing urlpatterns:

```python
from django.urls import include
urlpatterns += [path("accounts/", include("accounts.urls"))]
```

3. Ensure DJANGO_SECRET_KEY in private .env is a random secret of >=32 characters (not the example placeholder). Generate a new one only if current key is missing/weak: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Copy output locally; don't send or commit it. Keep DEBUG=1, bind 127.0.0.1 only. Existing ExtractOnlyRouter remains. Do NOT run migrate. File sessions reside in .local/auth_sessions (must be private and gitignored); local single host only. No production readiness: no HTTPS, login throttling, account recovery, centralized sessions, or revocation admin UI yet. Session expiry 30 minutes based on session age, not a guaranteed idle timer. `python manage.py clearsessions` periodically cleans expired local session files.

4. `python -m unittest discover -v` (target 131). `python manage.py check`. `python manage.py test accounts.django_checks -v 2` (six Django tests, mocked DB, no migrations). If Django reports error, send sanitized output.

5. Only for local development, use a new test email, not an existing user. Command asks for a new password via hidden prompt; at least 12 characters. `python manage.py create_wgi_admin --email admin.dev@example.invalid --name "Admin Development"`. This inserts one real account into local MySQL pengguna; it does not edit old rows. Requires SELECT and INSERT permissions on pengguna. If account already exists or permissions fail, stop; do not grant broad permissions or overwrite an existing password. Email is not delivered anywhere.

6. `python manage.py runserver 127.0.0.1:8000`. Visit /etl/monitoring/ in a private browser window: should redirect to /accounts/login/. Sign in, open monitoring, use Akun / Keluar to return to portal and sign out via POST. After logout monitoring must redirect again. Existing Extract routes also protected. SALES and BOD are recognized but cannot access ETL; no actual Sales/BOD portal features yet. All other Django views default admin-only until role-specific routing is implemented. CLI scheduler is unchanged. Manual Run ETL not included.

7. Commit only source files, settings and urls. Never add .env, local sessions, company data, or logs. Production requires dedicated authentication/security design and validated roles. No plaintext password migration or reuse.
