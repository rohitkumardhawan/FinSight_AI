import sys
import os
import uvicorn

if __name__ == "__main__":
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)
    print("Starting FastAPI backend on http://127.0.0.1:8000 ...", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
