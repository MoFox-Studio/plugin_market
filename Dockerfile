# 第一阶段：构建前端
FROM node:22-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# 第二阶段：Python 后端
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src

# 将前端构建产物复制到后端静态文件目录
COPY --from=frontend-build /src/plugin_market_backend/static/ ./src/plugin_market_backend/static/

RUN uv sync --frozen --no-dev

VOLUME ["/app/data"]
EXPOSE 8787

CMD ["sh", "-c", "uv run python -m plugin_market_backend.bootstrap && uv run uvicorn plugin_market_backend.app:app --host 0.0.0.0 --port 8787"]
