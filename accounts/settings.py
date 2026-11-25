"""Append-only configuration for the original WGI settings module."""
from django.core.exceptions import ImproperlyConfigured

def configure(s):
    secret = s.get('SECRET_KEY', '')
    if len(secret) < 32 or secret == 'replace-with-local-random-secret':
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY to a private random secret of at least 32 characters in .env.')
    if not s.get('DEBUG'):
        raise ImproperlyConfigured('WGI Authentication V1 is localhost development only; production security is not configured.')
    for app in ('django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions', 'accounts'):
        if app not in s['INSTALLED_APPS']:
            s['INSTALLED_APPS'].append(app)
    for middleware in ('django.contrib.sessions.middleware.SessionMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'accounts.middleware.LocalRoleGuard'):
        if middleware not in s['MIDDLEWARE']:
            s['MIDDLEWARE'].append(middleware)
    # Starter router denies migrations in all existing databases. Do not change it.
    s['AUTH_USER_MODEL'] = 'accounts.User'
    s['AUTHENTICATION_BACKENDS'] = ['accounts.backend.EmailBackend']
    s['LOGIN_URL'] = 'accounts:login'
    root = s['BASE_DIR'] / '.local' / 'auth_sessions'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    s['SESSION_ENGINE'] = 'django.contrib.sessions.backends.file'
    s['SESSION_FILE_PATH'] = str(root)
    s['SESSION_COOKIE_NAME'] = 'wgi_sessionid'
    s['SESSION_COOKIE_HTTPONLY'] = True
    s['SESSION_COOKIE_SAMESITE'] = 'Lax'
    s['SESSION_COOKIE_AGE'] = 1800
    s['SESSION_EXPIRE_AT_BROWSER_CLOSE'] = True
    s['SESSION_COOKIE_SECURE'] = False  # HTTP loopback only
    s['AUTH_PASSWORD_VALIDATORS'] = [
        {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', 'OPTIONS':{'user_attributes':['name','email']}},
        {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS':{'min_length':12}},
        {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
    ]
