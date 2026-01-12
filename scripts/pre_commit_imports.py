import sys
import os
import warnings

# Set default password for CI/pre-commit testing
os.environ['USE_DEFAULT_PASSWORD'] = 'true'

# Suppress warnings
warnings.filterwarnings("ignore")

print("[TEST] Importing critical modules...")
errors = []

try:
    from entity_resolution.utils.config import Config, get_config
    print("  [OK] Config module")
except Exception as e:
    errors.append(f"Config: {e}")
    print(f"  [ERROR] Config module: {e}")

try:
    from entity_resolution.utils.constants import DEFAULT_DATABASE_CONFIG
    print("  [OK] Constants module")
except Exception as e:
    errors.append(f"Constants: {e}")
    print(f"  [ERROR] Constants module: {e}")

try:
    from entity_resolution.services.blocking_service import BlockingService
    from entity_resolution.services.similarity_service import SimilarityService
    from entity_resolution.services.clustering_service import ClusteringService
    print("  [OK] Core services")
except Exception as e:
    errors.append(f"Services: {e}")
    print(f"  [ERROR] Core services: {e}")

try:
    from entity_resolution.core.entity_resolver import EntityResolver
    print("  [OK] Entity resolver")
except Exception as e:
    errors.append(f"EntityResolver: {e}")
    print(f"  [ERROR] Entity resolver: {e}")

if errors:
    print(f"\n[FAIL] {len(errors)} import errors")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
else:
    print("\n[SUCCESS] All critical imports passed")
    
print("\nSummary: All pre-commit checks passed")
