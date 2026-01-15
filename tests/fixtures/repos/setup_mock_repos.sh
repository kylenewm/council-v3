#!/bin/bash
# Setup mock git repos for testing check_invariants.py
# Run from tests/fixtures/repos/

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Clean up existing repos
rm -rf clean_diff forbidden_touched protected_touched mixed_violations

# Helper to create a repo with invariants.yaml
create_repo() {
    local name=$1
    mkdir -p "$name"
    cd "$name"
    git init -q

    # Create invariants config
    mkdir -p .council
    cat > .council/invariants.yaml << 'EOF'
forbidden_paths:
  - "*.env"
  - "credentials/*"
  - ".secrets/*"

protected_paths:
  - "api/schema.py"
  - "migrations/*"
  - "config/production.yaml"
EOF

    # Initial commit
    git add -A
    git commit -q -m "Initial commit with invariants"
    cd ..
}

# 1. clean_diff - no violations
create_repo "clean_diff"
cd clean_diff
echo "print('hello')" > main.py
echo "def helper(): pass" > utils.py
git add -A
git commit -q -m "Add safe files"
cd ..

# 2. forbidden_touched - touches credentials/*
create_repo "forbidden_touched"
cd forbidden_touched
mkdir -p credentials
echo "API_KEY=secret123" > credentials/api_key.txt
echo "print('main')" > main.py
git add -A
git commit -q -m "Add forbidden credentials file"
cd ..

# 3. protected_touched - touches api/schema.py
create_repo "protected_touched"
cd protected_touched
mkdir -p api
echo "class Schema: pass" > api/schema.py
echo "print('main')" > main.py
git add -A
git commit -q -m "Add protected schema file"
cd ..

# 4. mixed_violations - multiple issues
create_repo "mixed_violations"
cd mixed_violations
mkdir -p credentials api
echo "SECRET=xxx" > .env
echo "key: value" > credentials/config.yaml
echo "class Schema: pass" > api/schema.py
echo "print('main')" > main.py
git add -A
git commit -q -m "Add multiple violations"
cd ..

echo "Mock repos created successfully:"
ls -la
