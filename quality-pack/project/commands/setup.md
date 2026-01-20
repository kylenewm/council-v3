# Project Setup

Set up quality infrastructure for a new or existing project.

## What This Does

Creates `.claude/` directory with settings, commands, agents, and `.council/` structure.

## Steps

1. **Check current state**
```bash
ls -la .claude/ 2>/dev/null || echo "No .claude directory"
ls -la .council/ 2>/dev/null || echo "No .council directory"
```

2. **Ask about project type**
   Use AskUserQuestion:
   - "What type of project is this?"
   - Options: Python, JavaScript/TypeScript, Go, Rust, Other
   - This affects test commands and linter settings

3. **Create directory structure**
```bash
mkdir -p .claude/commands .claude/agents .council
```

4. **Copy appropriate files**
   Based on project type, create:
   - `.claude/settings.json` - permissions and hooks
   - `.claude/commands/` - slash commands
   - `.claude/agents/strict.md` - default agent

5. **Create CLAUDE.md template**
   - Project name
   - Build/test commands
   - Key files
   - Local conventions

6. **Create .council structure**
   - `.council/mode` - set to "production" by default
   - `.council/invariants.yaml` - forbidden/protected paths

7. **Create STATE.md**
   - Current work section
   - Blockers section
   - Decisions section

8. **Verify setup**
   - Check files exist
   - Test that hooks will work (inject.sh exists)

9. **Report completion**
   - List files created
   - Explain how to use `/inject` to switch modes
   - Suggest running `/test` to verify test setup

## Notes

- This is opinionated - creates a specific structure
- User can customize after setup
- Won't overwrite existing files without asking
