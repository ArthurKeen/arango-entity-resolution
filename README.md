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

This project is currently in the planning phase. Please refer to the [PRD](docs/PRD.md) for detailed requirements and specifications.

## Research Foundation

This project is built upon extensive academic research in entity resolution and record blocking. See the [research](research/) directory for relevant papers and notes.

## Contributing

Please ensure any contributions align with the project requirements outlined in the PRD and follow the established coding standards (to be defined based on chosen language).
