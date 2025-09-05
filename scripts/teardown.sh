#!/bin/bash
# Teardown script for ArangoDB Entity Resolution Testing Environment

set -e  # Exit on any error

echo "🧹 Tearing down ArangoDB Entity Resolution Testing Environment"

# Function to prompt for confirmation
confirm() {
    read -r -p "${1:-Are you sure?} [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            true
            ;;
        *)
            false
            ;;
    esac
}

# Stop and remove containers
echo "🐳 Stopping ArangoDB containers..."
docker-compose down

# Ask about data removal
if confirm "🗑️  Do you want to remove all ArangoDB data? (This will delete all databases)"; then
    echo "🗄️  Removing ArangoDB data..."
    
    # Remove Docker volumes
    docker-compose down -v
    
    # Remove local data directory (optional)
    if confirm "   Also remove local data directory (~/data)?"; then
        if [ -d "$HOME/data" ]; then
            rm -rf "$HOME/data"
            echo "   ✅ Local data directory removed"
        else
            echo "   ⚠️  Local data directory doesn't exist"
        fi
    fi
    
    echo "✅ Data removal complete"
else
    echo "⚠️  Data preserved. You can restart with: docker-compose up -d"
fi

# Ask about Python dependencies
if confirm "🐍 Do you want to remove Python dependencies?"; then
    echo "📦 Removing Python dependencies..."
    pip3 uninstall -y -r requirements.txt
    echo "✅ Python dependencies removed"
fi

# Ask about environment file
if confirm "🔧 Do you want to remove the environment file (.env)?"; then
    if [ -f .env ]; then
        rm .env
        echo "✅ Environment file removed"
    else
        echo "⚠️  Environment file doesn't exist"
    fi
fi

echo ""
echo "🎯 Teardown Summary:"
echo "   • ArangoDB containers: Stopped"
echo "   • Docker images: Preserved (run 'docker image prune' to remove)"
echo "   • Project files: Preserved"
echo ""
echo "🔄 To restart the environment:"
echo "   ./scripts/setup.sh"
echo ""
