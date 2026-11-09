import os
import sys
import uvicorn

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

if __name__ == "__main__":
    uvicorn.run("app.carrier_portal:app", host="127.0.0.1", port=8001, reload=False)
