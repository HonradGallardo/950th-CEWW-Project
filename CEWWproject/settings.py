import os
import environ
from pathlib import Path

# 1. Path Setup
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Initialize Environ
env = environ.Env(
    DEBUG=(bool, False)
)

# 3. Read Environment Files (Priority: .sys_config then .env)
sys_env_path = os.path.join(BASE_DIR, '.internal_lib', '.sys_config')
default_env_path = os.path.join(BASE_DIR, '.env')

if os.path.exists(sys_env_path):
    environ.Env.read_env(sys_env_path)

if os.path.exists(default_env_path):
    environ.Env.read_env(default_env_path)

# 4. Core Security Settings
SECRET_KEY = env('SECRET_KEY')

# Honrad-Branch (Active): Secure, environment-driven approach
DEBUG = env.bool('DEBUG', default=False)

# SECURITY FIX: Wildcard '*' removed to prevent Host Header attacks.
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', 'onthego-aims.onrender.com'])

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
    'axes', # SECURITY: Added for brute-force protection
]

# Session settings (in seconds)
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Resets the 30min timer on every click
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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

# SECURITY: Authentication Backends for Axes integration
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# 7. Middleware (Consolidated & Secured)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware', # SECURITY: Injected CSP Middleware
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware', # SECURITY: Injected Axes Middleware
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

# 9. Database Configuration
DATABASES = {
    'default': env.db(),
}

# 10. Email Configuration
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
ANYMAIL = {
    "BREVO_API_KEY": env('BREVO_API_KEY', default=''),
}
DEFAULT_FROM_EMAIL = '950th CEWW System <honradg71@gmail.com>'

EMAIL_HOST = env('EMAIL_HOST', default='smtp.resend.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=2525) 
EMAIL_USE_TLS = True

EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='resend')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# 11. ReCaptcha Security
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

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
MEDIA_URL = '/media/'

# 14. Internationalization
TIME_ZONE = 'Asia/Manila'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==========================================
# 15. SECURITY HARDENING 
# ==========================================

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY' 

# --- NEW: Password Validation ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- NEW: Brute-Force Protection (Axes) ---
AXES_FAILURE_LIMIT = 5            # Lock out after 5 failed attempts
AXES_COOLOFF_TIME = 1             # Lock out duration in hours
AXES_RESET_ON_SUCCESS = True      # Reset failed attempts on successful login
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"] # Block specific user from specific IP

# --- NEW: Content Security Policy (CSP) ---
# Enforces strict loading of resources to prevent XSS execution
CSP_INCLUDE_NONCE_IN = ['script-src'] # style-src removed to allow Tailwind inline rendering
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'", 
    "https://code.jquery.com", 
    "https://cdn.tailwindcss.com", # Allows Tailwind CDN execution
    "'nonce'"
)
CSP_STYLE_SRC = (
    "'self'", 
    "https://fonts.googleapis.com", 
    "https://cdnjs.cloudflare.com",
    "'unsafe-inline'" # CRITICAL FIX: Allows Tailwind and inline HTML styles to render
)
CSP_FONT_SRC = (
    "'self'", 
    "https://fonts.gstatic.com", 
    "https://cdnjs.cloudflare.com"
)
# Allows Cloudinary images and base64 previews
CSP_IMG_SRC = ("'self'", "https://res.cloudinary.com", "data:", "blob:") 
# Allows API calls to your own backend
CSP_CONNECT_SRC = ("'self'",) 

# HTTPS/SSL Settings applied ONLY in production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True