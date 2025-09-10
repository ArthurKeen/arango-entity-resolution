#!/bin/bash

# Manual Foxx Service Deployment Script
# Creates a ZIP file that can be uploaded via ArangoDB Web Interface

set -e

SERVICE_PATH="foxx-services/entity-resolution"
OUTPUT_DIR="build"
ZIP_NAME="entity-resolution-service.zip"

echo "🚀 Creating Foxx service deployment package..."

# Create build directory
mkdir -p $OUTPUT_DIR

# Create ZIP file
cd $SERVICE_PATH
zip -r "../../$OUTPUT_DIR/$ZIP_NAME" . -x ".*" "*/.*"
cd ../..

echo "✓ Created deployment package: $OUTPUT_DIR/$ZIP_NAME"
echo ""
echo "📋 Manual deployment instructions:"
echo "1. Open ArangoDB Web Interface: http://localhost:8529"
echo "2. Login with username: root, password: testpassword123"
echo "3. Go to SERVICES tab"
echo "4. Click 'Add Service'"
echo "5. Choose 'Upload from file'"
echo "6. Upload: $OUTPUT_DIR/$ZIP_NAME"
echo "7. Set mount point: /entity-resolution"
echo "8. Configure settings:"
echo "   - defaultSimilarityThreshold: 0.8"
echo "   - maxCandidatesPerRecord: 100"
echo "   - ngramLength: 3"
echo "   - enablePhoneticMatching: true"
echo "   - logLevel: info"
echo "9. Click 'Install'"
echo ""
echo "🧪 Test the service:"
echo "curl http://localhost:8529/_db/_system/entity-resolution/health"
echo ""
echo "📊 Service endpoints will be available at:"
echo "- http://localhost:8529/_db/_system/entity-resolution/info"
echo "- http://localhost:8529/_db/_system/entity-resolution/setup/status"
echo "- http://localhost:8529/_db/_system/entity-resolution/blocking/strategies"
echo ""
