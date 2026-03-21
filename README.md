# Volt AI Battery Intelligence Platform

## Problem Statement
Battery failure prediction and predictive maintenance are highly complex operations dependent on evaluating continuous streams of voltage, current, and temperature data over cycle intervals. Identifying capacity fade and predicting Remaining Useful Life (RUL) before unexpected cascading failures occur is essential for electric scaling and grid storage safety.

## Features
- **Predictive Maintenance:** Calculates precise Remaining Useful Life (RUL).
- **Condition Monitoring:** Real-time evaluation of health scores via cycle arrays.
- **RESTful Endpoints:** Fully typed APIs for triggering AI heuristics.
- **Scalable Architecture:** Designed explicitly for cloud-native deployment.

## Tech Stack
- **FastAPI** (Python backend core)
- **Docker** (Containerization pipeline)
- **Microsoft Azure App Service** (Cloud hosting)
- **Azure Container Registry** (Image distribution)
- **Azure SQL Database** (ODBC connected data lake)
- **Vercel Frontend** (React user interfaces)
- **Machine Learning** (Scikit-learn / LSTM predictive analytics)

## System Architecture
The application is bifurcated internally where operations trigger horizontally scalable actions inside a Dockerized App Service boundary reporting centrally. (See `docs/architecture.md` for details).

## Deployment Architecture
Frontend (Vercel) → Backend Container via Azure Container Registry (ACR) deployed onto Azure App Service connecting privately to an Azure SQL Database.

## API Endpoints
The production API Base URL serves publicly from:
**https://voltai-api-prod.azurewebsites.net**

## Local Development Instructions
1. Navigate to the `backend/` directory from the root.
```bash
cd battery-intelligence-platform/backend
```
2. Create your `.env` and configure `DATABASE_URL` (SQLite will default).
3. Install project dependencies.
```bash
pip install -r requirements.txt
```
4. Run the backend correctly with the startup script explicitly supporting auto table mapping configurations.
```bash
./startup.sh
```

## Docker Build Instructions
You can rebuild the native Azure ODBC compatible Docker container locally:
```bash
docker build -t voltai-backend .
docker run -p 8000:8000 voltai-backend
```

## Azure Deployment Steps
1. Authenticate with your Azure infrastructure using the Azure CLI (`az login`).
2. Tag your local Docker image towards your specific Azure Container Registry explicitly.
3. Push via `docker push <your-acr-name>.azurecr.io/voltai-backend`.
4. Trigger a restart hook on your App Service to pull the latest changes seamlessly.

## Future Roadmap
- integration with **Azure Blob Storage**.
- Automated pipelines managed via **Azure Machine Learning**.
- Time-series metric streaming to an **Event Hub Telemetry** ecosystem.
- Dedicated unified **Fleet Monitoring Dashboard**.
- Fully automated Push/SMS **Alert System**.
- Live synchronization to a **Battery Digital Twin**.
