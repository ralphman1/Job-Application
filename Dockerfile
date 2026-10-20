FROM ghcr.io/astral-sh/uv:0.12.10 AS uv
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev \
    && groupadd --gid 10001 tracker \
    && useradd --uid 10001 --gid tracker --no-create-home tracker \
    && mkdir -p /app/data \
    && chown tracker:tracker /app/data

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY --chmod=755 scripts/entrypoint.sh /usr/local/bin/start-tracker

USER tracker
EXPOSE 8000
ENTRYPOINT ["start-tracker"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
