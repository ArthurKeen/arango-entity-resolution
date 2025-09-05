# ArangoDB Entity Resolution with Record Blocking

A scalable entity resolution system using ArangoDB and record blocking techniques to deduplicate and link customer records across multiple data sources.

## Project Overview

This project implements an entity resolution system that identifies and links records from one or more data sources that refer to the same real-world entity. The system uses record blocking as a crucial first step to improve efficiency by reducing the number of record pairs that need to be compared.

## Project Structure

```
arango-entity-resolution-record-blocking/
├── docs/                   # Documentation and requirements
│   ├── PRD.md             # Product Requirements Document
│   └── CLAUDE.md          # Claude AI integration docs
├── research/              # Academic papers and research materials
│   ├── papers/           # Academic papers on entity resolution
│   └── notes/            # Research notes and summaries
├── src/                   # Source code (language TBD)
├── data/                  # Sample datasets and test data
├── config/                # Configuration files
├── tests/                 # Test files
├── scripts/              # Utility scripts
└── examples/             # Usage examples and demos
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

- **Database**: ArangoDB (for graph-based entity relationships)
- **Language**: TBD (considering Python, Java, or Go)
- **API**: REST API for entity resolution operations

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

Please ensure any contributions align with the project requirements outlined in the PRD and follow the established coding standards (to be defined based on chosen language).
