# Volt AI Battery Intelligence Platform

The **Volt AI Battery Intelligence Platform** is a powerful cloud AI solution designed for predictive maintenance, condition monitoring, and health analysis of battery fleets. This platform processes complex cycle data to generate predictions like Remaining Useful Life (RUL) and State of Health (SOH).

## Architecture Overview
The system relies on modern cloud technologies divided into logical tiers:
- **Frontend** → Hosted on Vercel
- **Backend** → Python FastAPI running on Azure App Service as a container
- **Container Registry** → Azure Container Registry (ACR)
- **Machine Learning Engine** → Python predictive models evaluating battery life arrays

## Project Directory Structure
```
Volt AI/
    battery-intelligence-platform/
        api/             # API routing (sometimes standalone or merged with backend core)
        backend/         # FastAPI, DB schemas, Docker configurations
        frontend/        # React/Next.js UI interfaces
        ml_engine/       # Machine learning pipelines, dataset parsing logic
        scripts/         # Auxiliary operational scripts
        data/            # Ignored via VC, local datasets
    .gitignore
    README.md
```

## How to Run Backend Locally
1. Navigate to the `backend/` directory from the root.
   ```bash
   cd battery-intelligence-platform/backend
   ```
2. Ensure you have Python 3.10+ installed and install dependencies.
   ```bash
   pip install -r requirements.txt
   ```
3. Run the backend using the local startup script.
   ```bash
   ./startup.sh
   # It is accessible across http://localhost:8000
   ```

## How to Build the Docker Image
Inside the `battery-intelligence-platform/backend/` folder, run:
```bash
docker build -t voltai-backend .
```
You can test the container instance using:
```bash
docker run -p 8000:8000 voltai-backend
```

## How to Deploy to Azure
1. Authenticate with your Azure Container Registry:
   ```bash
   az acr login --name <your-acr-name>
   ```
2. Tag and push the local Docker image to ACR:
   ```bash
   docker tag voltai-backend:latest <your-acr-name>.azurecr.io/voltai-backend:latest
   docker push <your-acr-name>.azurecr.io/voltai-backend:latest
   ```
3. Deploy onto Azure App Service linking the Web App to your Azure Container Registry repository via the Azure Portal or Azure CLI.

## API Endpoint
The production API Base URL serves from:
**https://voltai-api-prod.azurewebsites.net**
