FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock run.py ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-install-project

EXPOSE 8003

CMD ["uv", "run", "python", "run.py"]
