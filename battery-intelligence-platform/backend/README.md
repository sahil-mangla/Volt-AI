# Volt AI Backend

This is the production-ready FastAPI backend for the Volt AI platform, structured and containerized for deployment on Microsoft Azure App Service.

## Project Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI Application entrypoint
│   ├── api/                 # API Routers and endpoints
│   ├── services/            # Business logic separation 
│   ├── models/              # SQLAlchemy Domain Models
│   ├── database/            # Database engine and sessions
│   ├── ml/                  # Machine Learning Service wrappers
│   ├── schemas/             # Pydantic payloads for validation
│   ├── utils/               # Logging and helpers
│   └── config.py            # Environment configurations
├── requirements.txt         # Production dependencies
├── Dockerfile               # Container build instructions
├── startup.sh               # Gunicorn entrypoint for App Service
├── .env.example             # Template for Secrets
└── README.md                # Documentation
```

## Local Development
1. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
2. Install requirements: `pip install -r requirements.txt`
3. Copy env template: `cp .env.example .env` and fill variables.
4. Run server: `uvicorn app.main:app --reload`

## Deployment to Azure App Service (Azure Container Registry)

We recommend deploying this backend using a Docker Container via ACR (Azure Container Registry) to Azure App Service for Linux.

### Prerequisites
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) installed (`az login`)
- An active Azure Subscription

### Step 1: Build and Push Docker Image
```bash
# Set your registry name
ACR_NAME="voltairegistry"

# Create Azure Container Registry if you don't have one
az acr create --resource-group VoltAI-RG --name $ACR_NAME --sku Basic

# Log in to ACR
az acr login --name $ACR_NAME

# Build and Push the image
docker build -t $ACR_NAME.azurecr.io/voltai-backend:latest .
docker push $ACR_NAME.azurecr.io/voltai-backend:latest
```

### Step 2: Create App Service Plan & Web App
```bash
# Create a Linux App Service Plan
az appservice plan create --name VoltAI-Plan --resource-group VoltAI-RG --sku B1 --is-linux

# Create the Web App using your Docker container
az webapp create --resource-group VoltAI-RG --plan VoltAI-Plan --name voltai-api-prod --deployment-container-image-name $ACR_NAME.azurecr.io/voltai-backend:latest
```

### Step 3: Configure Environment Variables
Navigate to your App Service in the Azure Portal -> **Settings** -> **Environment variables** to map your `.env` securely:
- `DATABASE_URL` = Your Azure Postgres/SQL Connection String
- `MODEL_PATH` = Custom path if mapped via Azure Blob Storage mounts
- `PORT` = `8000` (Gunicorn binds to this as defined in `startup.sh`)

### Step 4: Configure Startup Command
In the Azure Portal -> **Settings** -> **Configuration** -> **General Settings**:
- Set the **Startup Command** exactly to: `./startup.sh`

### Step 5: Restart and Verify
Restart the App Service and verify the health check:
`curl https://voltai-api-prod.azurewebsites.net/health`
Expected output: `{"status": "ok"}`
