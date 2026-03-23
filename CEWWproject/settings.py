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
# ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', '192.168.0.5'])

# Christian-Branch (Preserved as comments): 
# DEBUG = env('DEBUG', default=True) # Fallback to True for local testing
# CRITICAL FIX: Hardcode the allowed hosts right here, overwriting the env file completely.
ALLOWED_HOSTS = ['*']
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
    'anymail',
    'cloudinary_storage',
    'cloudinary',
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
# 10. Email Configuration (Securely pulled from env)

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_TIMEOUT = 10

# Feed the Resend API Key directly to Anymail
ANYMAIL = {
    # FIX APPLIED HERE: Using the variable name, not the actual secret key
    "BREVO_API_KEY": env('BREVO_API_KEY', default=''),
}

# Use the verified Gmail address from your Brevo account
# DEFAULT_FROM_EMAIL = '950th CEWW System <honradg71@gmail.com>'

# OLD: Brevo SMTP setup (Preserved as comments)
# EMAIL_HOST = env('EMAIL_HOST', default='smtp-relay.brevo.com')
# EMAIL_PORT = env.int('EMAIL_PORT', default=2525)
# DEFAULT_FROM_EMAIL = '950th CEWW System <honradg71@gmail.com>'

# NEW: Resend SMTP setup
EMAIL_HOST = env('EMAIL_HOST', default='smtp.resend.com')
# Use Port 587 for TLS; Port 2525 is often blocked or throttled on cloud hosts
EMAIL_PORT = env.int('EMAIL_PORT', default=587) 
EMAIL_USE_TLS = True
# CRITICAL FIX: Sending FROM Resend's approved testing domain to bypass Google's spam block
#DEFAULT_FROM_EMAIL = '950th CEWW System <onboarding@resend.dev>'

# Active secure configuration (We will update Render to feed these into the app)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='resend')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='950th CEWW System <honradg71@gmail.com>')

# 11. ReCaptcha Security
# Original hardcoded credentials preserved as comments
# RECAPTCHA_SITE_KEY = '6LfZKoksAAAAAIQa-R-ifpRM-KAWlH6GURcjcT5D'
# RECAPTCHA_SECRET_KEY = '6LfZKoksAAAAAI2kvj1d2d-5KlL1dNDsC_YNn_Xo'

# Active secure configuration
# FIX APPLIED HERE: Using the variable names, not the actual secret keys
RECAPTCHA_SITE_KEY = env('RECAPTCHA_SITE_KEY', default='')
RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY', default='')

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

# OLD MEDIA SETTINGS (Preserved)
# MEDIA_URL = env('MEDIA_URL', default='/media/')
# MEDIA_ROOT = os.path.join(
#    BASE_DIR,
#    env('MEDIA_ROOT', default=env('MEDIA_ROOT_PATH', default='media'))
# )

# NEW CLOUDINARY STORAGE CONFIGURATION
#CLOUDINARY_STORAGE = {
#    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=''),
#    'API_KEY': env('CLOUDINARY_API_KEY', default=''),
#    'API_SECRET': env('CLOUDINARY_API_SECRET', default=''),
#    'RESOURCE_TYPE': 'auto'
#}
# Tell Django to route all uploaded files to Cloudinary automatically
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
MEDIA_URL = '/media/'

# 14. Internationalization
TIME_ZONE = 'Asia/Manila'
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'