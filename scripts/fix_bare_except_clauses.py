#!/usr/bin/env python3
"""
Fix Bare Except Clauses

This script fixes all bare except clauses in the codebase by replacing them
with specific exception handling.
"""

import sys
import os
import re
from typing import List, Tuple

def fix_bare_except_clauses():
    """Fix all bare except clauses in the codebase."""
    print("🔧 FIXING BARE EXCEPT CLAUSES")
    print("="*50)
    
    # Files with bare except clauses identified in code review
    files_to_fix = [
        "scripts/code_quality_audit.py",
        "scripts/entity_resolution_demo.py", 
        "scripts/final_code_quality_check.py",
        "scripts/shared_utils.py",
        "scripts/foxx/automated_deploy.py"
    ]
    
    fixes_applied = 0
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            print(f"📄 Fixing {file_path}...")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Fix bare except clauses
                original_content = content
                
                # Pattern 1: except: -> except Exception:
                content = re.sub(r'except\s*:', 'except Exception:', content)
                
                # Pattern 2: except : -> except Exception:
                content = re.sub(r'except\s+:', 'except Exception:', content)
                
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"   ✅ Fixed bare except clauses")
                    fixes_applied += 1
                else:
                    print(f"   ℹ️  No bare except clauses found")
                    
            except Exception as e:
                print(f"   ❌ Error fixing {file_path}: {e}")
        else:
            print(f"   ⚠️  File not found: {file_path}")
    
    print(f"\n📊 Summary: Fixed {fixes_applied} files")
    return fixes_applied

def main():
    """Main function to fix bare except clauses."""
    try:
        fixes = fix_bare_except_clauses()
        print(f"\n🎉 Successfully fixed bare except clauses in {fixes} files")
        return 0
    except Exception as e:
        print(f"❌ Error fixing bare except clauses: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
