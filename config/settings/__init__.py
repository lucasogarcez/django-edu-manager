from decouple import config

# Lê a variável de ambiente 'DJANGO_ENV' para determinar o ambiente atual
DJANGO_ENV = config('DJANGO_ENV', default='dev')

if DJANGO_ENV == 'prod':
    from .prod import *
else:
    from .dev import *