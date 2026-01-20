# Inject Mode Toggle

Toggle context injection modes for different work types.

## Usage

- `/inject strict` - Production mode: ask first, verify after, respect invariants
- `/inject production` - Full production mode: strict + critical mindset
- `/inject sandbox` - POC mode: quick iteration with fixtures, move fast
- `/inject scrappy` - Rapid mode: try fast, validate fast, no overhead
- `/inject plan` - Planning mode: design before building, slow and steady
- `/inject review` - Adversarial review mode: context-blind critique
- `/inject critical` - High-stakes mode: right over fast
- `/inject riper` - 5-phase workflow: Research-Innovate-Plan-Execute-Review
- `/inject off` - Disable mode-specific injection (global rules still apply)
- `/inject status` - Show current mode
- `/inject local <mode>` - Set mode for current project only (creates .council/mode)

## What to do

When user runs this command with argument `$ARGUMENTS`:

1. If argument is `status`:
   - Read `~/.council/current_inject.txt`
   - Also check `.council/mode` for local override
   - Report current mode (local overrides global)

2. If argument is `strict`, `production`, `sandbox`, `scrappy`, `plan`, `review`, `critical`, `riper`, or `off`:
   - Write the argument to `~/.council/current_inject.txt`
   - Confirm: "Injection mode set to [mode]. This will apply to all prompts until changed."

3. If argument is `local <mode>`:
   - Create `.council/` directory if needed
   - Write the mode to `.council/mode`
   - Confirm: "Local mode set to [mode]. This project will use [mode] regardless of global setting."

4. If no argument or invalid:
   - Show usage options above

## Mode Precedence

local (.council/mode) > global (~/.council/current_inject.txt)

## Notes

- Global mindset rules always apply regardless of mode
- Modes are sticky until explicitly changed
- Mode affects ALL prompts in this session via UserPromptSubmit hook
