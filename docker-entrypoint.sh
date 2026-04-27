#!/bin/sh
# Serve Vue SPA static files from FastAPI
mkdir -p /app/static
# If static files exist, mount them
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
