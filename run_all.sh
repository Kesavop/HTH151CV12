#!/usr/bin/env bash
set -e

# Gladiators - macOS & Linux launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "   GLADIATORS - starting everything (macOS) "
echo "============================================"
echo

# 1. Check Python installation
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "Error: Python 3 is not installed or not in PATH."
    echo "Please install Python 3 (e.g., via brew install python or from python.org)."
    exit 1
fi

echo "Using Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

# 2. Virtual environment setup
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    $PYTHON_BIN -m venv .venv
fi

source .venv/bin/activate

# 3. Install packages
echo
echo "[1/4] Installing packages (first time may take a few minutes)..."
pip install -r requirements.txt

# 4. Run optimizer on sample data
echo
echo "[2/4] Running optimizer on sample data..."
(cd optimizer && python optimizer.py --csv ../data/sample_detections_synthetic.csv --budget 500000)

# Process cleanup handler
BACKEND_PID=""
DASHBOARD_PID=""

cleanup() {
    trap - SIGINT SIGTERM EXIT
    echo
    echo "Shutting down servers..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$DASHBOARD_PID" ]; then
        kill "$DASHBOARD_PID" 2>/dev/null || true
    fi
    echo "All stopped. Goodbye!"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 5. Start backend
echo
echo "[3/4] Starting backend (http://127.0.0.1:8000)..."
(cd backend && python -m uvicorn main:app --port 8000) &
BACKEND_PID=$!

# 6. Start dashboard
echo
echo "[4/4] Starting dashboard (http://localhost:8501)..."
(cd dashboard && python -m streamlit run app.py --server.port 8501 --server.headless true) &
DASHBOARD_PID=$!

echo
echo "Waiting for servers to initialize..."
sleep 4

# 7. Open browser on macOS
if command -v open &>/dev/null; then
    open "http://127.0.0.1:8000"
    open "http://localhost:8501"
    open "$SCRIPT_DIR/website/index.html"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://127.0.0.1:8000" 2>/dev/null || true
    xdg-open "http://localhost:8501" 2>/dev/null || true
    xdg-open "$SCRIPT_DIR/website/index.html" 2>/dev/null || true
fi

echo
echo "============================================"
echo " Services are running!"
echo "   - Backend website : http://127.0.0.1:8000"
echo "   - API test page   : http://127.0.0.1:8000/docs"
echo "   - Dashboard       : http://localhost:8501"
echo "   - Static Website  : $SCRIPT_DIR/website/index.html"
echo "   - Optimizer output: optimizer/repair_plan.csv, budget_curve.png, map.html"
echo
echo " Press Ctrl+C in this terminal window to stop all services."
echo "============================================"
echo

# Wait for background processes
wait
