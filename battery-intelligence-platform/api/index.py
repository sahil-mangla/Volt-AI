from fastapi import FastAPI
from backend.app.main import app

# Vercel needs a variable named 'app' to be the entry point
# We import the existing FastAPI app from backend/app/main.py
