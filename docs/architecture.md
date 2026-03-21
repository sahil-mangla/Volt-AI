# System Architecture

## Data Flow
The architecture follows a strict decoupled multi-tier stream where telemetry payload arrays are generated, passed into the network RESTfully, analyzed by a dedicated python machine-learning context module, recorded, and sent safely back down.

## Backend Architecture
Developed modularly using Python and FastAPI. Operations are decoupled into granular interfaces (`routers/`, `schemas/`, `ml/`, `services/`, `database/`) permitting hyper-scaler deployment mapping gracefully through WSGI/ASGI configurations like Gunicorn and Uvicorn. The engine isolates database bindings dynamically based on internal context.

## ML Pipeline
A python-managed matrix leveraging robust algorithms including localized LSTM models mapped securely natively directly within isolated memory-spaces to ensure ultra-low latency risk predictions. 

## Database Architecture
Built extensively on SQLAlchemy ORM abstractions utilizing dynamic relational modeling capable of interfacing directly against raw `sqlite` structures recursively for sandbox operations while natively executing Microsoft ODBC queries directly targeting an optimized **Azure SQL Database**.

## Deployment Pipeline and Azure Dependencies
Constructed specifically as a cloud-native architecture. Commits are bundled via Azure Container Registries seamlessly transferring images autonomously downstream unto the scalable App Services array.

```
Frontend (Vercel)
        ↓
Azure App Service (FastAPI Docker Container)
        ↓
Azure SQL Database
        ↓
Azure Blob Storage (future)
        ↓
Azure Machine Learning (future)
        ↓
Event Hub (future telemetry)
```
