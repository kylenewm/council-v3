#!/bin/bash
# Pre-commit hook - blocks commits to forbidden/protected paths
# Install: cp scripts/templates/pre-commit-invariants.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e

INVARIANTS_FILE=".council/invariants.yaml"

# Check if invariants.yaml exists
if [[ ! -f "$INVARIANTS_FILE" ]]; then
    exit 0
fi

# Get staged files only
STAGED_FILES=$(git diff --cached --name-only)
if [[ -z "$STAGED_FILES" ]]; then
    exit 0
fi

# Parse patterns from yaml and check staged files
export STAGED_FILES
python3 << 'PYTHON'
import os
import sys
import fnmatch

try:
    import yaml
    with open(".council/invariants.yaml") as f:
        data = yaml.safe_load(f)
except ImportError:
    # Simple fallback parser
    data = {"forbidden_paths": [], "protected_paths": []}
    with open(".council/invariants.yaml") as f:
        current_key = None
        for line in f:
            line = line.strip()
            if line.startswith("forbidden_paths"):
                current_key = "forbidden_paths"
            elif line.startswith("protected_paths"):
                current_key = "protected_paths"
            elif line.startswith("- ") and current_key:
                pattern = line[2:].strip().strip('"').strip("'")
                data[current_key].append(pattern)

forbidden = data.get("forbidden_paths", []) or []
protected = data.get("protected_paths", []) or []

# Get staged files from environment variable
staged_str = os.environ.get("STAGED_FILES", "")
staged = [f for f in staged_str.strip().split('\n') if f]

violations = []

for file_path in staged:
    for pattern in forbidden:
        if fnmatch.fnmatch(file_path, pattern):
            violations.append(("FORBIDDEN", file_path, pattern))
            break
        if pattern.endswith("/*") and file_path.startswith(pattern[:-1]):
            violations.append(("FORBIDDEN", file_path, pattern))
            break
    else:
        for pattern in protected:
            if fnmatch.fnmatch(file_path, pattern):
                violations.append(("PROTECTED", file_path, pattern))
                break
            if pattern.endswith("/*") and file_path.startswith(pattern[:-1]):
                violations.append(("PROTECTED", file_path, pattern))
                break

if violations:
    print("❌ Invariant violations in staged files:")
    for vtype, path, pattern in violations:
        if vtype == "FORBIDDEN":
            print(f"   ❌ FORBIDDEN: {path} (matched {pattern})")
        else:
            print(f"   ⚠️  PROTECTED: {path} (matched {pattern})")
    print()
    print("Commit blocked. Use --no-verify to bypass.")
    sys.exit(1)

print(f"✅ Invariants check passed ({len(staged)} staged files)")
sys.exit(0)
PYTHON
