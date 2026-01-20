#!/bin/bash
# Type checking hook - runs after Write|Edit on code files
# Language-aware: Python (mypy), TypeScript (tsc), Go (go vet)
#
# Usage: Called by PostToolUse hook with $CLAUDE_FILE_PATH
#
# This hook reports type errors but doesn't block (uses || true)
# Errors are shown to Claude so it can fix them proactively

FILE_PATH="${CLAUDE_FILE_PATH:-$1}"

if [[ -z "$FILE_PATH" ]] || [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Get file extension
EXT="${FILE_PATH##*.}"

case "$EXT" in
    py)
        # Python: Try mypy first, fall back to pyright
        if command -v mypy &> /dev/null; then
            # Run mypy with common flags
            # --ignore-missing-imports: Don't fail on missing stubs
            # --no-error-summary: Cleaner output
            # --show-column-numbers: Precise locations
            OUTPUT=$(mypy --ignore-missing-imports --no-error-summary --show-column-numbers "$FILE_PATH" 2>&1)
            EXIT_CODE=$?
            if [[ $EXIT_CODE -ne 0 ]] && [[ -n "$OUTPUT" ]]; then
                echo "[TYPE CHECK] mypy found issues in $FILE_PATH:"
                echo "$OUTPUT"
            fi
        elif command -v pyright &> /dev/null; then
            OUTPUT=$(pyright "$FILE_PATH" 2>&1)
            EXIT_CODE=$?
            if [[ $EXIT_CODE -ne 0 ]] && [[ -n "$OUTPUT" ]]; then
                echo "[TYPE CHECK] pyright found issues in $FILE_PATH:"
                echo "$OUTPUT"
            fi
        fi
        ;;

    ts|tsx)
        # TypeScript: Use tsc if available
        if command -v tsc &> /dev/null; then
            # --noEmit: Don't generate output files
            # --skipLibCheck: Faster, skip .d.ts files
            OUTPUT=$(tsc --noEmit --skipLibCheck "$FILE_PATH" 2>&1)
            EXIT_CODE=$?
            if [[ $EXIT_CODE -ne 0 ]] && [[ -n "$OUTPUT" ]]; then
                echo "[TYPE CHECK] tsc found issues in $FILE_PATH:"
                echo "$OUTPUT"
            fi
        elif command -v npx &> /dev/null; then
            # Try npx tsc if tsc not globally installed
            OUTPUT=$(npx --yes tsc --noEmit --skipLibCheck "$FILE_PATH" 2>&1)
            EXIT_CODE=$?
            if [[ $EXIT_CODE -ne 0 ]] && [[ -n "$OUTPUT" ]]; then
                echo "[TYPE CHECK] tsc found issues in $FILE_PATH:"
                echo "$OUTPUT"
            fi
        fi
        ;;

    go)
        # Go: Use go vet
        if command -v go &> /dev/null; then
            # Get directory of the file for go vet
            DIR=$(dirname "$FILE_PATH")
            OUTPUT=$(cd "$DIR" && go vet ./... 2>&1)
            EXIT_CODE=$?
            if [[ $EXIT_CODE -ne 0 ]] && [[ -n "$OUTPUT" ]]; then
                echo "[TYPE CHECK] go vet found issues:"
                echo "$OUTPUT"
            fi
        fi
        ;;

    rs)
        # Rust: Use cargo check (if in a cargo project)
        if command -v cargo &> /dev/null; then
            # Find Cargo.toml
            DIR=$(dirname "$FILE_PATH")
            while [[ "$DIR" != "/" ]]; do
                if [[ -f "$DIR/Cargo.toml" ]]; then
                    OUTPUT=$(cd "$DIR" && cargo check --message-format=short 2>&1 | head -20)
                    EXIT_CODE=$?
                    if [[ $EXIT_CODE -ne 0 ]] && [[ -n "$OUTPUT" ]]; then
                        echo "[TYPE CHECK] cargo check found issues:"
                        echo "$OUTPUT"
                    fi
                    break
                fi
                DIR=$(dirname "$DIR")
            done
        fi
        ;;
esac

# Always exit 0 - we report errors but don't block
exit 0
