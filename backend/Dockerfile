FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instala as dependências antes de copiar o código, para aproveitar o cache
# de camadas quando só a aplicação muda.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY start.sh ./
RUN chmod +x start.sh

EXPOSE 8000

# start.sh migra o banco e sobe a API na $PORT (o Render define a porta; local
# cai em 8000). O docker-compose sobrescreve isto com o seu próprio `command`.
CMD ["./start.sh"]
