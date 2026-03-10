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
env_path = os.path.join(BASE_DIR, '.internal_lib', '.sys_config')
if os.path.exists(env_path):
    environ.Env.read_env(env_path)
else:
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# 4. Core Security Settings
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG', default=True) # Fallback to True for local testing

# CRITICAL FIX: Hardcode the allowed hosts right here, overwriting the env file completely.
ALLOWED_HOSTS = ['*']

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

# 6. Django REST Framework Configuration
# 6. Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # Use ONLY your custom class for tokens
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
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'honradg71@gmail.com'
EMAIL_HOST_PASSWORD = 'nsvj nrsw zdod zurb'
DEFAULT_FROM_EMAIL = '950th CEWW System <honradg71@gmail.com>'

# 11. ReCaptcha Security
RECAPTCHA_SITE_KEY = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'
RECAPTCHA_SECRET_KEY = '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe'

# 12. Authentication Routing
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = 'role_redirect'
LOGOUT_REDIRECT_URL = 'landing'

# 13. Static and Media Files
STATIC_URL = 'static/'
MEDIA_URL = env('MEDIA_URL', default='/media/')
MEDIA_ROOT = os.path.join(BASE_DIR, env('MEDIA_ROOT_PATH', default='media'))

# 14. Internationalization
TIME_ZONE = 'Asia/Manila'
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'