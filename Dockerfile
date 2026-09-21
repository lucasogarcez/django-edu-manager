# Define o interpretador base
FROM python:3.12-slim

# Configurações de ambiente padrão para aplicações web Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cria um usuário não-root chamado "appuser" para rodar a aplicação com segurança
RUN adduser --disabled-password --no-create-home appuser

# Define a pasta de trabalho
WORKDIR /app

# Instala dependências de sistema essenciais (caso precise compilar pacotes do requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências
ARG REQUIREMENT_FILE=requirements.txt
COPY ./requirements.txt ./requirements-dev.txt* /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r $REQUIREMENT_FILE

# Copia todo o resto do projeto (o .dockerignore filtrará os dados sensíveis)
COPY . /app/

# Torna o script de inicialização executável
RUN chmod +x /app/entrypoint.sh

# Altera o dono dos arquivos da pasta /app para o usuário seguro criado
RUN chown -R appuser:appuser /app

# Troca do usuário "root" para o usuário "appuser" daqui em diante
USER appuser

# Expõe a porta que o Gunicorn vai rodar
EXPOSE 8000

# Executa o script de inicialização
CMD ["/app/entrypoint.sh"]