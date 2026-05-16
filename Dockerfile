# Stage 1: Build frontend
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Copy frontend build output into backend static directory
COPY --from=frontend-build /src/plugin_market_backend/static/ ./src/plugin_market_backend/static/

RUN uv sync --frozen --no-dev

EXPOSE 8787

CMD ["uv", "run", "uvicorn", "plugin_market_backend.app:app", "--host", "0.0.0.0", "--port", "8787"]
