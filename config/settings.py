import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "replace-with-local-random-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
# This starter has no authentication; only use on loopback for development.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = ["django.contrib.staticfiles", "etl"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request"]}}]
DATABASES = {
    "default": {"ENGINE": "django.db.backends.mysql", "NAME": os.getenv("MYSQL_DATABASE", "salesdashboard"), "USER": os.getenv("MYSQL_USER", "wgi_extract"), "PASSWORD": os.getenv("MYSQL_PASSWORD", ""), "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"), "PORT": os.getenv("MYSQL_PORT", "3306"), "OPTIONS": {"charset": "utf8mb4"}, "CONN_MAX_AGE": 0},
    "datamart": {"ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("PG_DATABASE", "sales_datamart"), "USER": os.getenv("PG_USER", "postgres"), "PASSWORD": os.getenv("PG_PASSWORD", ""), "HOST": os.getenv("PG_HOST", "127.0.0.1"), "PORT": os.getenv("PG_PORT", "5432"), "CONN_MAX_AGE": 0},
}
# No migrations in either database at Extract stage.
DATABASE_ROUTERS = ["config.db_router.ExtractOnlyRouter"]
LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EXTRACT_ROOT = BASE_DIR / ".local" / "extracts"
EXTRACT_BATCH_SIZE = int(os.getenv("EXTRACT_BATCH_SIZE", "1000"))

from accounts.settings import configure as configure_accounts

configure_accounts(globals())