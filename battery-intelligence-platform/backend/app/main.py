from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import Base, engine
from app.api.router import router

# Create DB Tables on startup if using strict SQLAlchemy initialization
# Note: For production Azure SQL, tools like Alembic migrations are standard,
# but for baseline Azure App Service init, we create tables if missing.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="VoltAI Battery Intelligence API",
    description="Production-ready predictive maintenance backend.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Health Check
@app.get("/health")
def health():
    return {"status": "ok"}

# Mount API 
app.include_router(router, prefix="/api", tags=["API Endpoints"])
