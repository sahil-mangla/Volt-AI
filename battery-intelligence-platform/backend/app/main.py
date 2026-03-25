from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import engine, Base
from app.api.router import router
from app.models import domain  # ensure all models are registered before create_all

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

@app.on_event("startup")
def startup_event():
    # Only initialize DB schema — no CSV processing, no ML, no background tasks
    Base.metadata.create_all(bind=engine)
    print("VoltAI API started successfully.")

# Mount API
app.include_router(router, prefix="/api", tags=["API Endpoints"])
