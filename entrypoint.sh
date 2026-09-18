#!/bin/bash

# Interrompe o script imediatamente se qualquer comando falhar
set -e

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "Aplicando migrações do banco de dados..."
python manage.py migrate

echo "Iniciando o servidor Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 4 --worker-class gthread --timeout 120 --keep-alive 5