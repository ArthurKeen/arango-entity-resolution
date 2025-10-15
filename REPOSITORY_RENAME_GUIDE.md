# Repository Rename Guide

## Overview

This repository has been expanded in scope from a focused "record blocking" system to a comprehensive advanced entity resolution platform. To reflect this broader scope, the repository should be renamed.

## Proposed New Name

**From:** `arango-entity-resolution-record-blocking`  
**To:** `arango-entity-resolution` or `arango-advanced-entity-resolution`

## Rationale

The original name emphasized "record blocking" as the primary technique. However, the system now includes:
- Record Blocking (foundation)
- Graph Algorithms & Network Analysis
- GraphML Embeddings & Vector Search
- GraphRAG & LLM Integration
- Geospatial-Temporal Analysis
- LLM-Based Curation

The new name better reflects the comprehensive, multi-technique approach to entity resolution.

## Steps to Rename Repository

### On GitHub/GitLab

1. **Navigate to Repository Settings**
   - Go to your repository on GitHub/GitLab
   - Click "Settings"

2. **Rename Repository**
   - Find the "Repository name" field
   - Change from `arango-entity-resolution-record-blocking` to `arango-entity-resolution`
   - Click "Rename"

3. **Update Repository Description**
   - Update description to: "Advanced Entity Resolution System for ArangoDB combining traditional techniques (record blocking, similarity matching) with cutting-edge AI/ML methods (GraphML embeddings, vector search, GraphRAG, geospatial analysis, LLM curation)"

### Local Repository Update

After renaming on GitHub/GitLab, update your local repository:

```bash
# Update the remote URL
git remote set-url origin https://github.com/YOUR_USERNAME/arango-entity-resolution.git

# Or for SSH
git remote set-url origin git@github.com:YOUR_USERNAME/arango-entity-resolution.git

# Verify the change
git remote -v
```

### Update Documentation References

The following files have been updated to reflect the new scope:
- `README.md` - Title changed to "ArangoDB Advanced Entity Resolution System"
- `docs/PRD.md` - Title changed to "Advanced Entity Resolution System - Product Requirements Document"

### Update Clone Instructions

If you have documentation pointing to the old repository name, update:

```bash
# Old
git clone https://github.com/YOUR_USERNAME/arango-entity-resolution-record-blocking.git

# New
git clone https://github.com/YOUR_USERNAME/arango-entity-resolution.git
```

## Benefits of Renaming

1. **Clarity**: Name reflects comprehensive capabilities, not just one technique
2. **Professionalism**: Cleaner, more concise name
3. **Future-Proof**: Room to add more techniques without name mismatch
4. **Marketing**: Better positioning for advanced AI/ML entity resolution

## Notes

- GitHub/GitLab automatically redirects from old URL to new URL for a period of time
- Existing clones will continue to work during transition
- Update any CI/CD pipelines, documentation, or external references to use new name
- Consider adding a redirect notice to old repository location if applicable

## Completion Checklist

- [ ] Rename repository on GitHub/GitLab
- [ ] Update repository description
- [ ] Update local remote URL
- [ ] Update any external documentation
- [ ] Update CI/CD configurations
- [ ] Notify team members of change
- [ ] Update any package.json, requirements.txt, or similar files if they reference repo name
- [ ] Update Docker image names if applicable

