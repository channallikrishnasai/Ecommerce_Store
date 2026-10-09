from pathlib import Path
from typing import (List, Dict, Tuple, Any)

from environ import Env

env = Env()

BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
Env.read_env(BASE_DIR / '.env')

SECRET_KEY: str = env.str('SECRET_KEY', '')
DEBUG: bool = env.bool('DEBUG', False)
ALLOWED_HOSTS: List[str] = env.list('ALLOWED_HOSTS', default=[])
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST: str = env.str('EMAIL_HOST', 'localhost')
EMAIL_PORT: int = env.int('EMAIL_PORT', 25)
EMAIL_HOST_USER: str = env.str('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD: str = env.str('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS: bool = env.bool('EMAIL_USE_TLS', False)
EMAIL_USE_SSL: bool = env.bool('EMAIL_USE_SSL', False)

ROOT_URLCONF: str = 'ecom.urls'
WSGI_APPLICATION: str = 'ecom.wsgi.application'
SITE_ID: int = 1
LOGIN_REDIRECT_URL: str = '/'

# Installed applications
# region
DJANGO_APPS: List[str] = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

REQUIREMENTS_APPS: List[str] = [
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'crispy_forms',
    'crispy_bootstrap4',
]

PROJECT_APPS: List[str] = [
    'cart',
    'core',
    'staff',
]
INSTALLED_APPS = [
    *DJANGO_APPS,
    *REQUIREMENTS_APPS,
    *PROJECT_APPS,
]
# endregion


DEFAULT_FROM_EMAIL = env.str('DEFAULT_FROM_EMAIL', '')
NOTIFY_EMAIL: str = env.str('NOTIFY_EMAIL', '')
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Middleware
# region
MIDDLEWARE: List[str] = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
# endregion

# Templates
# region
TEMPLATES: List[Dict[str, Any]] = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}, ]
# endregion

# Database
# region
DATABASES: Dict[str, Dict[str, Any]] = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env.str('DATABASE_NAME', 'django_ecommerce'),
        'USER': env.str('DATABASE_USER', 'postgres'),
        'PASSWORD': env.str('DATABASE_PASSWORD', ''),
        'HOST': env.str('DATABASE_HOST', 'localhost'),
        'PORT': env.str('DATABASE_PORT', '5432'),
    }
}
# endregion


# Authentication
# region
AUTH_PASSWORD_VALIDATORS: List[Dict[str, str]] = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

AUTHENTICATION_BACKENDS: Tuple[str, ...] = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION: str = 'mandatory'
# endregion

# Crispy
# region
CRISPY_TEMPLATE_PACK: str = 'bootstrap4'
# endregion

# Language and Timezone
# region
LANGUAGE_CODE: str = 'en-us'
TIME_ZONE: str = 'UTC'
USE_I18N: bool = True
USE_TZ: bool = True
# endregion

# Static and Media
# region
STATIC_URL: str = '/static/'
MEDIA_URL: str = '/media/'

STATICFILES_DIRS: Tuple[Path, ...] = (
    BASE_DIR / 'static',
)

STATIC_ROOT: Path = BASE_DIR / 'static_root'
MEDIA_ROOT: Path = BASE_DIR / 'media_root'
# endregion

# Payment
# region
PAYPAL_ENV: str = env.str('PAYPAL_ENV', 'live')
PAYPAL_CLIENT_ID: str = env.str('PAYPAL_CLIENT_ID', '')
PAYPAL_SECRET_KEY: str = env.str('PAYPAL_SECRET_KEY', '')

STRIPE_PUBLIC_KEY: str = env.str('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY: str = env.str('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET: str = env.str('STRIPE_WEBHOOK_SECRET', '')
# endregion

# Session
# region
SESSION_COOKIE_SECURE: bool = env.bool('SESSION_COOKIE_SECURE', True)
# endregion

# Secure
# region
SECURE_CONTENT_TYPE_NOSNIFF: bool = True
SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = env.bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', True
)
SECURE_HSTS_SECONDS: int = env.int('SECURE_HSTS_SECONDS', 31536000)
SECURE_REDIRECT_EXEMPT: List[str] = []
SECURE_SSL_REDIRECT: bool = env.bool('SECURE_SSL_REDIRECT', True)
SECURE_PROXY_SSL_HEADER: Tuple[str, str] = (
    'HTTP_X_FORWARDED_PROTO',
    'https',
)
CSRF_COOKIE_SECURE: bool = env.bool('CSRF_COOKIE_SECURE', True)
SECURE_REFERRER_POLICY: str = 'same-origin'
# endregion
