# --- Stage 1: Build the React frontend ---
FROM node:20-slim AS frontend

WORKDIR /app/dora-ui
COPY dora-ui/package.json dora-ui/package-lock.json ./
RUN npm ci
COPY dora-ui/ ./
RUN npm run build

# --- Stage 2: Python backend ---
FROM python:3.12-slim

WORKDIR /app

# System dependencies for pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY contract_review/ contract_review/
COPY dora_api/ dora_api/
COPY Contract_Clause_Risk_Flagging/References/ Contract_Clause_Risk_Flagging/References/

# Copy pre-built frontend from stage 1
COPY --from=frontend /app/dora-ui/dist/ dora-ui/dist/

# Workspace directory for uploads
RUN mkdir -p /app/dora_workspace
ENV DORA_WORKSPACE=/app/dora_workspace

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "dora_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
