import logging
from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qsl
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure-ufku8$$kjf0#co7&178se$03iv+4g&az=o3^8099!&yvnu46tv'

DEBUG = True

ALLOWED_HOSTS = ['*'] # Allowed for hackathon development


INSTALLED_APPS = [
    "daphne",
    "django_eventstream",
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_q',
    'drf_spectacular',
    'django_sqids',
    'anymail',

    'core',
    'plans',
    'transactions',
    'webhooks',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'payplan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

ASGI_APPLICATION = "payplan.asgi.application"
WSGI_APPLICATION = 'payplan.wsgi.application'


tmpPostgres = urlparse(os.getenv("DATABASE_URL"))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': tmpPostgres.path.replace('/', ''),
        'USER': tmpPostgres.username,
        'PASSWORD': tmpPostgres.password,
        'HOST': tmpPostgres.hostname,
        'PORT': 5432,
        'OPTIONS': dict(parse_qsl(tmpPostgres.query)),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'core.User'

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'payplan.authentication.CookieJWTAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'payplan.utils.exception_handler.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'PayPlan API',
    'DESCRIPTION': 'API for PayPlan recurring payment enforcement.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

Q_CLUSTER = {
    'name': 'PayPlanQueue',
    'workers': 4,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'orm': 'default'
}

DJANGO_SQIDS_MIN_LENGTH = 7

EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
DEFAULT_FROM_EMAIL = "PayPlan <covenantcrackslord03@gmail.com>"

SERVICE_BASE_URL   = os.getenv("SERVICE_BASE_URL", "http://localhost:8000")

ANYMAIL = {
    "BREVO_API_KEY": os.getenv("BREVO_API_KEY"),
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EVENTSTREAM_REDIS = {
    'host': 'redis',
    'port': 6379,
    'db': 0,
}

SENTRY_DSN = os.environ.get('SENTRY_DSN')

sentry_logging = LoggingIntegration(
    sentry_logs_level=logging.INFO,
)

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), sentry_logging],
        traces_sample_rate=0.1, 
        profiles_sample_rate=0.1, 
        send_default_pii=True, 
        enable_logs=True,
        environment=os.environ.get("ENVIRONMENT", "production"),
    )
    
SUB_ENGINE_API_KEY = os.environ.get('SUB_ENGINE_API_KEY')