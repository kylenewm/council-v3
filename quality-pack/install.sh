#!/bin/bash
# Quality Pack Installer
# Installs Claude Code quality infrastructure for consistent, high-quality development
#
# Usage:
#   ./install.sh              # Install global configs only
#   ./install.sh --project    # Also set up current project
#   ./install.sh --help       # Show help
#
# What it does:
#   Global (always):
#     - ~/.claude/CLAUDE.md - Global quality rules
#     - ~/.council/hooks/ - Mode injection system
#
#   Project (--project flag):
#     - .claude/settings.json - Permissions and hooks
#     - .claude/commands/ - Slash commands
#     - .claude/agents/ - Default agents
#     - .council/ - Mode and invariants
#     - CLAUDE.md - Project instructions (if not exists)
#     - STATE.md - Work tracking (if not exists)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_DIR="$SCRIPT_DIR/global"
PROJECT_DIR="$SCRIPT_DIR/project"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << 'EOF'
Quality Pack Installer

USAGE:
    ./install.sh [OPTIONS]

OPTIONS:
    --project     Also set up current directory as a project
    --force       Overwrite existing files (default: skip existing)
    --help        Show this help message

EXAMPLES:
    # Install global configs only (safe, doesn't touch projects)
    ./install.sh

    # Set up current directory as a project
    ./install.sh --project

    # Force overwrite existing files
    ./install.sh --project --force

WHAT GETS INSTALLED:

    Global (~/.claude/, ~/.council/):
        - CLAUDE.md: Quality rules that apply to all projects
        - hooks/inject.sh: Main injection router
        - hooks/auto-inject.sh: Global mindset rules
        - hooks/type-check.sh: Language-aware type checking (mypy, tsc, go vet)
        - hooks/notify-rich.sh: Rich notifications on stop
        - hooks/modes/*.sh: Mode-specific prompts

    Project (current directory):
        - .claude/settings.json: Permissions and hooks
        - .claude/commands/: Slash commands (/test, /commit, /done, etc)
        - .claude/agents/: Agent definitions
        - .council/mode: Current mode (default: production)
        - .council/invariants.yaml: Forbidden/protected paths
        - CLAUDE.md: Project-specific instructions
        - STATE.md: Work tracking

MODES AVAILABLE:
    strict      Production code, evidence over narrative
    production  Strict + critical mindset
    plan        Design before building
    review      Adversarial context-blind critique
    sandbox     Quick POC iteration
    scrappy     Rapid validation, brute force OK
    critical    High stakes, right over fast

RIPER WORKFLOW (via /riper:* commands):
    /riper:strict    Activate strict RIPER protocol
    /riper:research  Research mode (read-only)
    /riper:innovate  Brainstorming mode (read-only)
    /riper:plan      Create specifications (memory-bank only)
    /riper:execute   Implement approved plan
    /riper:review    Validate implementation

TDD GUARD:
    PreToolUse hook that warns when editing implementation code
    without failing tests. Enforces test-first development.
    First warning allows override on retry.

AFTER INSTALLATION:
    Use /inject <mode> to switch modes
    Use /test, /commit, /done, /ship for workflows
    Use /bug, /feature, /refactor for task-specific workflows
    Use /riper:strict to start RIPER workflow for complex tasks
EOF
}

install_global() {
    log_info "Installing global configs..."

    # Create directories
    mkdir -p "$HOME/.claude"
    mkdir -p "$HOME/.council/hooks/modes"
    mkdir -p "$HOME/.council/hooks/python"

    # Copy global CLAUDE.md
    if [[ ! -f "$HOME/.claude/CLAUDE.md" ]] || [[ "$FORCE" == "true" ]]; then
        cp "$GLOBAL_DIR/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
        log_info "Installed ~/.claude/CLAUDE.md"
    else
        log_warn "~/.claude/CLAUDE.md exists, skipping (use --force to overwrite)"
    fi

    # Copy shell hooks
    for hook in inject.sh auto-inject.sh type-check.sh notify-rich.sh; do
        if [[ -f "$GLOBAL_DIR/hooks/$hook" ]]; then
            if [[ ! -f "$HOME/.council/hooks/$hook" ]] || [[ "$FORCE" == "true" ]]; then
                cp "$GLOBAL_DIR/hooks/$hook" "$HOME/.council/hooks/$hook"
                chmod +x "$HOME/.council/hooks/$hook"
                log_info "Installed ~/.council/hooks/$hook"
            else
                log_warn "~/.council/hooks/$hook exists, skipping"
            fi
        fi
    done

    # Copy Python hooks (TDD Guard, file checker, etc.)
    if [[ -d "$GLOBAL_DIR/hooks/python" ]]; then
        for py_hook in "$GLOBAL_DIR/hooks/python/"*.py; do
            if [[ -f "$py_hook" ]]; then
                hook_name=$(basename "$py_hook")
                if [[ ! -f "$HOME/.council/hooks/python/$hook_name" ]] || [[ "$FORCE" == "true" ]]; then
                    cp "$py_hook" "$HOME/.council/hooks/python/$hook_name"
                    chmod +x "$HOME/.council/hooks/python/$hook_name"
                    log_info "Installed ~/.council/hooks/python/$hook_name"
                else
                    log_warn "~/.council/hooks/python/$hook_name exists, skipping"
                fi
            fi
        done
    fi

    # Copy mode scripts (excluding riper.sh - RIPER is now commands/agents based)
    for mode_script in "$GLOBAL_DIR/hooks/modes/"*.sh; do
        mode_name=$(basename "$mode_script")
        # Skip riper.sh - RIPER workflow uses commands/agents now
        if [[ "$mode_name" == "riper.sh" ]]; then
            continue
        fi
        if [[ ! -f "$HOME/.council/hooks/modes/$mode_name" ]] || [[ "$FORCE" == "true" ]]; then
            cp "$mode_script" "$HOME/.council/hooks/modes/$mode_name"
            chmod +x "$HOME/.council/hooks/modes/$mode_name"
            log_info "Installed ~/.council/hooks/modes/$mode_name"
        else
            log_warn "~/.council/hooks/modes/$mode_name exists, skipping"
        fi
    done

    log_info "Global installation complete!"
}

install_project() {
    log_info "Setting up project in current directory..."

    # Create directories
    mkdir -p .claude/commands/riper .claude/agents .council .claude/memory-bank

    # Copy settings.json
    if [[ ! -f ".claude/settings.json" ]] || [[ "$FORCE" == "true" ]]; then
        cp "$PROJECT_DIR/settings.json" ".claude/settings.json"
        log_info "Installed .claude/settings.json"
    else
        log_warn ".claude/settings.json exists, skipping"
    fi

    # Copy commands
    for cmd in "$PROJECT_DIR/commands/"*.md; do
        cmd_name=$(basename "$cmd")
        if [[ ! -f ".claude/commands/$cmd_name" ]] || [[ "$FORCE" == "true" ]]; then
            cp "$cmd" ".claude/commands/$cmd_name"
            log_info "Installed .claude/commands/$cmd_name"
        else
            log_warn ".claude/commands/$cmd_name exists, skipping"
        fi
    done

    # Copy RIPER commands (subcommands like /riper:strict, /riper:research, etc.)
    if [[ -d "$PROJECT_DIR/commands/riper" ]]; then
        for cmd in "$PROJECT_DIR/commands/riper/"*.md; do
            if [[ -f "$cmd" ]]; then
                cmd_name=$(basename "$cmd")
                if [[ ! -f ".claude/commands/riper/$cmd_name" ]] || [[ "$FORCE" == "true" ]]; then
                    cp "$cmd" ".claude/commands/riper/$cmd_name"
                    log_info "Installed .claude/commands/riper/$cmd_name"
                else
                    log_warn ".claude/commands/riper/$cmd_name exists, skipping"
                fi
            fi
        done
    fi

    # Copy agents
    for agent in "$PROJECT_DIR/agents/"*.md; do
        agent_name=$(basename "$agent")
        if [[ ! -f ".claude/agents/$agent_name" ]] || [[ "$FORCE" == "true" ]]; then
            cp "$agent" ".claude/agents/$agent_name"
            log_info "Installed .claude/agents/$agent_name"
        else
            log_warn ".claude/agents/$agent_name exists, skipping"
        fi
    done

    # Set default mode
    if [[ ! -f ".council/mode" ]] || [[ "$FORCE" == "true" ]]; then
        echo "production" > ".council/mode"
        log_info "Set default mode to 'production' in .council/mode"
    else
        log_warn ".council/mode exists, skipping"
    fi

    # Copy invariants template
    if [[ ! -f ".council/invariants.yaml" ]] || [[ "$FORCE" == "true" ]]; then
        cp "$PROJECT_DIR/templates/invariants.yaml.tmpl" ".council/invariants.yaml"
        log_info "Installed .council/invariants.yaml (customize for your project)"
    else
        log_warn ".council/invariants.yaml exists, skipping"
    fi

    # Create STATE.md from template
    if [[ ! -f "STATE.md" ]] || [[ "$FORCE" == "true" ]]; then
        DATE=$(date +%Y-%m-%d)
        sed "s/{{DATE}}/$DATE/g" "$PROJECT_DIR/templates/STATE.md.tmpl" > "STATE.md"
        log_info "Created STATE.md"
    else
        log_warn "STATE.md exists, skipping"
    fi

    # Create basic CLAUDE.md if not exists
    if [[ ! -f "CLAUDE.md" ]]; then
        PROJECT_NAME=$(basename "$(pwd)")
        cat > "CLAUDE.md" << EOF
# Project: $PROJECT_NAME

## Overview

_Add project description here_

## Before Anything Else

1. Read STATE.md - Current work status
2. Read this file - Project conventions

## Commands

\`\`\`bash
# Run tests
pytest tests/ -v  # Customize for your project

# Run linter
ruff check .  # Customize for your project
\`\`\`

## Key Files

| File | Purpose |
|------|---------|
| _file_ | _purpose_ |

## Slash Commands

| Command | What |
|---------|------|
| \`/test\` | Run tests |
| \`/commit\` | Stage and commit |
| \`/done\` | Verify before complete |
| \`/ship\` | Test, commit, push, PR |
| \`/bug\` | Bug fix workflow |
| \`/feature\` | Feature workflow |
| \`/inject\` | Set mode |

## Context Files

| File | Purpose |
|------|---------|
| STATE.md | Current work, blockers |
EOF
        log_info "Created CLAUDE.md (customize for your project)"
    else
        log_warn "CLAUDE.md exists, skipping"
    fi

    log_info "Project setup complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Customize CLAUDE.md with your project details"
    echo "  2. Customize .council/invariants.yaml with forbidden/protected paths"
    echo "  3. Use /inject <mode> to switch modes (production, strict, plan, etc)"
    echo "  4. Use /test, /commit, /done, /ship for workflows"
}

# Parse arguments
INSTALL_PROJECT=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --project)
            INSTALL_PROJECT=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Verify we're in the right place
if [[ ! -d "$GLOBAL_DIR" ]] || [[ ! -d "$PROJECT_DIR" ]]; then
    log_error "Cannot find quality-pack directories. Run this script from the quality-pack directory."
    exit 1
fi

# Install global configs
install_global

# Optionally install project configs
if [[ "$INSTALL_PROJECT" == "true" ]]; then
    echo ""
    install_project
fi

echo ""
log_info "Done! Quality pack installed successfully."
