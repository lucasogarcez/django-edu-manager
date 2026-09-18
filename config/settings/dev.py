from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

# DEVELOPMENT DEBUG
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

# DEVELOPMENT ALLOWED_HOSTS
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='').split(',') if config('DJANGO_ALLOWED_HOSTS', default='') else []

# # CHAVE GERAL DE SEGURANÇA (Feature Toggle Global)
# True = Atestado obrigatório para a escola inteira (ignora bypass da Turma)
# False = Deixa cada Turma decidir a sua obrigatoriedade
OBRIGATORIEDADE_GLOBAL_ATESTADO = False

# Redireciona os e-mails enviados para o console do terminal (Monitor Serial)
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'Sistema Acadêmico <estudosengcomputacao@gmail.com>'

EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

CORS_ALLOW_ALL_ORIGINS = True

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
    environment='homologacao',
)
    print("✓ Sensor de Telemetria Sentry Ativado")
    
INSTALLED_APPS += [
    'hijack',
    'hijack.contrib.admin',
]

# Atenção: O Hijack precisa vir DEPOIS da autenticação
MIDDLEWARE += [
    'hijack.middleware.HijackUserMiddleware',
]

HIJACK_LOGIN_REDIRECT_URL = '/'
HIJACK_LOGOUT_REDIRECT_URL = '/admin/auth/user/'