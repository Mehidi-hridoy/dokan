from pathlib import Path
import os
from decouple import config, Csv
import dj_database_url
from datetime import timedelta

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent




DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost', cast=Csv())

# Default SQLite (for local)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# If DATABASE_URL exists (on Heroku), override with Postgres
DATABASE_URL = config('DATABASE_URL', default=None)
if DATABASE_URL:
    DATABASES['default'] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# Site & admin
SITE_ID = 1
DOKAN_VERSION = "2.01"
ADMIN_SITE_HEADER = "Dokan Administration"
ADMIN_SITE_TITLE = "Dokan Admin Portal"
ADMIN_INDEX_TITLE = "Welcome to Dokan Admin Panel"

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# SMS Settings
SMS_BACKEND = 'django.core.mail.backends.console.EmailBackend'
SMS_PROVIDER_API_KEY = config('SMS_PROVIDER_API_KEY', default='')

# POS Settings
POS_SETTINGS = {
    'DEFAULT_TAX_RATE': 0.08,
    'RECEIPT_PRINTER_ENABLED': False,
    'CASH_DRAWER_ENABLED': False,
}

# Inventory Settings
INVENTORY_SETTINGS = {
    'LOW_STOCK_ALERT': True,
    'AUTO_REORDER': False,
    'STOCK_ALERT_EMAILS': ['admin@dokan.com'],
}

# Email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@dokanecommer.com'

# Installed apps
INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'django_cleanup',

    # Local apps
    'core',
    'store',
    'users',
    'products',
    'orders',
    'inventory',
    'promotions',
    'analytics',
    # 'ckeditor',
    'django_ckeditor_5',

]
AUTH_USER_MODEL = 'users.User'

# # Add these settings
# LOGIN_REDIRECT_URL = 'products:home'  # Redirect to home after login
# LOGOUT_REDIRECT_URL = 'products:home'  # Redirect to home after logout
# LOGIN_URL = 'login'  # URL to redirect to for 

CKEDITOR_5_UPLOAD_PATH = "uploads/"

CKEDITOR_5_CONFIGS = {
    'extends': {
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3', 'blockQuote', 'codeBlock'
        ],
        'toolbar': [
            'heading', '|',
            'bold', 'italic', 'underline', 'strikethrough', '|',
            'link', 'bulletedList', 'numberedList', '|',
            'insertTable', 'blockQuote', 'code', '|',
            'undo', 'redo'
        ],
        'language': 'en',
        'image': {
            'toolbar': ['imageTextAlternative', 'imageStyle:full', 'imageStyle:side']
        },
        'table': {
            'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells']
        },
        'htmlSupport': {
            'allow': [
                {'name': '.*', 'attributes': True, 'classes': True, 'styles': True}
            ]
        },
        # 👇 link to the custom stylesheet
        'extraPlugins': [],
        'extraAllowedContent': True,
        'contentsCss': ['/static/css/ckeditor_fix.css'],  # <- important line
    }
}



# Middleware
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

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# URLs & Templates
ROOT_URLCONF = 'dokan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'orders.context_processors.cart_count_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'dokan.wsgi.application'

# Password validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True
# Optional (helps display times in your local zone)
USE_L10N = True


# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = BASE_DIR / 'staticfiles'    # for collectstatic output

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
