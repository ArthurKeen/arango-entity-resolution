# Changelog

All notable changes to the ArangoDB Entity Resolution project will be documented in this file.

## [Unreleased]

### Changed
- **BREAKING**: Upgraded ArangoDB from 3.11 to 3.12 for testing environment
- Updated Python ArangoDB driver from 7.8.0 to 8.0.0 for compatibility with ArangoDB 3.12
- Updated Docker Compose configuration to use ArangoDB 3.12 image
- Enhanced documentation with ArangoDB 3.12 compatibility notes

### Notes
- **Platform Support**: ArangoDB 3.12 no longer provides native support for Windows and macOS. Docker containers are now required for these platforms.
- **API Changes**: The deprecated `api/traversal` endpoint has been removed in 3.12. Our scripts do not use this endpoint, so no changes were required.
- **Python Driver**: Updated to python-arango 8.0.0 which is compatible with ArangoDB 3.12.

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
