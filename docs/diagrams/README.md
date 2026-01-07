# Entity Resolution System Diagrams

This directory contains Mermaid diagram files that can be rendered into graphic illustrations for documentation and presentations.

## Diagram Files

### 1. **architecture.mermaid** - System Architecture
- High-level system architecture showing all components
- Data flow from sources through processing to outputs
- ArangoDB multi-model database integration
- Demo and presentation system components

### 2. **workflow.mermaid** - Entity Resolution Workflow
- Complete 5-stage entity resolution pipeline
- Decision points and validation steps
- Performance metrics and monitoring
- Data flow through each processing stage

### 3. **arango-multimodel.mermaid** - ArangoDB Multi-Model Integration
- Document, Graph, and Search engine integration
- Comparison with traditional multi-system approaches
- Native algorithm capabilities
- Performance advantages

## Generating Images

### Method 1: Online Mermaid Editor
1. Visit https://mermaid.live/
2. Copy the content from any .mermaid file
3. Paste into the editor
4. Export as PNG, SVG, or PDF

### Method 2: Mermaid CLI (Local)
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Generate PNG images
mmdc -i architecture.mermaid -o architecture.png
mmdc -i workflow.mermaid -o workflow.png
mmdc -i arango-multimodel.mermaid -o arango-multimodel.png

# Generate SVG images (scalable)
mmdc -i architecture.mermaid -o architecture.svg
mmdc -i workflow.mermaid -o workflow.svg
mmdc -i arango-multimodel.mermaid -o arango-multimodel.svg
```

### Method 3: VS Code Extension
1. Install "Mermaid Markdown Syntax Highlighting" extension
2. Open any .mermaid file
3. Use Command Palette -> "Mermaid: Preview"
4. Export from preview pane

### Method 4: GitHub/GitLab Integration
These .mermaid files can be directly embedded in Markdown:

```markdown
```mermaid
graph TB
[content from .mermaid file]
```
```

## Recommended Output Formats

### For Documentation
- **PNG**: Good for README files and web documentation
- **SVG**: Best for scalable documentation, small file sizes

### For Presentations
- **PNG**: High resolution (300 DPI) for PowerPoint/Keynote
- **PDF**: Vector format for professional presentations

### For Print
- **SVG**: Scalable vector format
- **PDF**: High-quality print output

## Image Specifications

### Recommended Resolutions
- **Web/GitHub**: 1200x800 pixels
- **Presentations**: 1920x1080 pixels
- **Print**: 300 DPI, vector format preferred

### Color Schemes
The diagrams use color coding:
- **Blue**: Data sources and entry points
- **Purple**: Database and storage components
- **Green**: Processing services and algorithms
- **Orange**: Outputs and results
- **Pink**: Demo and presentation components
- **Red**: External/comparison systems

## Usage in README

Once images are generated, update the main README.md to include them:

```markdown
## System Architecture

![System Architecture](docs/diagrams/architecture.png)

## Entity Resolution Workflow

![Entity Resolution Workflow](docs/diagrams/workflow.png)

## ArangoDB Multi-Model Integration

![ArangoDB Integration](docs/diagrams/arango-multimodel.png)
```

## Editing Diagrams

To modify the diagrams:

1. Edit the .mermaid files directly
2. Use Mermaid live editor for real-time preview
3. Test syntax with the online editor before committing
4. Regenerate images after changes
5. Update README references if needed

## Mermaid Syntax Reference

- **Graph Types**: `graph TB` (top-bottom), `graph LR` (left-right)
- **Nodes**: `NodeID[Label]`, `NodeID{Decision}`, `NodeID((Circle))`
- **Edges**: `-->` (arrow), `-.->` (dotted), `<-->` (bidirectional)
- **Subgraphs**: `subgraph "Title"` ... `end`
- **Styling**: `classDef className fill:#color`

For complete syntax reference: https://mermaid.js.org/syntax/

## File Organization

```
docs/diagrams/
README.md # This file
architecture.mermaid # System architecture diagram
workflow.mermaid # Entity resolution workflow
arango-multimodel.mermaid # ArangoDB integration details
architecture.png # Generated images (add after rendering)
workflow.png # Generated images (add after rendering)
arango-multimodel.png # Generated images (add after rendering)
```

## Integration with Main Documentation

These diagrams are designed to enhance the main README.md by providing visual representations of the concepts described in text. They should be generated and included in the repository for immediate viewing without requiring additional tools.
