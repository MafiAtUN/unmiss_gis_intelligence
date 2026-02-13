#!/bin/bash
# Start Streamlit app using the virtual environment

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "ungis" ] || [ ! -f "ungis/bin/streamlit" ]; then
    echo "❌ Virtual environment 'ungis' not found or Streamlit not installed"
    echo "Please create venv and install dependencies:"
    echo "  python3 -m venv ungis"
    echo "  source ungis/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Stop any existing Streamlit processes
pkill -f "streamlit run app/streamlit_app.py" 2>/dev/null
sleep 1

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "📝 Loading environment variables from .env file..."
    # Use Python helper script to load env vars (handles permission issues)
    eval "$(ungis/bin/python3 load_env.py 2>/dev/null)" || {
        echo "⚠️  Could not load .env file. App will use system environment variables."
    }
    echo "✅ Environment variables loaded"
else
    echo "⚠️  No .env file found"
fi

# Start Streamlit using venv
echo "🚀 Starting Streamlit app using virtual environment 'ungis'..."
echo "📍 App will be available at http://localhost:8501"
echo ""

ungis/bin/streamlit run app/streamlit_app.py --server.headless=true


