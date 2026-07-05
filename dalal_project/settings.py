"""
Django settings for dalal_project — production-ready configuration.
Supports SQLite (dev) and PostgreSQL (production) via environment variables.
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


DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-dev-only-change-me'
    else:
        raise ValueError('SECRET_KEY environment variable must be set in production')

# Custom domain — daluailiraq.com on Railway
custom_domain = os.getenv('CUSTOM_DOMAIN', 'daluailiraq.com')

# Configure ALLOWED_HOSTS (Django supports subdomain wildcards via leading dot)
ALLOWED_HOSTS = _parse_csv_env('ALLOWED_HOSTS')
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + [
    '.railway.app',
    'muq.up.railway.app',
    'muqq.up.railway.app',
    'healthcheck.railway.app',
])

if custom_domain:
    ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + [custom_domain, f'www.{custom_domain}'])

railway_public_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if railway_public_domain:
    ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + [railway_public_domain])

if DEBUG:
    ALLOWED_HOSTS = _unique(ALLOWED_HOSTS + ['localhost', '127.0.0.1', '[::1]'])

# Configure CSRF_TRUSTED_ORIGINS (no wildcard support in Django)
CSRF_TRUSTED_ORIGINS = _unique([
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
    'http://127.0.0.1:64813',
    'http://127.0.0.1:62854',
    'http://localhost:62854',
    'https://muq.up.railway.app',
    'https://muqq.up.railway.app',
    'http://muq.up.railway.app',
    'http://muqq.up.railway.app',
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
    'properties',
]

MIDDLEWARE = [
    'properties.middleware.HealthCheckMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # Temporarily disabled enterprise middleware to isolate redirect issue
    # 'properties.middleware_enterprise.RateLimitMiddleware',
    # 'properties.middleware_enterprise.SecurityHeadersMiddleware',
    # 'properties.middleware_enterprise.XSSProtectionMiddleware',
    # 'properties.middleware_enterprise.SQLInjectionProtectionMiddleware',
    # 'properties.middleware_enterprise.AdminIPRestrictionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'properties.middleware.MaintenanceModeMiddleware',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'dalal_project.wsgi.application'
ASGI_APPLICATION = 'dalal_project.asgi.application'

# Optional WebSocket support (enable with USE_WEBSOCKETS=True and Redis)
USE_WEBSOCKETS = os.getenv('USE_WEBSOCKETS', 'False').lower() == 'true'
if USE_WEBSOCKETS:
    try:
        import channels  # noqa: F401
        INSTALLED_APPS.insert(0, 'channels')
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
# PostgreSQL for production (Railway), SQLite for development only

import dj_database_url

# Detect Railway environment
is_railway = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_SERVICE_NAME')

# Try to get DATABASE_URL from Railway or environment variables
database_url = os.getenv('DATABASE_URL')

# Fallback for Railway: construct from individual variables if DATABASE_URL is not set
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
        print(f"WARNING: Invalid DATABASE_URL detected. Falling back to SQLite.")
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
    print("WARNING: Using SQLite fallback. Attach PostgreSQL on Railway for production.")
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

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
    WHITENOISE_MANIFEST_STRICT = False
    WHITENOISE_IGNORE_IF_NOT_FOUND = True
else:
    WHITENOISE_USE_FINDERS = True

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'

# --- Security ---
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Railway SSL termination - commented out to prevent redirect loops with HTTP access
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

if not DEBUG:
    # Railway handles SSL termination at the edge proxy level.
    # NEVER set SECURE_SSL_REDIRECT=True on Railway — it causes infinite redirect loops.
    SECURE_SSL_REDIRECT = False
    # Enable secure cookies in production
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Disable HSTS to prevent redirect loops on Railway
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Must be False so Django's JS can read the CSRF token
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# CSRF settings for Railway - simplified to prevent conflicts
CSRF_USE_SESSIONS = False
CSRF_COOKIE_AGE = 3600 * 24 * 7  # 7 days

# Session timeout (7 days)
SESSION_COOKIE_AGE = 3600 * 24 * 7

# --- File Upload Security ---
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# --- Cache (rate limiting + performance) ---
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

if os.getenv('REDIS_URL'):
    try:
        import django_redis  # noqa: F401
        CACHES['default'] = {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 50,
                    'retry_on_timeout': True,
                },
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'KEY_PREFIX': 'dalal',
            'TIMEOUT': 300,
        }
        CACHES['sessions'] = {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.getenv('REDIS_URL'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 20,
                    'retry_on_timeout': True,
                },
            },
            'KEY_PREFIX': 'dalal_sessions',
            'TIMEOUT': 3600,
        }
        SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
        SESSION_CACHE_ALIAS = 'sessions'
    except ImportError:
        print("WARNING: REDIS_URL set but django-redis is not installed. Using local memory cache.")

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

# Site
SITE_NAME = os.getenv('SITE_NAME', 'دلال')

# CORS Settings
# In production, never allow all origins for security
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only allow all in development
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
    # Add Railway domains for production
    cors_origins = _unique(cors_origins + [
        'https://muq.up.railway.app',
        'https://muqq.up.railway.app',
        'http://muq.up.railway.app',
        'http://muqq.up.railway.app',
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

# Security Headers for API
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

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
