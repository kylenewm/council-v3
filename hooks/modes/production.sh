#!/bin/bash
# Production mode - combines strict rules + critical mindset
# For real builds with real users
# Activated via: /inject production

INVARIANTS_FILE=".council/invariants.yaml"

# Get forbidden/protected paths from invariants.yaml
get_paths() {
    if [[ -f "$INVARIANTS_FILE" ]]; then
        python3 << 'PYTHON'
import yaml
try:
    with open(".council/invariants.yaml") as f:
        data = yaml.safe_load(f)
    forbidden = data.get("forbidden_paths", [])
    protected = data.get("protected_paths", [])
    if forbidden:
        print("FORBIDDEN (never touch):")
        for p in forbidden:
            print(f"  - {p}")
    if protected:
        print("PROTECTED (ask first):")
        for p in protected:
            print(f"  - {p}")
except Exception:
    pass
PYTHON
    fi
}

PATHS_SECTION=$(get_paths 2>/dev/null)

cat << EOF
[MODE: PRODUCTION]

MINDSET:
- Right > Fast. Always.
- This code will be used by real people
- Bugs here = product failure
- Thoroughness is your job, speed is the system's job

RULES:
1. Read files before editing - never guess at content
2. Test after each significant change
3. 2 failures on same error - STOP, propose alternative
4. Don't add features beyond what's requested

QUALITY BAR:
- Would you trust this with your own data?
- Would you be embarrassed showing this code?
- Did you actually verify it works?

ANTI-PATTERNS (you do these):
- Rushing to "done" before verifying
- Assuming instead of checking
- "Good enough" when it's not
- Skipping edge cases

${PATHS_SECTION}
EOF

exit 0
