#!/bin/bash
# Main injection router - runs on UserPromptSubmit
# 1. Always outputs minimal global rules
# 2. Routes to mode-specific script
# 3. Routes to framework script if set

HOOKS_DIR="$HOME/.council/hooks"
MODES_DIR="$HOOKS_DIR/modes"
LOCAL_MODE_FILE=".council/mode"
GLOBAL_MODE_FILE="$HOME/.council/mode"

# 1. Always output minimal global rules
"$HOOKS_DIR/global.sh"

# 2. Determine mode: local > global > default (production)
MODE="production"
if [[ -f "$LOCAL_MODE_FILE" ]]; then
    MODE=$(cat "$LOCAL_MODE_FILE" | tr -d '[:space:]')
elif [[ -f "$GLOBAL_MODE_FILE" ]]; then
    MODE=$(cat "$GLOBAL_MODE_FILE" | tr -d '[:space:]')
fi

# 3. Route to mode script
case "$MODE" in
    off)
        # No mode injection
        ;;
    *)
        MODE_SCRIPT="$MODES_DIR/${MODE}.sh"
        if [[ -f "$MODE_SCRIPT" ]]; then
            echo ""
            "$MODE_SCRIPT"
        else
            echo "[WARN] Unknown mode: $MODE (no script at $MODE_SCRIPT)"
        fi
        ;;
esac

# 4. Add framework if set (orthogonal to mode)
FRAMEWORK_FILE=".council/framework"
if [[ -f "$FRAMEWORK_FILE" ]]; then
    echo ""
    "$HOOKS_DIR/framework.sh"
fi

exit 0
