# Changelog

All notable changes to the ArangoDB Advanced Entity Resolution System will be documented in this file.

## [Unreleased]

### Added
- **Project Scope Expansion**: Evolved from record blocking focus to comprehensive multi-technique platform
- **Advanced Capabilities Roadmap**: Added 7 new techniques (Graph algorithms, GraphML embeddings, Vector search, GraphRAG, Geospatial-temporal, LLM curation)
- **Research Foundation**: Documented current research base and planned integration areas
- **Repository Rename Guide**: Complete guide for transitioning to new repository name
- **Scope Expansion Summary**: Master reference document for project evolution
- **Code Quality**: Comprehensive refactoring to eliminate duplicate code
- **Shared Utilities**: New `scripts/common/` module with reusable ArangoDB connection logic
- **Environment Variables**: Support for configuration via environment variables
- **Error Handling**: Improved exception handling with consistent messaging

### Changed
- **PROJECT NAME**: From "Entity Resolution with Record Blocking" to "Advanced Entity Resolution System"
- **Repository Name**: Recommend rename from `arango-entity-resolution-record-blocking` to `arango-entity-resolution`
- **README.md**: Updated to reflect multi-technique approach with 9-stage pipeline
- **PRD**: Expanded functional requirements with advanced AI/ML capabilities
- **Documentation**: Removed emojis for professional appearance and better accessibility
- **BREAKING**: Upgraded ArangoDB from 3.11 to 3.12 for testing environment
- Updated Python ArangoDB driver from 7.8.0 to 8.0.0 for compatibility with ArangoDB 3.12
- Updated Docker Compose configuration to use ArangoDB 3.12 image
- Enhanced documentation with ArangoDB 3.12 compatibility notes
- **Code Refactoring**: Eliminated duplicate code patterns between database and CRUD scripts
- **Documentation**: Updated project structure and technology stack information
- **Error Messages**: Standardized success/warning/error message formatting
- **Path References**: Updated all documentation to use new repository name

### Fixed
- **Exception Handling**: Fixed unreachable code in CRUD operations exception handling
- **Argument Parsing**: Consolidated connection argument parsing into shared utility
- **Documentation**: Removed duplicate PRD file, updated README with current project state

### Removed
- **Duplicate Files**: Removed `ER_Record_Blocking_PRD.md` (content preserved in `docs/PRD.md`)
- **Hardcoded Values**: Replaced hardcoded connection strings with environment variable support

### Notes
- **Platform Support**: ArangoDB 3.12 no longer provides native support for Windows and macOS. Docker containers are now required for these platforms.
- **API Changes**: The deprecated `api/traversal` endpoint has been removed in 3.12. Our scripts do not use this endpoint, so no changes were required.
- **Python Driver**: Updated to python-arango 8.0.0 which is compatible with ArangoDB 3.12.
- **Code Quality**: Refactored scripts follow DRY principles with shared base classes

### Migration Guide
If upgrading from a previous version:

1. **Stop existing containers**: `docker-compose down`
2. **Pull new images**: `docker-compose pull`
3. **Update Python dependencies**: `pip3 install -r requirements.txt --upgrade`
4. **Restart environment**: `./scripts/setup.sh`

## [v1.0.0] - 2024-01-XX (Initial Testing Environment)

### Added
- Initial Docker-based testing environment setup
- ArangoDB Community Edition 3.11 support
- Database management scripts for CRUD operations
- Sample customer data with entity resolution test cases
- Automated setup and teardown scripts
- Comprehensive testing documentation
- Python requirements with ArangoDB driver and utilities
- Support for mounting local ~/data directory to Docker container
- Full CRUD operations support for testing scenarios
