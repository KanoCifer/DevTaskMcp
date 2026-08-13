FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# PyPI mirror for faster dependency downloads. Override at build time, e.g.:
#   docker compose build --build-arg UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG UV_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
ENV UV_INDEX_URL=$UV_INDEX_URL

# Flaky mirrors stall on high download parallelism — cap it and give a
# generous per-request timeout so a slow wheel doesn't hang the build.
ENV UV_CONCURRENT_DOWNLOADS=8 \
    UV_HTTP_TIMEOUT=120

COPY pyproject.toml uv.lock run.py ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8003

CMD ["uv", "run", "python", "run.py"]
