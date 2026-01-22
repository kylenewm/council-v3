# Inject Mode Toggle

> **Source of truth:** `~/.claude/commands/inject.md`
> This file is a project-local copy with additional documentation.

Toggle context injection modes for different work types.

## Usage
- `/inject research` - Research mode: collaborative brainstorming, preserve content
- `/inject plan` - Planning mode: design before building, wait for approval
- `/inject sandbox` - Sandbox mode: quick POC iteration, experimentation allowed
- `/inject scrappy` - Scrappy mode: rapid validation, brute force OK
- `/inject strict` - Strict mode: procedures + paths + DONE_REPORT
- `/inject production` - Production mode: full rigor (mindset + procedures + paths)
- `/inject review` - Review mode: adversarial context-blind critique
- `/inject off` - Disable mode-specific injection (global rules still apply)
- `/inject status` - Show current mode
- `/inject local <mode>` - Set mode for current project only (creates .council/mode)

## What to do

When user runs this command with argument `$ARGUMENTS`:

1. If argument is `status`:
   - Check `.council/mode` first (local), then `~/.council/mode` (global)
   - Report current mode and source

2. If argument is a valid mode (`research`, `plan`, `sandbox`, `scrappy`, `strict`, `production`, `review`, `off`):
   - Write the argument to `~/.council/mode`
   - Confirm: "Global mode set to [mode]. This will apply to all projects unless overridden locally."

3. If argument is `local <mode>`:
   - Create `.council/` directory if needed
   - Write the mode to `.council/mode`
   - Confirm: "Local mode set to [mode]. This project will use [mode] regardless of global setting."

4. If no argument or invalid:
   - Show usage options above

## Mode Details

### research
Collaborative information gathering:
- Think first, ask if uncertain
- Preserve full content when reorganizing
- Stay in current phase until explicitly moving forward
- Don't jump to implementation

### plan
Design before building:
- Break into phases with clear deliverables
- Identify invariants that must not break
- Output structured plan document
- Wait for approval before coding

### sandbox
POC/experimentation mode:
- Experimentation allowed, failures are learning
- Use fixtures over real data
- Move fast, respect invariants
- Don't ship to production

### scrappy
Rapid integration/validation mode:
- No DONE_REPORT required
- No upfront file reading (except invariants)
- Try → run → fix → next
- Brute force > clever when time matters
- Summary at end (N/M succeeded)

### strict
Production procedures (no mindset):
- Evidence over narrative
- Read files before editing
- Test after each significant change
- DONE_REPORT required
- Paths from invariants.yaml

### production
Full rigor for real users:
- "Right > Fast" mindset
- "You will naturally rush. Resist that."
- All strict procedures
- DONE_REPORT required
- 5 mandatory questions before implementing

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

## Architecture

```
inject.sh (router)
├── global.sh              ← always (push back, investigate)
├── modes/{mode}.sh        ← based on mode setting
└── framework.sh           ← if .council/framework set
```

## Notes
- Global rules always apply regardless of mode
- Modes are sticky until explicitly changed
- Mode affects ALL prompts via UserPromptSubmit hook
- **Precedence:** local (.council/mode) > global (~/.council/mode) > default (strict)
- Use `local` to set per-project modes that don't affect other agents/projects
