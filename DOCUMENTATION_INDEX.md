# Documentation Index

Complete guide to all documentation for the ArangoDB Advanced Entity Resolution System.

## Quick Links

### Getting Started
- **[README.md](README.md)** - Project overview, features, and quick start
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and recent changes
- **[demo/README.md](demo/README.md)** - Demo package guide with presentation modes

### Essential Guides
- **[docs/TESTING.md](docs/TESTING.md)** - Complete testing guide (setup, strategies, automation)
- **[docs/GIT_HOOKS.md](docs/GIT_HOOKS.md)** - Git hooks for automated quality checks
- **[docs/FOXX_DEPLOYMENT.md](docs/FOXX_DEPLOYMENT.md)** - Foxx service deployment guide

### API Documentation
- **[docs/API_QUICKSTART.md](docs/API_QUICKSTART.md)** - Get started with APIs in 5 minutes
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete REST API reference
- **[docs/API_PYTHON.md](docs/API_PYTHON.md)** - Python SDK documentation
- **[docs/API_EXAMPLES.md](docs/API_EXAMPLES.md)** - Practical usage examples
- **[docs/openapi.yaml](docs/openapi.yaml)** - OpenAPI 3.0 specification

---

## Documentation by Category

### 1. Project Overview & Planning

#### Core Documents
- **[README.md](README.md)**
  - Project vision and business value
  - Technology stack and architecture
  - Key features (implemented and roadmap)
  - Quick start guide
  - System demonstrations

- **[docs/PRD.md](docs/PRD.md)**
  - Product Requirements Document
  - Functional requirements
  - Non-functional requirements
  - Success metrics
  - Research foundation

- **[docs/PROJECT_EVOLUTION.md](docs/PROJECT_EVOLUTION.md)**
  - Project history and evolution
  - Scope expansion timeline
  - Implementation roadmap
  - Lessons learned

#### Change Management
- **[CHANGELOG.md](CHANGELOG.md)**
  - Version history
  - Feature additions
  - Bug fixes
  - Breaking changes

### 2. Getting Started

#### Setup & Installation
- **[docs/TESTING.md](docs/TESTING.md)** - Sections: Testing Setup, Prerequisites, Configuration
  - Prerequisites and requirements
  - Automated setup instructions
  - Manual setup for troubleshooting
  - Environment configuration
  - Data directory setup

#### Quick Start Guides
- **[README.md](README.md)** - Section: Getting Started
  - 4-step quick setup
  - Docker and Python setup
  - First test run

- **[docs/API_QUICKSTART.md](docs/API_QUICKSTART.md)**
  - 5-minute API introduction
  - REST and Python examples
  - Common operations
  - Quick troubleshooting

### 3. API Documentation

#### REST API (Foxx Services)
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)**
  - Complete endpoint documentation
  - Request/response formats
  - Authentication
  - Error handling
  - Rate limiting

- **[docs/openapi.yaml](docs/openapi.yaml)**
  - OpenAPI 3.0.3 specification
  - Machine-readable API schema
  - For code generation and tooling

#### Python SDK
- **[docs/API_PYTHON.md](docs/API_PYTHON.md)**
  - Python SDK reference
  - Class documentation
  - Method signatures
  - Configuration options
  - Integration patterns

#### Usage Examples
- **[docs/API_EXAMPLES.md](docs/API_EXAMPLES.md)**
  - Complete pipeline examples
  - Service-specific examples
  - Industry use cases (healthcare, finance, retail, B2B)
  - Error handling patterns
  - Performance optimization

#### API Summary
- **[docs/API_DOCUMENTATION_SUMMARY.md](docs/API_DOCUMENTATION_SUMMARY.md)**
  - Overview of all API docs
  - Navigation guide
  - Quick reference links

### 4. Testing & Quality Assurance

#### Comprehensive Testing Guide
- **[docs/TESTING.md](docs/TESTING.md)**
  - Testing setup (prerequisites, installation)
  - Testing strategies (CURL, Python, performance)
  - Automated testing with git hooks
  - CI/CD integration
  - Troubleshooting

#### Git Hooks
- **[docs/GIT_HOOKS.md](docs/GIT_HOOKS.md)**
  - Pre-commit hook (~5 seconds)
  - Pre-push hook (~2-3 minutes)
  - Installation and usage
  - Bypass options
  - Troubleshooting

#### Test Scripts
Located in `scripts/` and `tests/` directories:
- Unit tests: `tests/test_*.py`
- Integration tests: `examples/test_*.py`
- Performance benchmarks: `scripts/benchmarks/*.py`

### 5. Deployment & Operations

#### Foxx Service Deployment
- **[docs/FOXX_DEPLOYMENT.md](docs/FOXX_DEPLOYMENT.md)**
  - Quick start (automated deployment)
  - Manual deployment via web interface
  - Alternative deployment methods
  - Testing deployment
  - Troubleshooting
  - Service configuration
  - Monitoring and maintenance

#### Foxx Architecture
- **[docs/FOXX_ARCHITECTURE.md](docs/FOXX_ARCHITECTURE.md)**
  - Service architecture
  - Module organization
  - Route structure
  - Performance benefits
  - Design decisions

#### Docker & Infrastructure
- **[docker-compose.yml](docker-compose.yml)**
  - ArangoDB container configuration
  - Port mappings
  - Volume mounts
  - Environment variables

- **[env.example](env.example)**
  - Environment variable template
  - Configuration options
  - Security settings

### 6. Demonstrations & Presentations

#### Demo Package
- **[demo/README.md](demo/README.md)**
  - Complete demo guide
  - Quick start (1 minute launch)
  - Demo modes (Interactive, Inspector, Quick, Automated)
  - Business value & ROI
  - Demo scenarios (Executive, Technical, Sales, Industry)
  - Presentation guide
  - Technical details

#### Presentation Materials
- **[demo/PRESENTATION_SCRIPT.md](demo/PRESENTATION_SCRIPT.md)**
  - 3-act demo structure
  - Talking points for each section
  - Audience interaction guidelines
  - Q&A preparation
  - Technical deep-dive options

#### Demo Scripts
Located in `demo/scripts/`:
- `interactive_presentation_demo.py` - Step-by-step presentation
- `database_inspector.py` - Real-time data inspection
- `demo_orchestrator.py` - Automated demo execution
- `data_generator.py` - Generate realistic test data
- `industry_scenarios.py` - Industry-specific demos

### 7. Architecture & Design

#### System Architecture
- **[docs/DESIGN.md](docs/DESIGN.md)**
  - Overall system design
  - Component architecture
  - Data flow
  - Design decisions
  - Scalability considerations

#### Diagrams
- **[docs/diagrams/README.md](docs/diagrams/README.md)**
  - Diagram index and descriptions

- **[docs/DIAGRAM_GENERATION_GUIDE.md](docs/DIAGRAM_GENERATION_GUIDE.md)**
  - How to create and update diagrams
  - Mermaid syntax guide
  - Diagram conventions

Available diagrams (Mermaid + SVG/PNG):
- Architecture overview
- Component architecture
- System workflow
- ArangoDB multi-model integration

#### Technical Explanations
- **[docs/GRAPH_ALGORITHMS_EXPLANATION.md](docs/GRAPH_ALGORITHMS_EXPLANATION.md)**
  - Graph algorithm details
  - Weakly Connected Components (WCC)
  - Clustering approaches
  - Performance characteristics

### 8. Research & Academic Foundation

#### Research Overview
- **[research/README.md](research/README.md)**
  - Research areas
  - Academic papers
  - Implementation notes
  - Future directions

#### Bibliography
- **[research/bibliography.md](research/bibliography.md)**
  - Complete paper references
  - Categorized by topic
  - Key findings
  - Relevance to project

#### Paper Notes
Located in `research/papers/`:
- `blocking/` - Blocking and filtering techniques
- `similarity/` - Similarity computation and probabilistic matching
- `systems/` - Complete entity resolution systems
- Each paper has detailed notes: `YYYY_Authors_Title_notes.md`

#### Implementation Notes
Located in `research/notes/`:
- ArangoSearch implementation strategies
- Algorithm optimization notes
- Performance tuning insights

### 9. Data & Examples

#### Available Datasets
- **[docs/AVAILABLE_DATASETS.md](docs/AVAILABLE_DATASETS.md)**
  - Implemented datasets
  - Test scenarios
  - Demo execution instructions
  - Data characteristics

#### Sample Data
Located in `data/sample/`:
- `customers_sample.json` - Sample customer records
- Industry-specific datasets
- Test data with known duplicates

#### Demo Data
Located in `demo/data/`:
- Demo customer datasets
- Duplicate groups
- Industry scenarios
- Generated demo reports

#### Code Examples
Located in `examples/`:
- `complete_entity_resolution_demo.py` - Full pipeline example
- `test_blocking_service.py` - Blocking service usage
- `test_similarity_service.py` - Similarity computation
- `test_clustering_service.py` - Clustering examples

### 10. Development Resources

#### Contributing & Development
- **[README.md](README.md)** - Section: Contributing
  - Development workflow
  - Git hooks setup
  - Testing requirements
  - Code quality standards

- **[docs/GIT_HOOKS.md](docs/GIT_HOOKS.md)**
  - Automated quality checks
  - Pre-commit validation
  - Pre-push testing

#### Configuration
- **[docs/CLAUDE.md](docs/CLAUDE.md)**
  - Claude AI integration guidelines
  - Project-specific instructions
  - Documentation standards
  - ASCII-only policy

- **[config.json](config.json)**
  - Application configuration
  - Service settings
  - Default parameters

#### Scripts & Utilities
Located in `scripts/`:
- `setup.sh` - Automated environment setup
- `teardown.sh` - Clean environment shutdown
- `setup-git-hooks.sh` - Git hooks installation
- `database/manage_db.py` - Database management CLI
- `crud/crud_operations.py` - CRUD operations CLI
- `foxx/automated_deploy.py` - Foxx deployment automation
- `benchmarks/` - Performance testing tools

### 11. Project Organization

#### File Structure
```
arango-entity-resolution/
├── README.md                          # Project overview
├── DOCUMENTATION_INDEX.md             # This file
├── CHANGELOG.md                       # Version history
├── docker-compose.yml                 # Docker configuration
├── requirements.txt                   # Python dependencies
├── env.example                        # Environment template
│
├── src/entity_resolution/             # Core implementation
│   ├── core/                          # Pipeline orchestration
│   ├── services/                      # ER services
│   ├── data/                          # Data management
│   └── utils/                         # Utilities
│
├── foxx-services/entity-resolution/   # Foxx microservices
│   ├── main.js                        # Service entry point
│   ├── manifest.json                  # Service manifest
│   └── routes/                        # API routes
│
├── docs/                              # Documentation
│   ├── API_*.md                       # API documentation
│   ├── TESTING.md                     # Testing guide
│   ├── FOXX_*.md                      # Foxx docs
│   ├── GIT_HOOKS.md                   # Git hooks
│   ├── DESIGN.md                      # Architecture
│   ├── PRD.md                         # Requirements
│   ├── PROJECT_EVOLUTION.md           # History
│   ├── openapi.yaml                   # OpenAPI spec
│   └── diagrams/                      # Architecture diagrams
│
├── demo/                              # Demo package
│   ├── README.md                      # Demo guide
│   ├── PRESENTATION_SCRIPT.md         # Presentation guide
│   ├── scripts/                       # Demo scripts
│   ├── data/                          # Demo data
│   └── templates/                     # Dashboards
│
├── tests/                             # Test suite
├── examples/                          # Usage examples
├── scripts/                           # Utility scripts
├── research/                          # Academic papers
├── data/                              # Data files
└── config/                            # Configuration files
```

---

## Documentation Standards

### ASCII-Only Policy
All documentation follows ASCII-only standards:
- No emojis or Unicode symbols
- Use ASCII indicators: `[OK]`, `[ERROR]`, `[WARNING]`, `[INFO]`
- Clear, professional presentation
- Accessibility compliance

### Markdown Standards
- Use clear headings and structure
- Include table of contents for long documents
- Provide code examples with syntax highlighting
- Include cross-references to related docs
- Keep information non-redundant

### Code Examples
- Include complete, runnable examples
- Show both REST API and Python SDK usage
- Provide error handling examples
- Include comments for clarity
- Demonstrate best practices

### Documentation Updates
- Update docs with code changes
- Use git hooks to enforce quality
- Cross-check for redundancy
- Validate all links
- Keep examples current

---

## Getting Help

### Documentation Issues
- **Missing information**: Check related documents using this index
- **Outdated content**: Refer to CHANGELOG.md for latest changes
- **Examples needed**: See API_EXAMPLES.md and examples/ directory

### Technical Support
- **Setup issues**: Start with docs/TESTING.md troubleshooting section
- **API questions**: Check docs/API_REFERENCE.md and docs/API_EXAMPLES.md
- **Performance**: Review docs/TESTING.md performance benchmarking
- **Deployment**: See docs/FOXX_DEPLOYMENT.md troubleshooting

### Contributing
- **Development workflow**: See README.md Contributing section
- **Code standards**: Review docs/CLAUDE.md for guidelines
- **Testing**: Follow docs/TESTING.md strategies
- **Git hooks**: Install with ./scripts/setup-git-hooks.sh

### Additional Resources
- **GitHub Issues**: Report bugs and request features
- **Research Papers**: Check research/ for academic background
- **ArangoDB Docs**: https://www.arangodb.com/docs/stable/
- **Python SDK**: https://docs.python-arango.com/

---

## Document Quick Reference

| Document | Purpose | Audience | Length |
|----------|---------|----------|--------|
| README.md | Project overview | All | Long |
| CHANGELOG.md | Version history | All | Medium |
| docs/TESTING.md | Testing guide | Developers | Long |
| docs/GIT_HOOKS.md | Git automation | Developers | Medium |
| docs/API_QUICKSTART.md | Quick start | Developers | Short |
| docs/API_REFERENCE.md | API docs | Developers | Long |
| docs/API_PYTHON.md | Python SDK | Developers | Long |
| docs/API_EXAMPLES.md | Usage examples | Developers | Long |
| docs/FOXX_DEPLOYMENT.md | Deployment | Ops/DevOps | Medium |
| docs/FOXX_ARCHITECTURE.md | Architecture | Architects | Medium |
| docs/DESIGN.md | System design | Architects | Medium |
| docs/PRD.md | Requirements | PM/Architects | Long |
| docs/PROJECT_EVOLUTION.md | History | All | Long |
| demo/README.md | Demo guide | Sales/Marketing | Long |
| demo/PRESENTATION_SCRIPT.md | Presentation | Sales | Medium |
| research/README.md | Research | Researchers | Short |

---

**Last Updated**: January 2025

**Navigation Tip**: Use your editor's search function (Ctrl+F / Cmd+F) to quickly find specific topics in this index.

**Feedback**: If you find missing documentation or have suggestions for improvement, please create an issue on GitHub.

