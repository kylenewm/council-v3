#!/bin/bash
# PreToolUse hook - blocks writes to forbidden paths
# Debug logging
echo "[HOOK] Called at $(date)" >> /tmp/hook_debug.log

# Read hook input from stdin
INPUT=$(cat)
echo "[HOOK] Input: $INPUT" >> /tmp/hook_debug.log

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')

echo "[HOOK] Tool: $TOOL_NAME, Path: $FILE_PATH" >> /tmp/hook_debug.log

# If no file path, allow
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Get basename for pattern matching
BASENAME=$(basename "$FILE_PATH")

# Check for .env anywhere
if [[ "$BASENAME" == ".env" ]] || [[ "$BASENAME" == .env.* ]]; then
    echo "BLOCKED: Cannot $TOOL_NAME '$FILE_PATH' - .env files are forbidden" >&2
    echo "[HOOK] BLOCKED .env" >> /tmp/hook_debug.log
    exit 2
fi

# Check for credentials/secrets in filename
if [[ "$BASENAME" == *credentials* ]] || [[ "$BASENAME" == *secrets* ]] || [[ "$BASENAME" == *.secret ]]; then
    echo "BLOCKED: Cannot $TOOL_NAME '$FILE_PATH' - secrets/credentials files are forbidden" >&2
    exit 2
fi

echo "[HOOK] ALLOWED" >> /tmp/hook_debug.log
exit 0
