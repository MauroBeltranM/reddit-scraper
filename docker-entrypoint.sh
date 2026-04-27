#!/bin/sh
export PYTHONPATH="/app/backend:$PYTHONPATH"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
