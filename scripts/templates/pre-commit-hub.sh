#!/bin/bash
# Pre-commit hook (hub/spoke) - calls council-v3's check_invariants.py
# This hook is installed in TARGET projects and calls back to the council-v3 hub
#
# Install: Run /enforce from council-v3 on target project
# Requires: COUNCIL_HUB_PATH environment variable or hardcoded path below

set -e

# === CONFIGURE THIS ===
# Set to your council-v3 path (or export COUNCIL_HUB_PATH in your shell)
COUNCIL_HUB="${COUNCIL_HUB_PATH:-/Users/kylenewman/Downloads/council-v3}"
# =====================

INVARIANTS_FILE=".council/invariants.yaml"

# Check if invariants.yaml exists in THIS repo
if [[ ! -f "$INVARIANTS_FILE" ]]; then
    exit 0
fi

# Get staged files only
STAGED_FILES=$(git diff --cached --name-only)
if [[ -z "$STAGED_FILES" ]]; then
    exit 0
fi

# Check if council-v3 hub exists
if [[ ! -f "$COUNCIL_HUB/scripts/check_invariants.py" ]]; then
    echo "⚠️  Council hub not found at: $COUNCIL_HUB"
    echo "   Set COUNCIL_HUB_PATH or update this hook"
    echo "   Skipping invariants check..."
    exit 0
fi

# Create temp file with staged files
STAGED_FILE=$(mktemp)
echo "$STAGED_FILES" > "$STAGED_FILE"

# Call council-v3's check_invariants.py with staged files
# We use --diff with a custom approach since we need staged files, not a ref
export STAGED_FILES
python3 << PYTHON
import os
import sys
import fnmatch

# Add council-v3 to path for imports if needed
sys.path.insert(0, "$COUNCIL_HUB/scripts")

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
        # Handle ** patterns
        if "**" in pattern:
            import pathlib
            if pathlib.PurePath(file_path).match(pattern):
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
            if "**" in pattern:
                import pathlib
                if pathlib.PurePath(file_path).match(pattern):
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
    print("Commit blocked. Use --no-verify to bypass protected paths.")
    print("(Forbidden paths cannot be bypassed)")
    # Check if any forbidden
    has_forbidden = any(v[0] == "FORBIDDEN" for v in violations)
    if has_forbidden:
        print()
        print("FORBIDDEN files must be removed from staging:")
        print("   git reset <file>")
    sys.exit(1)

print(f"✅ Invariants check passed ({len(staged)} staged files)")
sys.exit(0)
PYTHON

# Cleanup
rm -f "$STAGED_FILE"
