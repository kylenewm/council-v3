#!/bin/bash
# Main injection router - runs on UserPromptSubmit
# 1. Always outputs global rules (auto-inject.sh)
# 2. Checks current mode and outputs mode-specific rules

HOOKS_DIR="$HOME/.council/hooks"
GLOBAL_MODE_FILE="$HOME/.council/current_inject.txt"
LOCAL_MODE_FILE=".council/mode"

# Always output global mindset rules
"$HOOKS_DIR/auto-inject.sh"

# Check for mode: local project override > global
MODE=""
if [[ -f "$LOCAL_MODE_FILE" ]]; then
    MODE=$(cat "$LOCAL_MODE_FILE" | tr -d '[:space:]')
elif [[ -f "$GLOBAL_MODE_FILE" ]]; then
    MODE=$(cat "$GLOBAL_MODE_FILE" | tr -d '[:space:]')
fi

if [[ -n "$MODE" ]]; then

    case "$MODE" in
        strict)
            echo ""
            "$HOOKS_DIR/strict.sh"
            ;;
        poc)
            echo ""
            "$HOOKS_DIR/poc.sh"
            ;;
        scrappy)
            echo ""
            "$HOOKS_DIR/scrappy.sh"
            ;;
        plan)
            echo ""
            "$HOOKS_DIR/plan.sh"
            ;;
        review)
            echo ""
            "$HOOKS_DIR/review.sh"
            ;;
        critical)
            echo ""
            "$HOOKS_DIR/critical.sh"
            ;;
        production)
            echo ""
            "$HOOKS_DIR/production.sh"
            ;;
        off|"")
            # No additional injection
            ;;
        *)
            echo "[WARN] Unknown inject mode: $MODE"
            ;;
    esac
fi

# Check for build framework and inject if set
FRAMEWORK_FILE=".council/framework"
if [[ -f "$FRAMEWORK_FILE" ]]; then
    echo ""
    "$HOOKS_DIR/framework.sh"
fi

exit 0
