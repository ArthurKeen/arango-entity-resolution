# Diagram Generation Guide

This guide shows how to convert the Mermaid diagram files into graphic illustrations for the README and presentations.

## Quick Start: Online Method (Recommended)

### Step 1: Access Mermaid Live Editor
1. Go to https://mermaid.live/
2. This is the official Mermaid online editor

### Step 2: Load Diagram Content
1. Open one of the .mermaid files from `docs/diagrams/`
2. Copy all the content from the file
3. Paste it into the Mermaid Live Editor
4. The diagram will render automatically

### Step 3: Export as Image
1. Click the "Actions" menu in the editor
2. Choose "Download PNG" or "Download SVG"
3. Save the file with a descriptive name (e.g., `architecture.png`)

### Step 4: Add to Repository
1. Place the generated images in `docs/diagrams/`
2. Update the main README.md to include the images:

```markdown
## System Architecture

![System Architecture](docs/diagrams/architecture.png)

[Description of the architecture...]
```

## Example: Architecture Diagram

Here's how the architecture diagram looks when rendered:

**File**: `docs/diagrams/architecture.mermaid`

**What it shows**:
- Data sources (CRM, Marketing, Sales, Support, External)
- Entity Resolution Engine with ArangoDB Multi-Model Database
- Core services (Blocking, Similarity, Clustering, Golden Records)
- Output systems (Golden Records, Clusters, Reports, API)
- Demo & Presentation system

**Color coding**:
- Light blue: Data sources
- Purple: Database components
- Green: Processing services
- Orange: Output systems
- Pink: Demo components

## Example: Workflow Diagram

**File**: `docs/diagrams/workflow.mermaid`

**What it shows**:
- 5-stage entity resolution pipeline
- Decision points and validation steps
- Feedback loops and optimization
- Performance metrics integration

**Flow**:
1. Data Ingestion & Preprocessing
2. Record Blocking (99% pair reduction)
3. Similarity Computation & Classification
4. Graph-Based Clustering
5. Golden Record Generation

## Example: ArangoDB Multi-Model Diagram

**File**: `docs/diagrams/arango-multimodel.mermaid`

**What it shows**:
- Integration of Document, Graph, and Search capabilities
- Comparison with traditional multi-system approaches
- Native algorithm integration
- Performance advantages

## Local Installation (Optional)

If you prefer to generate diagrams locally:

```bash
# Install Mermaid CLI globally
npm install -g @mermaid-js/mermaid-cli

# Navigate to diagrams directory
cd docs/diagrams

# Generate all diagrams as PNG
mmdc -i architecture.mermaid -o architecture.png
mmdc -i workflow.mermaid -o workflow.png
mmdc -i arango-multimodel.mermaid -o arango-multimodel.png

# Generate as SVG (scalable vector graphics)
mmdc -i architecture.mermaid -o architecture.svg
mmdc -i workflow.mermaid -o workflow.svg
mmdc -i arango-multimodel.mermaid -o arango-multimodel.svg
```

## VS Code Integration

If you use VS Code:

1. Install "Mermaid Markdown Syntax Highlighting" extension
2. Open any .mermaid file
3. Use Command Palette (Cmd/Ctrl + Shift + P)
4. Type "Mermaid: Preview"
5. Export from the preview pane

## GitHub Integration

These diagrams can be embedded directly in GitHub Markdown:

```markdown
```mermaid
graph TB
    [content from .mermaid file]
```
```

However, for the main README, static images are recommended for better compatibility.

## Recommended Workflow

1. **Edit diagrams**: Modify .mermaid files as needed
2. **Preview online**: Use https://mermaid.live/ to test changes
3. **Generate images**: Export as PNG/SVG from the online editor
4. **Update README**: Add image references to documentation
5. **Commit all files**: Include both .mermaid source and generated images

## Image Specifications for Different Uses

### README Documentation
- **Format**: PNG
- **Resolution**: 1200x800 pixels
- **Compression**: Medium (web-optimized)

### Presentations
- **Format**: PNG or SVG
- **Resolution**: 1920x1080 pixels (PNG) or vector (SVG)
- **Quality**: High

### Print Documentation
- **Format**: SVG or PDF
- **Quality**: Vector (scalable)

## Troubleshooting

### Diagram Not Rendering
- Check Mermaid syntax in the online editor
- Ensure proper indentation and structure
- Verify all node IDs are unique

### Poor Image Quality
- Use SVG format for scalable graphics
- Increase resolution for PNG exports
- Check browser zoom level when exporting

### Large File Sizes
- Optimize PNG images with tools like TinyPNG
- Use SVG for complex diagrams (smaller file size)
- Consider splitting complex diagrams into multiple parts

## Next Steps

After generating the images:

1. Update the main README.md with image references
2. Consider creating a dedicated "Architecture" section in docs/
3. Use these diagrams in presentations and technical documentation
4. Keep .mermaid source files for future edits

The goal is to make the entity resolution system's architecture and workflow visually clear to both technical and business audiences.
