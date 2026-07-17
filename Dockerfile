# 可复现运行环境（M9 运维就绪）。离线优先：镜像不含任何密钥。
# 构建： docker build -t agentic-trading .
# 自检： docker run --rm agentic-trading            # 跑测试套件
# 采集： docker run --rm -p 9108:9108 agentic-trading uv run python -m atrading.monitoring.demo
FROM python:3.12-slim

# uv：快、锁定可复现（ADR-0004）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 先装依赖（利用层缓存），再拷源码
COPY pyproject.toml uv.lock* README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY . .

# 密钥仅在运行时经环境/密钥托管注入，绝不写入镜像（见 docs/runbooks/）。
EXPOSE 9108
CMD ["uv", "run", "pytest", "-q"]
