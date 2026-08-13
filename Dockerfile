FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# PyPI mirror for faster dependency downloads. Override at build time, e.g.:
#   docker compose build --build-arg UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_INDEX_URL=$UV_INDEX_URL

COPY pyproject.toml uv.lock run.py ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8003

CMD ["uv", "run", "python", "run.py"]
