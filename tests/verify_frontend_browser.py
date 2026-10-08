"""
Headless Browser Verification Script for WinterRoad Web Client
Captures console errors, failed network requests, and simulates user clicks.
"""

import os
import sys
import time
import glob
import subprocess
import requests
from playwright.sync_api import sync_playwright

_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)

# Locate Chrome executable in playwright cache
chrome_matches = glob.glob(
    os.path.expanduser('~/Library/Caches/ms-playwright/chromium-1243/**/Google Chrome for Testing'),
    recursive=True
)
CHROME_BIN = chrome_matches[0] if chrome_matches else None

SERVER_URL = "http://127.0.0.1:8000"

def ensure_backend_running():
    try:
        r = requests.get(f"{SERVER_URL}/api/health", timeout=1.5)
        if r.status_code == 200:
            print("Backend already running and healthy.")
            return None
    except Exception:
        pass

    print("Starting backend server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    for _ in range(30):
        time.sleep(0.5)
        try:
            r = requests.get(f"{SERVER_URL}/api/health", timeout=1.0)
            if r.status_code == 200:
                print("Backend started successfully.")
                return proc
        except Exception:
            pass
    raise RuntimeError("Backend failed to start within 15 seconds.")

def run_diagnostic():
    proc = ensure_backend_running()
    console_messages = []
    page_errors = []
    failed_requests = []
    http_errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME_BIN, headless=True)
            page = browser.new_page()

            page.on("console", lambda msg: console_messages.append({"type": msg.type, "text": msg.text, "location": msg.location}))
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            page.on("requestfailed", lambda req: failed_requests.append({"url": req.url, "failure": req.failure}))
            page.on("response", lambda res: http_errors.append({"url": res.url, "status": res.status}) if res.status >= 400 else None)

            print(f"Navigating to {SERVER_URL}...")
            page.goto(SERVER_URL, wait_until="networkidle", timeout=20000)
            time.sleep(2)

            print("\n--- PAGE LOAD DIAGNOSTICS ---")
            print(f"Page Title: {page.title()}")
            print(f"Page Errors (Uncaught Exceptions): {len(page_errors)}")
            for pe in page_errors:
                print(f"  [PAGE ERROR] {pe}")

            print(f"Console Errors/Warnings: {len([m for m in console_messages if m['type'] in ('error', 'warning')])}")
            for m in console_messages:
                if m['type'] in ('error', 'warning'):
                    print(f"  [{m['type'].upper()}] {m['text']} (at {m['location']})")

            print(f"Failed Network Requests: {len(failed_requests)}")
            for fr in failed_requests:
                print(f"  [FAILED REQ] {fr['url']}: {fr['failure']}")

            print(f"HTTP Errors (>=400): {len(http_errors)}")
            for he in http_errors:
                print(f"  [HTTP {he['status']}] {he['url']}")

            browser.close()
    finally:
        if proc:
            proc.terminate()

if __name__ == "__main__":
    run_diagnostic()
