# ArangoDB Entity Resolution with Record Blocking

A scalable entity resolution system using ArangoDB and record blocking techniques to deduplicate and link customer records across multiple data sources.

## Project Overview

This project implements an entity resolution system that identifies and links records from one or more data sources that refer to the same real-world entity. The system uses record blocking as a crucial first step to improve efficiency by reducing the number of record pairs that need to be compared.

## Project Structure

```
arango-entity-resolution-record-blocking/
├── docs/                   # Documentation and requirements
│   ├── PRD.md             # Product Requirements Document
│   ├── TESTING_SETUP.md   # Comprehensive testing setup guide
│   └── CLAUDE.md          # Claude AI integration docs
├── research/              # Academic papers and research materials
│   ├── papers/           # Academic papers on entity resolution
│   └── notes/            # Research notes and summaries
├── scripts/               # Python scripts and utilities
│   ├── common/           # Shared utilities and base classes
│   ├── database/         # Database management tools
│   └── crud/             # CRUD operations
├── data/                  # Sample datasets and test data
│   └── sample/           # Realistic test data with duplicates
├── src/                   # Core algorithm implementation (pending)
├── config/                # Configuration files
├── tests/                 # Test framework (pending)
├── examples/             # Usage examples and demos
├── CHANGELOG.md          # Version history and changes
└── docker-compose.yml    # ArangoDB container configuration
```

## Key Features (Planned)

- **Data Ingestion**: Import customer data from various sources into ArangoDB
- **Blocking Key Generation**: Configurable blocking key creation for record grouping
- **Record Blocking**: Efficient candidate record identification
- **Similarity Matching**: Configurable similarity metrics for record comparison
- **Clustering**: Group matched records into entity clusters
- **Golden Record Creation**: Generate unified, accurate entity representations
- **REST API**: Expose entity resolution functionality via API

## Technology Stack

- **Database**: ArangoDB 3.12 (graph-based entity relationships)
- **Language**: Python 3.8+ (with modern typing and async support)
- **Driver**: python-arango 8.0.0 (full compatibility with ArangoDB 3.12)
- **Infrastructure**: Docker & Docker Compose for testing
- **API**: REST API for entity resolution operations (planned)

## Getting Started

### Quick Setup for Testing

1. **Prerequisites**: Ensure you have Docker, Docker Compose, and Python 3.8+ installed
2. **Automated Setup**: Run the setup script to get started immediately
   ```bash
   ./scripts/setup.sh
   ```
3. **Access ArangoDB**: Open http://localhost:8529 (username: `root`, password: `testpassword123`)
4. **Test the System**: 
   ```bash
   python3 scripts/crud/crud_operations.py count --collection customers
   ```

For detailed setup instructions, see [Testing Setup Guide](docs/TESTING_SETUP.md).

### Development Status

This project includes a fully functional Docker-based testing environment with:
- ✅ **ArangoDB Setup**: Docker Compose configuration with data persistence
- ✅ **Database Management**: Scripts for creating, deleting, and initializing databases
- ✅ **CRUD Operations**: Complete set of database operations for testing
- ✅ **Sample Data**: Realistic customer data with duplicates for entity resolution testing
- ✅ **Documentation**: Comprehensive setup and usage guides

**Next Phase**: Core algorithm implementation (blocking, similarity matching, clustering)

## Research Foundation

This project is built upon extensive academic research in entity resolution and record blocking. See the [research](research/) directory for relevant papers and notes.

## Contributing

Please ensure any contributions align with the project requirements outlined in the [PRD](docs/PRD.md) and follow the established coding standards:

### Code Standards
- **Python 3.8+** with type hints
- **DRY Principles**: Use shared utilities in `scripts/common/`
- **Error Handling**: Consistent messaging patterns
- **Documentation**: Comprehensive docstrings and comments
- **Environment**: Use environment variables for configuration

### Development Workflow
1. Review the [Testing Setup Guide](docs/TESTING_SETUP.md)
2. Check the [CHANGELOG](CHANGELOG.md) for recent changes
3. Follow the established patterns in existing scripts
4. Test changes with the Docker environment
5. Update documentation if needed

### Getting Help
- **Documentation**: Start with `docs/TESTING_SETUP.md`
- **Issues**: Use GitHub Issues for bugs and feature requests
- **Research**: Check `research/` directory for academic background
