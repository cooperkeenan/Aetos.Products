#!/bin/bash
# updateDatabase.sh - Sync YAML files to Neon database

set -e  # Exit on error

echo "🔄 Aetos.Products Database Sync"
echo "================================"

# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check if .env exists in project root
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ .env file not found in $PROJECT_ROOT!"
    echo "Create .env with: DATABASE_URL=\"your_neon_connection_string\""
    exit 1
fi

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated"
    echo "Run: source venv/bin/activate"
    exit 1
fi

# Change to project root directory
cd "$PROJECT_ROOT"

# Run Python sync script
echo ""
python3 scripts/sync_db.py

echo ""
echo "✅ Sync complete!"