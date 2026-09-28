"""
Django settings for core project.

Configuration is driven entirely by environment variables.
Copy .env.example to .env in the backend/ directory and fill in real values
before running the server. Never commit .env or any file containing
production credentials.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Paths & Environment Loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
    load_dotenv(BASE_DIR.parent / '.env')
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Core security — all sourced from environment, no hardcoded values
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-fallback-key-replace-before-production')

DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() == 'true'

# ALLOWED_HOSTS: space-separated list in the env var, e.g. "example.com api.example.com"
_raw_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split() if h.strip()] if _raw_hosts.strip() else []

# In local dev with DEBUG=True, localhost variants are always allowed for convenience.
if DEBUG:
    ALLOWED_HOSTS += ['localhost', '127.0.0.1', '[::1]']


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'whitenoise.runserver_nostatic',  # serve collected static files in prod

    # Local apps
    'accounts',
    'academic',
    'attendance',
    'ai_assistant',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',       # static serving (prod)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTH_USER_MODEL = 'accounts.User'


# ---------------------------------------------------------------------------
# REST framework + JWT
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}


# ---------------------------------------------------------------------------
# CORS
# CORS_ALLOWED_ORIGINS: space-separated list, e.g. "http://localhost:5173 https://myapp.com"
# ---------------------------------------------------------------------------

_raw_origins = os.getenv('CORS_ALLOWED_ORIGINS', '')
if _raw_origins.strip():
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split() if o.strip()]
    CORS_ALLOW_ALL_ORIGINS = False
else:
    # Fallback: allow all only in debug mode; deny all in production
    CORS_ALLOW_ALL_ORIGINS = DEBUG
    if not DEBUG and not _raw_origins.strip():
        import warnings
        warnings.warn(
            "CORS_ALLOWED_ORIGINS is not set and DEBUG is False. "
            "All cross-origin requests will be denied. "
            "Set CORS_ALLOWED_ORIGINS to your frontend URL.",
            RuntimeWarning,
            stacklevel=1,
        )

CORS_ALLOW_CREDENTIALS = True


# ---------------------------------------------------------------------------
# URLs + WSGI
# ---------------------------------------------------------------------------

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# ---------------------------------------------------------------------------
# Database
#
# Set MYSQL_DATABASE to switch to MySQL.  When absent, SQLite is used for
# local development without any additional setup.
#
# MySQL env vars: MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT
# SQLite env var: SQLITE_PATH (optional; defaults to backend/db.sqlite3)
# ---------------------------------------------------------------------------

if os.getenv('MYSQL_DATABASE'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ['MYSQL_DATABASE'],
            'USER': os.environ['MYSQL_USER'],
            'PASSWORD': os.environ['MYSQL_PASSWORD'],
            'HOST': os.getenv('MYSQL_HOST', '127.0.0.1'),
            'PORT': os.getenv('MYSQL_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
        }
    }
else:
    _sqlite_path = os.getenv('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3'))
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': _sqlite_path,
        }
    }


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise compressed static files for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ---------------------------------------------------------------------------
# Security hardening — only active when DEBUG is off (i.e. production)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
else:
    # Development: disable all HTTPS enforcement so plain HTTP works locally
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False


# ---------------------------------------------------------------------------
# Email — console backend for dev; configure via env for production
# ---------------------------------------------------------------------------

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@edumerge.ac.in')


# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
