import os
import environ
from pathlib import Path

# 1. Path Setup
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Initialize Environ
env = environ.Env(
    DEBUG=(bool, False)
    # Removed the incorrect ALLOWED_HOSTS definition from here
)

# 3. Read Environment Files (Priority: .sys_config then .env)
sys_env_path = os.path.join(BASE_DIR, '.internal_lib', '.sys_config')
default_env_path = os.path.join(BASE_DIR, '.env')

if os.path.exists(sys_env_path):
    environ.Env.read_env(sys_env_path)

# Always try loading .env as well
if os.path.exists(default_env_path):
    environ.Env.read_env(default_env_path)

# 4. Core Security Settings
SECRET_KEY = env('SECRET_KEY')

# --- MERGE CONFLICT RESOLVED ---
# Honrad-Branch (Active): Secure, environment-driven approach
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', '192.168.0.5'])

# Christian-Branch (Preserved as comments): 
# DEBUG = env('DEBUG', default=True) # Fallback to True for local testing
# CRITICAL FIX: Hardcode the allowed hosts right here, overwriting the env file completely.
# ALLOWED_HOSTS = ['*']
# -------------------------------

# 5. Application Definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'core',
    'tickets',
    'django_extensions',
]

# Session settings (in seconds)
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Resets the 30min timer on every click
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True

# 6. Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

# 7. Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'CEWWproject.urls'

# 8. Template Configuration
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
                'core.context_processors.unread_notifications_count',
            ],
        },
    },
]

# 9. Database Configuration (Pulled from DATABASE_URL)
DATABASES = {
    'default': env.db(),
}

# 10. Email Configuration (Securely pulled from env)

#EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = '950th CEWW System <honradg71@gmail.com>'

# Original hardcoded credentials preserved as comments
# EMAIL_HOST_USER = 'honradg71@gmail.com'
# EMAIL_HOST_PASSWORD = '[REDACTED_APP_PASSWORD]'

# Active secure configuration
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='honradg71@gmail.com')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# 11. ReCaptcha Security
# Original hardcoded credentials preserved as comments
# RECAPTCHA_SITE_KEY = '6LfZKoksAAAAAIQa-R-ifpRM-KAWlH6GURcjcT5D'
# RECAPTCHA_SECRET_KEY = '6LfZKoksAAAAAI2kvj1d2d-5KlL1dNDsC_YNn_Xo'

# Active secure configuration
RECAPTCHA_SITE_KEY = env('6LfZKoksAAAAAIQa-R-ifpRM-KAWlH6GURcjcT5D', default='6LfZKoksAAAAAIQa-R-ifpRM-KAWlH6GURcjcT5D')
RECAPTCHA_SECRET_KEY = env('6LfZKoksAAAAAI2kvj1d2d-5KlL1dNDsC_YNn_Xo', default='6LfZKoksAAAAAI2kvj1d2d-5KlL1dNDsC_YNn_Xo')

# 12. Authentication Routing
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'role_redirect'
LOGOUT_REDIRECT_URL = 'login'

WEBAUTHN_RP_ID = 'localhost'
WEBAUTHN_RP_NAME = "950th CEWW System"
WEBAUTHN_ORIGIN = 'http://localhost:8000'

# 13. Static and Media Files
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

MEDIA_URL = env('MEDIA_URL', default='/media/')

# Support both MEDIA_ROOT and MEDIA_ROOT_PATH to avoid breaking env files
MEDIA_ROOT = os.path.join(
    BASE_DIR,
    env('MEDIA_ROOT', default=env('MEDIA_ROOT_PATH', default='media'))
)

# 14. Internationalization
TIME_ZONE = 'Asia/Manila'
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'