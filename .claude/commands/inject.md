# Inject Mode Toggle

> **Source of truth:** `~/.claude/commands/inject.md`
> This file is a project-local copy with additional documentation.

Toggle context injection modes for different work types.

## Usage
- `/inject strict` - Production mode: ask first, verify after, respect invariants
- `/inject sandbox` - POC mode: quick iteration with fixtures, move fast
- `/inject scrappy` - Rapid mode: try fast, validate fast, no overhead
- `/inject plan` - Planning mode: design before building, slow and steady
- `/inject review` - Adversarial review mode: context-blind critique
- `/inject off` - Disable mode-specific injection (global rules still apply)
- `/inject status` - Show current mode
- `/inject local <mode>` - Set mode for current project only (creates .council/mode)

## What to do

When user runs this command with argument `$ARGUMENTS`:

1. If argument is `status`:
   - Read `~/.council/current_inject.txt`
   - Report current mode

2. If argument is `strict`, `sandbox`, `scrappy`, `plan`, `review`, or `off`:
   - Write the argument to `~/.council/current_inject.txt`
   - Confirm: "Injection mode set to [mode]. This will apply to all prompts until changed."

3. If argument is `local <mode>`:
   - Create `.council/` directory if needed
   - Write the mode to `.council/mode`
   - Confirm: "Local mode set to [mode]. This project will use [mode] regardless of global setting."

4. If no argument or invalid:
   - Show usage options above

## Mode Details

### strict
Production mode. Before implementing:
- Confirm task scope
- Run check_invariants.py before changes
- Verify with tests after

After completion:
- Output DONE_REPORT
- audit_done.py validates claims

### sandbox
POC/experimentation mode. Move fast:
- Skip invariants checks
- Use fixtures over real data
- Prototype first, polish later

### scrappy
Rapid integration/validation mode. For bulk operations:
- No DONE_REPORT required
- No upfront file reading
- Try → run → fix → next
- Max 3 retries per item, then move on
- Summary at end (N/M succeeded)

### plan
Design before building:
- Use code-architect subagent
- Create implementation plan
- Get approval before coding

### review
Adversarial review mode (context-blind):

**REQUIRED INPUTS:**
- git diff output
- test results (pass/fail + output)
- invariants check result (or "not configured")

**IF ANY INPUT IS MISSING:**
Respond: "REJECT: Missing evidence: [x]. Cannot review without artifacts."

**OUTPUT FORMAT:**
- BLOCKERS: [must fix before merge]
- SHOULD_FIX: [important but not blocking]
- SUGGESTIONS: [nice to have]
- VERDICT: APPROVE / REJECT / INCOMPLETE

## Notes
- Global mindset rules always apply regardless of mode
- Modes are sticky until explicitly changed
- Mode affects ALL prompts in this session via UserPromptSubmit hook
- **Precedence:** local (.council/mode) > global (~/.council/current_inject.txt)
- Use `local` to set per-project modes that don't affect other agents/projects
