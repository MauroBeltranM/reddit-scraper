FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

COPY backend/ ./backend/
COPY --from=frontend /app/backend/static ./backend/static

ENV PYTHONPATH=/app/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
