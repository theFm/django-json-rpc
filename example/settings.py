import os


_PATH = os.path.abspath(os.path.dirname(__file__))
_MODULE = os.path.basename(_PATH)


DEBUG = True
TEMPLATE_DEBUG = DEBUG

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'example.db'
    }
}

ROOT_URLCONF = _MODULE + '.urls'

MEDIA_ROOT = os.path.join(_PATH, 'media')
MEDIA_URL = '/media/'
ADMIN_MEDIA_PREFIX = '/media/admin/'

TEMPLATE_DIRS = (
    os.path.join(_PATH, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.markup',
    'jsonrpc',
)

SECRET_KEY = 'ye39vq9d@d_tm#!hn^$+%9--8k*+gg12jjqru_pl$x7=_6mq^c'
