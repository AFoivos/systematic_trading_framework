FROM node:20-alpine AS frontend-build

WORKDIR /build/frontend

COPY apps/trading_dashboard/frontend/package.json apps/trading_dashboard/frontend/package-lock.json ./
RUN npm ci

COPY apps/trading_dashboard/frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace/apps/trading_dashboard/backend:/workspace \
    TRADING_DASHBOARD_PROJECT_ROOT=/workspace \
    TRADING_DASHBOARD_FRONTEND_DIST=/opt/trading-dashboard/frontend-dist

WORKDIR /workspace/apps/trading_dashboard/backend

COPY apps/trading_dashboard/backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY apps/trading_dashboard/backend /workspace/apps/trading_dashboard/backend
COPY apps/trading_dashboard/layouts /workspace/apps/trading_dashboard/layouts
COPY src /workspace/src
COPY config /workspace/config
COPY docs /workspace/docs

RUN mkdir -p /workspace/data /workspace/logs/experiments /opt/trading-dashboard

COPY --from=frontend-build /build/frontend/dist /opt/trading-dashboard/frontend-dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
