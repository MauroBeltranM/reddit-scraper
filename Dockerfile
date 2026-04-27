FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/ .
RUN npm install && npm run build

FROM python:3.12-slim AS backend-build
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

FROM python:3.12-slim
WORKDIR /app

# Backend
COPY --from=backend-build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-build /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY backend/ ./backend/

# Frontend static files
COPY --from=frontend-build /app/frontend/dist ./static/

ENV PYTHONPATH=/app/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
