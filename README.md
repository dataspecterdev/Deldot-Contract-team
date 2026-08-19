# Case Study: DORA — DelDOT Orchestrated Review Assistant

## Overview

DORA is an AI-powered contract clause risk flagging system for Delaware DOT construction contracts. It reads contract PDFs, checks 18 critical requirements from the DelDOT Standard Specifications, and flags material deviations — telling you the exact file, page, and line number where a problem exists.

The system uses Amazon Bedrock (Claude Sonnet 4.6) for contract analysis, with the `Challenge_Reference_Rule` from the Reference Checklist as the sole scoring authority. Sources stored in a Bedrock Knowledge Base are used only for confidence scoring, not for decision-making.

**Key results:** 100% accuracy on the 108-row development label set (6 packages × 18 requirements).

## Repository Structure

- `contract_review/` – Core analysis pipeline (extraction, applicability, precedence, prompts, evidence verification, reporting)
- `dora_api/` – FastAPI backend (project management, file upload, analysis orchestration, REST API)
- `dora-ui/` – React + TypeScript frontend (workspace UI, file tree, package organizer, document viewer)
- `Contract_Clause_Risk_Flagging/` – Challenge data (References, Sources, Development packages, Validation packages)
- `docs/` – Sphinx documentation scaffold
- `output/` – Pipeline output (submission.csv, evidence_trace.csv, findings_report.json)
- `infrastructure/` – AWS deployment configuration
- `Dockerfile` – Container build for AWS App Runner deployment

## How It Works

1. **Upload** contract PDFs through the web interface (supports folders, multiple packages)
2. **Extract** text with page/line provenance using pdfplumber
3. **Decide applicability** deterministically from Project_Metadata.json
4. **Resolve precedence** — Addenda that revise a clause govern over earlier text
5. **Compare** each applicable clause against its Challenge_Reference_Rule via Bedrock Converse
6. **Verify** the model's citations against the real extracted text
7. **Report** findings with exact file/page/line references and confidence scores

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt
cd dora-ui && npm install && npm run build && cd ..

# Start the server
python -m uvicorn dora_api.main:app --host 0.0.0.0 --port 8000

# Open http://localhost:8000
```

**Environment variables required:**
- `AWS_REGION` / `AWS_DEFAULT_REGION`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
- `KB_ID` (Bedrock Knowledge Base ID, default: `QQB54AWRBZ`)

## Running the Pipeline (CLI)

```bash
# Analyze development packages and score
python -m contract_review.cli --set development --score

# Analyze a single package
python -m contract_review.cli --package Contract_Clause_Risk_Flagging/Development/Pine_Grove
```

## Documentation

This repository includes a Sphinx documentation scaffold in `docs/`. Build with:

```bash
cd docs
make html
```
```

Here's the full step-by-step to deploy DORA on AWS using App Runner:

---

# Deploying DORA to AWS — Step by Step

## What you need first

- **AWS CLI** installed and configured (you already have credentials set)
- **Docker Desktop** installed and running
- Your **AWS account ID** (the 12-digit number — this project targets `775633088292`)
- **Region**: `us-east-1` (same as your Bedrock/Knowledge Base)

---

## Step 1: Build the frontend

```powershell
cd dora-ui
npm run build
cd ..
```

This creates `dora-ui/dist/` which the container will serve.

---

## Step 2: Create an ECR repository

ECR = Elastic Container Registry. It's where AWS stores your Docker image.

```powershell
aws ecr create-repository --repository-name dora --region us-east-1
```

You'll get back a `repositoryUri` like:
```
775633088292.dkr.ecr.us-east-1.amazonaws.com/dora
```

---

## Step 3: Build and push your Docker image

```powershell
# Log Docker into ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 775633088292.dkr.ecr.us-east-1.amazonaws.com

# Build the image (from repo root where the Dockerfile is)
docker build -t dora .

# Tag it for ECR
docker tag dora:latest 775633088292.dkr.ecr.us-east-1.amazonaws.com/dora:latest

# Push to AWS
docker push 775633088292.dkr.ecr.us-east-1.amazonaws.com/dora:latest
```

This uploads your full app to AWS. Takes 2-5 min.

---

## Step 4: Create an IAM role for the app (Bedrock access)

The running container needs permission to call Bedrock (Claude + Knowledge Base).

**Create a file called `trust-policy.json`:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "tasks.apprunner.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Then run:**
```powershell
aws iam create-role --role-name dora-app-role --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy --role-name dora-app-role --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
```

---

## Step 5: Create an ECR access role (so App Runner can pull your image)

**Create `trust-policy-ecr.json`:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "build.apprunner.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Run:**
```powershell
aws iam create-role --role-name dora-ecr-access --assume-role-policy-document file://trust-policy-ecr.json

aws iam attach-role-policy --role-name dora-ecr-access --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
```

---

## Step 6: Launch App Runner

```powershell
aws apprunner create-service --service-name dora --source-configuration "{\"AuthenticationConfiguration\":{\"AccessRoleArn\":\"arn:aws:iam::775633088292:role/dora-ecr-access\"},\"ImageRepository\":{\"ImageIdentifier\":\"775633088292.dkr.ecr.us-east-1.amazonaws.com/dora:latest\",\"ImageRepositoryType\":\"ECR\",\"ImageConfiguration\":{\"Port\":\"8000\",\"RuntimeEnvironmentVariables\":{\"AWS_REGION\":\"us-east-1\",\"KB_ID\":\"QQB54AWRBZ\",\"DORA_WORKSPACE\":\"/app/dora_workspace\"}}}}" --instance-configuration "{\"InstanceRoleArn\":\"arn:aws:iam::775633088292:role/dora-app-role\",\"Cpu\":\"1024\",\"Memory\":\"2048\"}" --region us-east-1
```

Replace `775633088292` with your actual account ID if different.

---

## Step 7: Get your URL

Wait 3-5 minutes, then:

```powershell
aws apprunner list-services --region us-east-1
```

Look for `"ServiceUrl"` — it'll be something like:
```
https://abc123xyz.us-east-1.awsapprunner.com
```

**That's your live website.** HTTPS is automatic. Share that URL with anyone.

---

## What this gives you

| Feature | Status |
|---------|--------|
| Public HTTPS URL | ✅ Automatic |
| End-to-end encrypted | ✅ All within your AWS account |
| Bedrock access | ✅ Via IAM role (no keys in code) |
| Auto-scaling | ✅ App Runner handles it |
| Cost when idle | ~$0.007/hour (pauses automatically) |

---

## To tear down after hackathon

```powershell
aws apprunner delete-service --service-arn <your-service-arn> --region us-east-1
aws ecr delete-repository --repository-name dora --force --region us-east-1
```

Total cost for a one-day hackathon: probably $2-5.

---

## If something goes wrong

| Error | Fix |
|-------|-----|
| Docker build fails | Make sure you ran `npm run build` in `dora-ui/` first |
| Image push fails | Re-run the `aws ecr get-login-password` command (token expires) |
| App Runner says "access denied" | Check the IAM roles in Steps 4 and 5 |
| Analysis fails but app loads | Verify `KB_ID` matches your Knowledge Base and the region is right |

Want me to help you run through any of these steps?
