FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"
COPY app/ app/
COPY scripts/ scripts/
RUN useradd --create-home appuser && mkdir -p /app/cache && chown appuser /app/cache
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
