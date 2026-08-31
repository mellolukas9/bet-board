#!/bin/sh
# Start de produção: migra o banco e sobe a API.
#
# As migrations rodam aqui, e não num passo separado do host, porque o mesmo
# comando precisa valer no Render, no Compose e em qualquer lugar que só saiba
# "rodar o container". `alembic upgrade head` é idempotente: subir de novo sem
# migration nova não faz nada.
#
# A porta vem de $PORT (o Render a define, e ela muda entre deploys); 8000 é o
# padrão local.
set -e

echo "migrando o banco…"
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
