#!/bin/bash
# Pre-commit hook - blocks commits to forbidden/protected paths
# Install: cp scripts/templates/pre-commit-invariants.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e

# Find check_invariants.py (try multiple locations)
SCRIPT=""
for path in \
    "./scripts/check_invariants.py" \
    "../council-v3/scripts/check_invariants.py" \
    "$HOME/.council/scripts/check_invariants.py"; do
    if [[ -f "$path" ]]; then
        SCRIPT="$path"
        break
    fi
done

# If no script found, check if invariants.yaml exists - if so, warn
if [[ -z "$SCRIPT" ]]; then
    if [[ -f ".council/invariants.yaml" ]]; then
        echo "⚠️  Warning: .council/invariants.yaml exists but check_invariants.py not found"
        echo "   Skipping invariant check (install script to enforce)"
    fi
    exit 0
fi

# Check if invariants.yaml exists
if [[ ! -f ".council/invariants.yaml" ]]; then
    # No invariants configured, nothing to check
    exit 0
fi

# Run check against staged changes
# Use --cached to check what's being committed, not working directory
STAGED_FILES=$(git diff --cached --name-only)

if [[ -z "$STAGED_FILES" ]]; then
    # No files staged, nothing to check
    exit 0
fi

# Create temp file with staged changes for checking
TEMP_REF=$(git write-tree)

# Check invariants against staged content
echo "Checking invariants..."
if ! python3 "$SCRIPT" --diff HEAD --invariants .council/invariants.yaml; then
    echo ""
    echo "❌ Commit blocked - fix violations or use --no-verify to bypass"
    exit 1
fi

echo "✅ Invariants check passed"
exit 0
# test
