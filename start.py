"""
start.py  —  Launch both API server + open frontend in browser.
Run:  python start.py
"""
import os, sys, time, threading, webbrowser, subprocess
from pathlib import Path

def start_api():
    os.chdir(Path(__file__).parent)
    from dotenv import load_dotenv; load_dotenv()
    from api import app
    app.run(port=5000, debug=False, use_reloader=False)

print("Starting Job Hunter …")
t = threading.Thread(target=start_api, daemon=True)
t.start()
time.sleep(1.5)

frontend = Path(__file__).parent / "frontend" / "index.html"
webbrowser.open(frontend.as_uri())
print(f"Frontend: {frontend}")
print("API:      http://localhost:5000")
print("Press Ctrl+C to stop.")
try:
    t.join()
except KeyboardInterrupt:
    print("\nStopped.")
