#!/bin/bash
# Main injection router - runs on UserPromptSubmit
# Routes to mode-specific scripts based on global or local mode setting
#
# How it works:
# 1. Always outputs global rules (auto-inject.sh)
# 2. Checks current mode (local project > global) and outputs mode-specific rules
# 3. Checks for build framework and outputs framework-specific guidance
#
# Precedence: .council/mode (local) > ~/.council/current_inject.txt (global)

set -euo pipefail

HOOKS_DIR="${HOOKS_DIR:-$HOME/.council/hooks}"
GLOBAL_MODE_FILE="$HOME/.council/current_inject.txt"
LOCAL_MODE_FILE=".council/mode"

# Always output global mindset rules
"$HOOKS_DIR/auto-inject.sh"

# Check for mode: local project override > global
MODE=""
if [[ -f "$LOCAL_MODE_FILE" ]]; then
    MODE=$(tr -d '[:space:]' < "$LOCAL_MODE_FILE")
elif [[ -f "$GLOBAL_MODE_FILE" ]]; then
    MODE=$(tr -d '[:space:]' < "$GLOBAL_MODE_FILE")
fi

if [[ -n "$MODE" ]]; then
    MODE_SCRIPT="$HOOKS_DIR/modes/${MODE}.sh"

    if [[ -f "$MODE_SCRIPT" ]]; then
        echo ""
        "$MODE_SCRIPT"
    elif [[ "$MODE" != "off" && -n "$MODE" ]]; then
        echo "[WARN] Unknown inject mode: $MODE"
    fi
fi

# Check for build framework and inject if set
FRAMEWORK_FILE=".council/framework"
if [[ -f "$FRAMEWORK_FILE" ]]; then
    FRAMEWORK=$(tr -d '[:space:]' < "$FRAMEWORK_FILE")
    FRAMEWORK_SCRIPT="$HOOKS_DIR/modes/framework-${FRAMEWORK}.sh"

    if [[ -f "$FRAMEWORK_SCRIPT" ]]; then
        echo ""
        "$FRAMEWORK_SCRIPT"
    fi
fi

exit 0
