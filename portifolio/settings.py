import os
from pathlib import Path

from decouple import Config, Csv, RepositoryEnv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = Config(RepositoryEnv(str(BASE_DIR / '.env')))


def read_env(name, default=None):
    try:
        value = ENV_FILE(name)
    except Exception:
        value = None

    if value is None:
        value = os.getenv(name)

    if value is None:
        return default

    return value


def read_bool_env(name, default=False):
    raw_value = read_env(name)
    if raw_value is None:
        return default

    normalized = str(raw_value).strip().lower()
    if normalized in {'1', 'true', 't', 'yes', 'y', 'on'}:
        return True
    if normalized in {'0', 'false', 'f', 'no', 'n', 'off'}:
        return False
    return default


def read_config(name, default=None, cast=None):
    value = read_env(name, default)
    if value is None or cast is None:
        return value

    if cast is bool:
        return read_bool_env(name, default=bool(default))

    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = read_env('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY is not configured.')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = read_bool_env('DEBUG', default=False)

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = Csv()(
    read_env('CSRF_TRUSTED_ORIGINS', 'https://andreporto.up.railway.app')
)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # My app
    'core',
]

AUTHENTICATION_BACKENDS = [
    'core.auth_backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'core:entrar'
LOGIN_REDIRECT_URL = 'core:licencas'
LOGOUT_REDIRECT_URL = 'core:index'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # serve para carregar os arquivos estaticos no modo Debug = False e para fazer o deploy da aplicação
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'portifolio.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'portifolio.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
#MEDIA_URL = '/media/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 
#MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

EMAIL_BACKEND = read_env(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)

EMAIL_HOST = read_config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = read_config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = read_config('EMAIL_HOST_USER', default='')
# Pode conter caracteres especiais; usamos os.environ para evitar parsing.
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = read_config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = read_config('EMAIL_USE_SSL', default=False, cast=bool)
DEFAULT_FROM_EMAIL = read_config(
    'DEFAULT_FROM_EMAIL',
    default=EMAIL_HOST_USER or 'no-reply@andreporto.up.railway.app',
)
PUBLIC_WEB_BASE_URL = read_config(
    'PUBLIC_WEB_BASE_URL',
    default='https://andreporto.up.railway.app',
).strip().rstrip('/')
CONTACT_EMAIL = read_config(
    'CONTACT_EMAIL',
    default=EMAIL_HOST_USER or DEFAULT_FROM_EMAIL or 'contato@example.com',
)


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
