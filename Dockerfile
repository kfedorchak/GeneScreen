# Single-deploy image: build the React app, then serve it + the API from FastAPI.

# ---- stage 1: build the frontend -> backend/app/static -------------------- #
FROM node:24-slim AS frontend
WORKDIR /app
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci
COPY frontend frontend
RUN mkdir -p backend/app && cd frontend && npm run build

# ---- stage 2: python runtime ---------------------------------------------- #
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY --from=frontend /app/backend/app/static backend/app/static

WORKDIR /app/backend
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
