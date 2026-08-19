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

# Pre-built frontend
COPY dora-ui/dist/ dora-ui/dist/

# Workspace directory for uploads (ephemeral per container)
RUN mkdir -p /app/dora_workspace
ENV DORA_WORKSPACE=/app/dora_workspace

# Port that App Runner expects
EXPOSE 8000

# Start the server
CMD ["python", "-m", "uvicorn", "dora_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
