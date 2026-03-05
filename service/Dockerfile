FROM python:3.12-alpine

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

EXPOSE 9003

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9003"]
