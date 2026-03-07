FROM python:3.12-alpine

RUN apk upgrade --no-cache

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project --frozen

COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

RUN adduser -D -u 1000 sentinel
USER sentinel

EXPOSE 9003

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9003"]
