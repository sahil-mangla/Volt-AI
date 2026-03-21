from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import session
from app.database.session import init_db
from app.api.router import router
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
    init_db()
    if session.engine:
        session.Base.metadata.create_all(bind=session.engine)

# Mount API 
app.include_router(router, prefix="/api", tags=["API Endpoints"])
