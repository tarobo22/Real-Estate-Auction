import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("AUCTION_DEBUG") == "1"
SECRET_KEY = os.environ.get("AUCTION_SECRET_KEY", "django-insecure-local-preview") if DEBUG else os.environ["AUCTION_SECRET_KEY"]
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("AUCTION_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if host.strip()
]
HTTPS = os.environ.get("AUCTION_HTTPS") == "1"
if HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.gis",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "auctions",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "auctions.cart.cart_context",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("AUCTION_DB_NAME", "auction_lab"),
        "USER": os.environ.get("AUCTION_DB_USER", "auction"),
        "PASSWORD": os.environ.get("AUCTION_DB_PASSWORD", ""),
        "HOST": os.environ.get("AUCTION_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("AUCTION_DB_PORT", "5432"),
    }
}

LANGUAGE_CODE = "ko"
TIME_ZONE = "Asia/Seoul"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
KAKAO_MAP_JS_KEY = os.environ.get("AUCTION_KAKAO_MAP_JS_KEY", "")
