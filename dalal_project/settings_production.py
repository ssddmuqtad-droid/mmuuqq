"""
Django settings for dalal_project — production-ready configuration.
Supports SQLite (dev) and PostgreSQL (production) via environment variables.
Updated: 2026-07-12-16-22 - Force Railway rebuild
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_csv_env(name, default=''):
    """Parse comma-separated env values; ignore placeholder entries."""
    raw = os.getenv(name, default)
    if not raw:
        return []
    invalid_items = {'.', '*'}
    return [
        item.strip()
        for item in raw.split(',')
        if item.strip() and item.strip() not in invalid_items
    ]


def _unique(items):
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-dev-only-change-me'
    else:
        raise ValueError('SECRET_KEY environment variable must be set in production')

# Custom domain
custom_domain = os.getenv('CUSTOM_DOMAIN', 'daluailiraq.com')

# Configure ALLOWED_HOSTS
# Start with '*' to accept all hosts (bypass ALLOWED_HOSTS check)
ALLOWED_HOSTS = ['*']

# Add additional hosts from environment
ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + _parse_csv_env('ALLOWED_HOSTS'))

# Explicitly add Railway domains
ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + [
    '.railway.app',
    'healthcheck.railway.app',
    '.up.railway.app',
    'mup.up.railway.app',
    'muq.up.railway.app',
    'muqq.up.railway.app',
    'localhost',
    '127.0.0.1',
])

if custom_domain:
    ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + [custom_domain, f'www.{custom_domain}'])

railway_public_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if railway_public_domain:
    ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + [railway_public_domain])

if DEBUG:
    ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + ['localhost', '127.0.0.1', '[::1]'])

# Log ALLOWED_HOSTS for debugging
import logging
logger = logging.getLogger(__name__)
logger.info(f"DEBUG={DEBUG}, ALLOWED_HOSTS={ALLOWED_HOSTS}")
logger.info(f"RAILWAY_PUBLIC_DOMAIN={railway_public_domain}")
logger.info(f"CUSTOM_DOMAIN={custom_domain}")

# CSRF_TRUSTED_ORIGINS
if DEBUG:
    railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:62950',
        'http://localhost:62950',
        railway_domain and f'https://{railway_domain}',
        'https://mup.up.railway.app',
        'https://muq.up.railway.app',
        'https://muqq.up.railway.app',
    ]
    # Filter out None values
    CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
else:
    CSRF_TRUSTED_ORIGINS = _unique([
        'https://mup.up.railway.app',
        'https://muq.up.railway.app',
        'https://muqq.up.railway.app',
    ] + _parse_csv_env('CSRF_TRUSTED_ORIGINS'))

if railway_public_domain:
    CSRF_TRUSTED_ORIGINS = _unique(CSRF_TRUSTED_ORIGINS + [f'https://{railway_public_domain}'])

if custom_domain:
    CSRF_TRUSTED_ORIGINS = _unique(CSRF_TRUSTED_ORIGINS + [
        f'https://{custom_domain}',
        f'https://www.{custom_domain}',
    ])

SILENCED_SYSTEM_CHECKS = ['security.W004', '4_0.E001']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
    'corsheaders',
    'django_filters',
    'rest_framework',
    'drf_yasg',
    'dalal_project',
    'properties',
    'social_django',
]

# Force logging to verify INSTALLED_APPS
import sys
print(f"=== SETTINGS_PRODUCTION.PY LOADED ===", file=sys.stderr)
print(f"INSTALLED_APPS: {INSTALLED_APPS}", file=sys.stderr)
print(f"Properties in INSTALLED_APPS: {'properties' in INSTALLED_APPS}", file=sys.stderr)

# Log INSTALLED_APPS for debugging
logger.info(f"INSTALLED_APPS: {INSTALLED_APPS}")
logger.info(f"Properties in INSTALLED_APPS: {'properties' in INSTALLED_APPS}")

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'properties.middleware.HealthCheckMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'properties.middleware.MaintenanceModeMiddleware',
    'properties.middleware.SubscriptionCheckMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dalal_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'properties.context_processors.site_context',
                'properties.context_processors.oauth_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'dalal_project.wsgi.application'

# Optional WebSocket support
USE_WEBSOCKETS = os.getenv('USE_WEBSOCKETS', 'False').lower() == 'true'
if USE_WEBSOCKETS:
    try:
        import channels  # noqa: F401
        if 'channels' not in INSTALLED_APPS:
            INSTALLED_APPS.insert(0, 'channels')
        ASGI_APPLICATION = 'dalal_project.asgi.application'
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels.layers.InMemoryChannelLayer',
            },
        }
        if os.getenv('REDIS_URL'):
            CHANNEL_LAYERS = {
                'default': {
                    'BACKEND': 'channels_redis.core.RedisChannelLayer',
                    'CONFIG': {
                        'hosts': [os.getenv('REDIS_URL')],
                    },
                },
            }
    except ImportError:
        USE_WEBSOCKETS = False

# --- Database Configuration ---
import dj_database_url

database_url = os.getenv('DATABASE_URL')

if not database_url:
    db_name = os.getenv('DB_NAME') or os.getenv('POSTGRES_DB')
    db_user = os.getenv('DB_USER') or os.getenv('POSTGRES_USER')
    db_password = os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')
    db_host = os.getenv('DB_HOST') or os.getenv('POSTGRES_HOST')
    db_port = os.getenv('DB_PORT') or os.getenv('POSTGRES_PORT', '5432')

    if db_name and db_user and db_password and db_host:
        database_url = f'postgres://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

# Validate database URL - reject placeholder values
if database_url:
    invalid_patterns = ['@host:', 'user:password@']
    if any(pattern in database_url for pattern in invalid_patterns):
        database_url = None

if database_url:
    DATABASES = {
        'default': dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
elif os.getenv('ALLOW_SQLITE_FALLBACK', 'False').lower() == 'true':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    raise ValueError(
        "DATABASE_URL must be set in production. "
        "Add a PostgreSQL service on Railway or set ALLOW_SQLITE_FALLBACK=True."
    )

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Baghdad'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.ManifestStaticFilesStorage'
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = '/'

# --- Security ---
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

USE_X_FORWARDED_HOST = True

if not DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

CSRF_USE_SESSIONS = False
CSRF_COOKIE_AGE = 3600 * 24 * 7  # 7 days
SESSION_COOKIE_AGE = 3600 * 24 * 7

# --- File Upload Security ---
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# --- Cache ---
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'dalal-cache',
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'dalal-sessions',
        'TIMEOUT': 3600,
    },
}

if os.getenv('REDIS_URL') and not DEBUG:
    try:
        import django_redis  # noqa: F401
        CACHES['default'] = {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'KEY_PREFIX': 'dalal',
            'TIMEOUT': 300,
        }
    except ImportError:
        pass

# --- Logging ---
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'dalal.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'WARNING', 'propagate': False},
        'properties': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
    },
}

# --- Messages ---
from django.contrib.messages import constants as message_constants

MESSAGE_TAGS = {
    message_constants.DEBUG: 'info',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'error',
}

SITE_NAME = os.getenv('SITE_NAME', 'دلال')

# --- Social Authentication ---
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
]

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '').strip()
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '').strip()
SOCIAL_AUTH_FACEBOOK_KEY = os.getenv('SOCIAL_AUTH_FACEBOOK_KEY', '').strip()
SOCIAL_AUTH_FACEBOOK_SECRET = os.getenv('SOCIAL_AUTH_FACEBOOK_SECRET', '').strip()

RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_PUBLIC_DOMAIN:
    BASE_URL = f'https://{RAILWAY_PUBLIC_DOMAIN}'
elif custom_domain:
    BASE_URL = f'https://{custom_domain}'
else:
    BASE_URL = 'http://127.0.0.1:8000'

SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]
SOCIAL_AUTH_GOOGLE_OAUTH2_EXTRA_DATA = ['first_name', 'last_name', 'picture']
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = f'{BASE_URL}/social/complete/google-oauth2/'

SOCIAL_AUTH_FACEBOOK_OAUTH2_SCOPE = ['email', 'public_profile']
SOCIAL_AUTH_FACEBOOK_OAUTH2_EXTRA_DATA = ['first_name', 'last_name', 'picture']
SOCIAL_AUTH_FACEBOOK_OAUTH2_REDIRECT_URI = f'{BASE_URL}/social/complete/facebook/'

SOCIAL_AUTH_CSRF_IGNORE = True
SOCIAL_AUTH_ALLOW_REDIRECT_URI_CHANGE = True
SOCIAL_AUTH_REDIRECT_IS_HTTPS = not DEBUG

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'properties.social_auth.save_profile_picture',
    'properties.social_auth.save_social_data',
    'properties.social_auth.social_auth_error',
)

SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/dashboard/'
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login/'
SOCIAL_AUTH_NEW_ASSOCIATION_REDIRECT_URL = '/dashboard/'
SOCIAL_AUTH_DISCONNECT_REDIRECT_URL = '/settings/social/'

SOCIAL_AUTH_USER_MODEL = 'auth.User'
SOCIAL_AUTH_FORCE_RANDOM_USERNAME = False
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True
SOCIAL_AUTH_SLUGIFY_USERNAMES = 'lower'
SOCIAL_AUTH_SANITIZE_USERNAMES = True

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
if not DEBUG:
    CORS_ALLOW_ALL_ORIGINS = False
    cors_origins = _parse_csv_env('CORS_ALLOWED_ORIGINS')
    if custom_domain:
        cors_origins = _unique(cors_origins + [
            f'https://{custom_domain}',
            f'https://www.{custom_domain}',
        ])
    cors_origins = _unique(cors_origins + [
        'https://muq.up.railway.app',
        'https://muqq.up.railway.app',
    ])
    if railway_public_domain:
        cors_origins = _unique(cors_origins + [f'https://{railway_public_domain}'])
    if cors_origins:
        CORS_ALLOWED_ORIGINS = cors_origins

# Email Settings
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@daluailiraq.com')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', 'admin@daluailiraq.com')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# --- REST Framework Settings ---
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
    'VERSION_PARAM': 'version',
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
}
