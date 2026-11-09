import os
import sys
import subprocess
import uvicorn

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend directory to sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    carrier_path = os.path.join(backend_dir, "carrier_run.py")
    launch_options = {"cwd": backend_dir}
    if os.name == "nt":
        launch_options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    carrier_process = subprocess.Popen([sys.executable, carrier_path], **launch_options)
    print("=" * 60)
    print("  SOOBIN SWIMWEAR E-COMMERCE PLATFORM (MVC PYTHON)")
    print("  PostgreSQL Database: cnpm")
    print("  Server running at: http://localhost:8000")
    print("  Storefront: http://localhost:8000/")
    print("  Admin & Manager Portal: http://localhost:8000/admin")
    print("  GHTK Carrier Website: http://localhost:8001/")
    print("  VietQR Mock Payment Portal: http://localhost:8000/mock-payment")
    print("  Swagger API Docs: http://localhost:8000/docs")
    print("=" * 60)
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, app_dir=backend_dir)
    finally:
        carrier_process.terminate()
        try:
            carrier_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            carrier_process.kill()
