#!/bin/bash
echo "🚀 Starting Context Engineering Study Demos"
echo "=========================================="

# Cleanup
echo "🧹 Cleaning up ports..."
echo ""
lsof -ti:8501,8502,8503,8081 | xargs kill -9 2>/dev/null

# Function to kill background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    pkill -P $$
    exit
}

trap cleanup SIGINT SIGTERM

# 1. OPAQUE
echo "👁️  Starting Opaque Demo..."
(cd demos/opaque && uv run streamlit run main.py --server.port 8501 --server.headless=true) > /dev/null 2>&1 &
echo "   ↳ http://localhost:8501"

# 2. USER-CONTROLLED
echo "👤 Starting User-Controlled Demo..."
(cd demos/user_controlled && uv run streamlit run main.py --server.port 8502 --server.headless=true) > /dev/null 2>&1 &
echo "   ↳ http://localhost:8502"

# 3. HYBRID
echo "⚡ Starting Hybrid Demo..."
(cd demos/hybrid && uv run streamlit run main.py --server.port 8503 --server.headless=true) > /dev/null 2>&1 &
echo "   ↳ http://localhost:8503"

# 4. SERVER (Optional)
echo "🔹 Starting Backend Server..."
uv run python server.py > /dev/null 2>&1 &
echo "   ↳ http://localhost:8081"

echo ""
echo "✅ All systems running. Press Ctrl+C to stop."
wait
