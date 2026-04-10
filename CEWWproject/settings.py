import os
import environ
from pathlib import Path

# ==========================================
# 1. PATH & ENVIRONMENT SETUP
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)

sys_env_path = os.path.join(BASE_DIR, '.internal_lib', '.sys_config')
default_env_path = os.path.join(BASE_DIR, '.env')

if os.path.exists(sys_env_path):
    environ.Env.read_env(sys_env_path)

if os.path.exists(default_env_path):
    environ.Env.read_env(default_env_path)

# ==========================================
# 2. CORE SECURITY & HOSTS
# ==========================================
SECRET_KEY = env('SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)

# SECURITY: Never use '*' in production. Define your exact Render URL in your Render environment variables.
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', 'onthego-aims.onrender.com'])

# ==========================================
# 3. PRODUCTION SSL & COOKIE SECURITY
# ==========================================
# SECURITY: These settings activate automatically when DEBUG = False (i.e., on Render)
if not DEBUG:
    # Tells Django it's secure behind Render's proxy
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Forces all HTTP traffic to redirect to HTTPS
    SECURE_SSL_REDIRECT = True
    
    # HTTP Strict Transport Security (HSTS) - Forces browsers to only use HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Ensures cookies are only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Session Configuration
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True  
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True

# ==========================================
# 4. APPLICATION & MIDDLEWARE
# ==========================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'django_extensions',
    'anymail',
    'cloudinary_storage',
    'cloudinary',
    
    # Local Apps
    'core',
    'tickets',
]

# SECURITY: Consolidated Middleware list with CSP and Whitenoise properly ordered.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware', # <-- CSP activated here
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'CEWWproject.urls'

# ==========================================
# 5. TEMPLATES & DRF CONFIGURATION
# ==========================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request', # Required for csp_nonce
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.unread_notifications_count',
            ],
        },
    },
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}

# ==========================================
# 6. DATABASE
# ==========================================
DATABASES = {
    'default': env.db(),
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# 7. COMMUNICATIONS (EMAIL & RECAPTCHA)
# ==========================================
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
ANYMAIL = {
    "BREVO_API_KEY": env('BREVO_API_KEY', default=''),
}
DEFAULT_FROM_EMAIL = '950th CEWW System <honradg71@gmail.com>'

# Resend SMTP Config
EMAIL_HOST = env('EMAIL_HOST', default='smtp.resend.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=2525) 
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='resend')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

RECAPTCHA_SITE_KEY = env('RECAPTCHA_SITE_KEY', default='')
RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY', default='')

# ==========================================
# 8. AUTHENTICATION & WEBAUTHN
# ==========================================
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'role_redirect'
LOGOUT_REDIRECT_URL = 'login'

# SECURITY: For production, these WebAuthn variables must match your live domain exactly.
WEBAUTHN_RP_ID = env('WEBAUTHN_RP_ID', default='localhost')
WEBAUTHN_RP_NAME = "950th CEWW System"
WEBAUTHN_ORIGIN = env('WEBAUTHN_ORIGIN', default='http://localhost:8000')

# ==========================================
# 9. STATIC & MEDIA FILES
# ==========================================
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
MEDIA_URL = '/media/'

# ==========================================
# 10. INTERNATIONALIZATION
# ==========================================
TIME_ZONE = 'Asia/Manila'
USE_TZ = True

# ==========================================
# 11. CONTENT SECURITY POLICY (CSP)
# ==========================================
# SECURITY: Strict resource whitelisting
CSP_DEFAULT_SRC = ("'self'",)

CSP_SCRIPT_SRC = ("'self'",)
CSP_INCLUDE_NONCE_IN = ('script-src', 'style-src')

CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")

CSP_IMG_SRC = ("'self'", "data:", "https://res.cloudinary.com")

# Explicitly defining connection sources for standard logic and APIs
CSP_CONNECT_SRC = ("'self'",)

# Prevent clickjacking / iframe embedding
CSP_FRAME_ANCESTORS = ("'none'",)

# SECURITY: I have set this to False for Maximum Security. 
# If your site suddenly looks broken upon deployment, change this back to True, 
# check your browser console for errors, whitelist the missing resources, and turn it back to False.
CSP_REPORT_ONLY = False