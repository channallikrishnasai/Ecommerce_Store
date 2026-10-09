from .main import *

SECRET_KEY: str = env.str(
    'SECRET_KEY',
    'django-insecure-local-development-key-not-for-production',
)
DEBUG: bool = True
ALLOWED_HOSTS: List[str] = env.list(
    'ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1', '[::1]'],
)
EMAIL_BACKEND: str = 'django.core.mail.backends.console.EmailBackend'
SECURE_SSL_REDIRECT: bool = False
SESSION_COOKIE_SECURE: bool = False
CSRF_COOKIE_SECURE: bool = False
SECURE_HSTS_SECONDS: int = 0

# Database
# region
DATABASES: Dict[str, Dict[str, Any]] = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
# endregion


# Payment
# region
PAYPAL_ENV: str = 'sandbox'
PAYPAL_CLIENT_ID: str = env.str('PAYPAL_SANDBOX_CLIENT_ID', '')
PAYPAL_SECRET_KEY: str = env.str('PAYPAL_SANDBOX_SECRET_KEY', '')

# endregion

# Session
# region
SESSION_COOKIE_SECURE: bool = False

# endregion
