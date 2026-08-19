# Deploy DORA to AWS App Runner

## Prerequisites
- AWS CLI installed and configured
- Docker installed
- Your AWS account has Bedrock access (us-east-1 or us-west-2)

## Step 1: Build the frontend (if not already built)
```powershell
cd dora-ui
npm run build
cd ..
```

## Step 2: Build the Docker image
```powershell
docker build -t dora-app .
```

## Step 3: Create an ECR repository
```powershell
aws ecr create-repository --repository-name dora-app --region us-east-1
```

## Step 4: Login to ECR and push
```powershell
# Get your account ID
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
$REGION = "us-east-1"

# Login
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Tag and push
docker tag dora-app:latest "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/dora-app:latest"
docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/dora-app:latest"
```

## Step 5: Create App Runner service

Go to AWS Console > App Runner > Create Service:
1. Source: Container registry > Amazon ECR
2. Image URI: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/dora-app:latest`
3. Port: 8000
4. CPU: 1 vCPU, Memory: 2 GB
5. Environment variables:
   - `AWS_REGION` = `us-east-1`
   - `KB_ID` = `7BKLBOJA7F`
   - `BEDROCK_MODEL_ID` = `us.anthropic.claude-sonnet-4-6`
6. Instance role: Create/select a role with these policies:
   - `bedrock:InvokeModel`
   - `bedrock:Retrieve`
   - `bedrock-agent-runtime:Retrieve`

## Step 6: Access your app

App Runner will give you a URL like:
`https://xxxxxxxx.us-east-1.awsapprunner.com`

That's your live, HTTPS-encrypted DORA deployment. No ngrok needed.

## Cost estimate
- App Runner: ~$25/month (auto-pauses when idle)
- Bedrock: ~$1-3 per contract package analyzed
- ECR: <$1/month for storage

## Tear down when done
```powershell
# Delete the App Runner service from the console or:
aws apprunner delete-service --service-arn <arn-from-creation>

# Delete ECR repo
aws ecr delete-repository --repository-name dora-app --force --region us-east-1
```
