#!/bin/bash
# Startup script for Augur DRHP IPO Intelligence Terminal

cd "$(dirname "$0")"

# Activate virtual environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Ensure dependencies are installed
pip install -r requirements.txt --quiet

echo "=========================================================="
echo "  🚀 Starting Augur DRHP IPO Intelligence Server"
echo "  🌐 UI & API running at: http://localhost:8000"
echo "  📄 Swagger API docs at: http://localhost:8000/docs"
echo "=========================================================="

python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
