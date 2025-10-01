#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "📄 Loading environment variables from .env file..."
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
else
    echo "⚠️  No .env file found. Copy .env.example to .env and configure your settings."
    echo "   Example: cp .env.example .env"
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Add the project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Set BYPASS_TOOL_CONSENT to skip interactive prompts (essential for voice agents)
export BYPASS_TOOL_CONSENT=true

echo "🔧 BYPASS_TOOL_CONSENT is set to: $BYPASS_TOOL_CONSENT"
echo "🔧 AWS_PROFILE is set to: $AWS_PROFILE"
echo "🔧 AWS_DEFAULT_REGION is set to: $AWS_DEFAULT_REGION"
echo "🚀 Starting Voice-based AWS Agent..."

# Run the backend server
cd backend
python -m src.voice_based_aws_agent.main "$@"
