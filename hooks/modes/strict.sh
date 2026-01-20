#!/bin/bash
# Strict mode - production code, evidence over narrative
# Activated via: /inject strict
# Reads forbidden/protected paths from .council/invariants.yaml if present

INVARIANTS_FILE=".council/invariants.yaml"

# Parse invariants.yaml with Python, fall back to defaults
get_paths() {
    if [[ -f "$INVARIANTS_FILE" ]]; then
        python3 << 'PYTHON'
import yaml
import sys
try:
    with open(".council/invariants.yaml") as f:
        data = yaml.safe_load(f)

    forbidden = data.get("forbidden_paths", [])
    protected = data.get("protected_paths", [])

    print("FORBIDDEN PATHS:")
    for p in forbidden:
        print(f"- {p} - NEVER touch")

    if protected:
        print("")
        print("PROTECTED PATHS (ask before touching):")
        for p in protected:
            print(f"- {p}")
except Exception as e:
    print(f"# Error reading invariants: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON
    else
        # Default paths when no invariants.yaml
        cat << 'DEFAULTS'
FORBIDDEN PATHS (common):
- .env, .env.* - NEVER touch
- **/credentials.json, **/secrets.* - NEVER touch
- Ask before touching config/**
DEFAULTS
    fi
}

# Build the injection
PATHS_SECTION=$(get_paths 2>/dev/null)
if [[ -z "$PATHS_SECTION" ]]; then
    # Python failed, use defaults
    PATHS_SECTION="FORBIDDEN PATHS (common):
- .env, .env.* - NEVER touch
- **/credentials.json, **/secrets.* - NEVER touch
- Ask before touching config/**"
fi

cat << EOF
[CONTEXT INJECTION - STRICT MODE]
Production software. Evidence over narrative.

BEFORE:
1. Read INVARIANTS.md (or .council/invariants.yaml) FIRST - check forbidden paths
2. Read STATE.md, CLAUDE.md if they exist
3. Read files before editing - never guess
4. Large scope? State: goal, constraints, acceptance criteria, tests

$PATHS_SECTION

DURING:
1. Test after each significant change
2. Don't add features beyond request
3. 2 failures on same error - STOP, summarize, propose alternative
4. Task > 30 min? Split into 3-7 micro-tasks, implement first only

DONE (required - auditable):
\`\`\`
DONE_REPORT:
- changed_files: [git diff --name-only]
- commands_run: [exact commands + exit codes]
- test_output: [summary or last N lines]
- invariants: [check_invariants.py result]
- next_actions: [if any]
\`\`\`

If you can't fill DONE_REPORT with real outputs, you're not done.
EOF

exit 0
