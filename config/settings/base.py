from datetime import timedelta
from decouple import config
import dj_database_url
from pathlib import Path
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECRET_KEY
SECRET_KEY = config('DJANGO_SECRET_KEY')

# Custom user model
AUTH_USER_MODEL = 'pessoas.Usuario'

# --- CONFIGURAÇÃO DE AUTENTICAÇÃO ---

# URL para onde o Django redireciona após um LOGIN bem-sucedido.
LOGIN_REDIRECT_URL = 'home'

# URL para onde o Django redireciona após um LOGOUT.
LOGOUT_REDIRECT_URL = 'home'

# URL que o Django usa para a página de login.
LOGIN_URL = '/accounts/login/'

# Tempo de vida da sessão em segundos (login)
SESSION_COOKIE_AGE = 3600

# Atualiza a sessão a cada requisição
# True: O tempo da sessão reseta toda vez que o usuário clica em algo.
SESSION_SAVE_EVERY_REQUEST = True

# Fecha a sessão se fechar o navegador
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Aumenta o limite de dados do request (corpo do POST) para 10 MB (padrão é 2.5MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# Aumenta o limite de arquivos individuais para 10 MB (padrão é 2.5MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'django_cleanup.apps.CleanupConfig',
    'corsheaders',
    'localflavor',
    'axes',
    # Apps do sistema
    'apps.academico',
    'apps.pessoas',
    'apps.saude',
    'apps.localizacao',
    'apps.core',
    # Terceiros
    "crispy_forms",
    "crispy_bootstrap5",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middlewares.SentryUserContextMiddleware',
    'apps.core.middlewares.MaintenanceModeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'axes.middleware.AxesMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend', # <--- Sensor do Axes
    'django.contrib.auth.backends.ModelBackend', # <--- Motor original
]

# Configuração Rate Limit (Axes)
AXES_FAILURE_LIMIT = 5

# Quanto tempo (em minutos) o bloqueio vai durar? (Ex: 10 minutos)
AXES_COOLOFF_TIME = timedelta(minutes=10)

# O que bloqueia? (IP, Username, ou ambos). Por padrão, bloqueia pelo IP.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]

# (Opcional) Código HTTP que o navegador recebe ao ser bloqueado
# O padrão é mostrar uma tela branca de erro 403.
AXES_HTTP_RESPONSE_CODE = 429 # 429 = Too Many Requests

# Redirecionamento visual (IHM) para quando o disjuntor desarmar
AXES_LOCKOUT_TEMPLATE = 'core/lockout.html'

# Se tiver usando proxy/Nginx/Cloudflare, ele precisa ler o IP real do usuário, e não do Proxy:
# AXES_PROXY_COUNT = 1 

# Configuração de Storage (Django 4.2+)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Esta classe adiciona um hash único ao nome do arquivo
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Se estiver rodando testes (pytest ou manage.py test)
if 'test' in sys.argv or 'pytest' in sys.argv[0]:
    STORAGES['staticfiles'] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }

ROOT_URLCONF = 'config.urls'

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
                'apps.core.context_processors.indicador_ambiente',
            ],
        },
    },
]

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# WSGI application
WSGI_APPLICATION = 'config.wsgi.application'

# Internationalization
LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = config('STATIC_URL', default='/static/')
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logger settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} - {asctime} - {module} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'debug.log', # O arquivo será criado na raiz do projeto
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'gestoredu': { # Nome do barramento de log
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

ENVIRONMENT_NAME = config('ENVIRONMENT_NAME', 'Produção')
ENVIRONMENT_COLOR = config('ENVIRONMENT_COLOR', 'primary')