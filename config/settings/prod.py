from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

# PRODUCTION DEBUG
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

# PRODUCTION ALLOWED_HOSTS
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='').split(',') if config('DJANGO_ALLOWED_HOSTS', default='') else []

# # CHAVE GERAL DE SEGURANÇA (Feature Toggle Global)
# True = Atestado obrigatório para a escola inteira (ignora bypass da Turma)
# False = Deixa cada Turma decidir a sua obrigatoriedade
OBRIGATORIEDADE_GLOBAL_ATESTADO = False

# SMTP
DEFAULT_FROM_EMAIL = 'Sistema Acadêmico <nao-responda@portfolio.com>'

if ENVIRONMENT_NAME == 'portfolio':
    # MODO EXIBIÇÃO: Desvia os e-mails com segurança para a tela de logs (terminal do Render)
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # MODO PRODUÇÃO: Acopla o motor SMTP real e carrega os encanamentos de configuração
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST')
    EMAIL_PORT = config('EMAIL_PORT', cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')

# CORS
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='').split(',') if config('CORS_ALLOWED_ORIGINS', default='') else []

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Security settings
SECURE_SSL_REDIRECT = False # Coloque "True" quando exposto a internet aberta
SESSION_COOKIE_SECURE = False # Coloque "True" quando exposto a internet aberta
CSRF_COOKIE_SECURE = False # Coloque "True" quando exposto a internet aberta
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Logger settings
LOGGING['loggers']['gestoredu']['level'] = 'INFO'

SENTRY_DSN = config('SENTRY_DSN', default=None)

if SENTRY_DSN:
    sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[DjangoIntegration()],
    send_default_pii=True,
    # Enable sending logs to Sentry
    enable_logs=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profile_session_sample_rate=1.0,
    # Set profile_lifecycle to "trace" to automatically
    # run the profiler on when there is an active transaction
    profile_lifecycle="trace",
    environment='producao',
)
    print("✓ Sensor de Telemetria Sentry Ativado")