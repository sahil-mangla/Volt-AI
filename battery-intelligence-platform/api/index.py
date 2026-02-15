import os
import sys

# Add the current directory (api) and parent directory (project root) to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from backend.app.main import app

@app.get("/api/debug")
def debug_info():
    import os
    return {
        "cwd": os.getcwd(),
        "files_in_cwd": os.listdir('.'),
        "sys_path": sys.path,
        "env_vercel": os.environ.get('VERCEL')
    }

# Vercel needs a variable named 'app' to be the entry point
# We import the existing FastAPI app from backend/app/main.py
