# Claude Code Research: Boris's Setup vs Community vs Council-v3

> Comprehensive research on Claude Code configurations, best practices, and how council-v3 compares.
>
> Last updated: 2026-01-12

---

## Table of Contents

1. [Boris Cherny's Actual Setup](#boris-chernys-actual-setup)
2. [The 0xquinto/bcherny-claude Repo (What We Cloned)](#the-0xquintobcherny-claude-repo)
3. [Better Community Alternatives](#better-community-alternatives)
4. [Official Anthropic Best Practices](#official-anthropic-best-practices)
5. [Council-v3 Gap Analysis](#council-v3-gap-analysis)
6. [Recommendations](#recommendations)

---

## Boris Cherny's Actual Setup

**Source:** [Boris's Twitter/X thread](https://twitter-thread.com/t/2007179832300581177) (January 3, 2025)

Boris Cherny is the creator and head of Claude Code at Anthropic. He shared his workflow publicly but **did not share his actual config files**.

### What Boris Actually Does

1. **5 parallel Claude instances** in terminal (tabs numbered 1-5)
   - Uses system notifications to know when Claude needs input
   - [iTerm2 notification setup](https://code.claude.com/docs/en/terminal-config#iterm-2-system-notifications)

2. **5-10 more instances on claude.ai/code** in browser
   - Hands off local sessions to web using `&`
   - Uses `--teleport` to move sessions between local and web
   - Starts sessions from phone (Claude iOS app) throughout the day

3. **Opus 4.5 with thinking** for everything
   > "It's the best coding model I've ever used, and even though it's bigger & slower than Sonnet, since you have to steer it less and it's better at tool use, it is almost always faster than using a smaller model in the end."

4. **Shared CLAUDE.md** checked into git
   - Whole team contributes multiple times a week
   - "Anytime we see Claude do something incorrectly we add it to the CLAUDE.md"

5. **@.claude on GitHub PRs** via GitHub action
   - Tags coworkers' PRs to add things to CLAUDE.md
   - Uses `/install-github-action`

6. **Plan mode** for most sessions (shift+tab twice)
   > "If my goal is to write a Pull Request, I will use Plan mode, and go back and forth with Claude until I like its plan. From there, I switch into auto-accept edits mode and Claude can usually 1-shot it."

7. **Slash commands** in `.claude/commands/`
   - Uses `/commit-push-pr` dozens of times daily
   - Commands use inline bash to pre-compute git status

8. **Subagents** for common workflows
   - `code-simplifier` - simplifies code after Claude is done
   - `verify-app` - detailed instructions for testing end-to-end
   - Thinks of subagents as "automating the most common workflows for most PRs"

9. **PostToolUse hook** for formatting
   - Handles the last 10% of formatting to avoid CI errors

10. **Pre-allowed permissions** in `.claude/settings.json`
    - Doesn't use `--dangerously-skip-permissions`
    - Uses `/permissions` to pre-allow safe commands

11. **MCP integrations**
    - Slack (via MCP server) - searches and posts
    - BigQuery (via bq CLI) - analytics queries
    - Sentry - error logs
    - Config checked into `.mcp.json` and shared with team

12. **Long-running tasks**
    - Prompts Claude to verify with background agent when done
    - Uses Stop hook for deterministic verification
    - Uses **ralph-wiggum plugin** for autonomous loops
    - Uses `--permission-mode=dontAsk` or `--dangerously-skip-permissions` in sandboxes

13. **Verification** (the most important thing)
    > "Probably the most important thing to get great results out of Claude Code -- give Claude a way to verify its work. If Claude has that feedback loop, it will 2-3x the quality of the final result."

    - Tests every change to claude.ai/code using Chrome extension
    - Opens browser, tests UI, iterates until it works
    - Different for each domain: bash command, test suite, browser/phone simulator

### What Boris Did NOT Share

- Exact content of his agent files
- Exact content of his command files
- His actual settings.json
- His .mcp.json configuration
- Internal Anthropic tooling (Chrome extension for UI testing)

### Key Stats from Community TL;DR

- Completes **50-100 PRs per week**
- **10-20% of sessions abandoned** due to unexpected scenarios
- Each agent works in **separate git checkout** (not worktrees)
- "People over-complicate it" - verification loops are simple

---

## The 0xquinto/bcherny-claude Repo

**Source:** [github.com/0xquinto/bcherny-claude](https://github.com/0xquinto/bcherny-claude)

**IMPORTANT:** This is NOT Boris's actual config. It's a community-created interpretation based on his Twitter thread.

### What It Contains

```
bcherny-claude/
├── .claude/
│   ├── agents/
│   │   ├── code-architect.md
│   │   ├── code-simplifier.md
│   │   ├── verify-app.md
│   │   ├── build-validator.md
│   │   └── oncall-guide.md
│   ├── commands/
│   │   ├── commit-push-pr.md
│   │   ├── quick-commit.md
│   │   ├── test-and-fix.md
│   │   ├── review-changes.md
│   │   └── first-principles.md
│   └── settings.json
├── CLAUDE.md
└── README.md
```

### Agents (Community Interpretations)

| Agent | Purpose |
|-------|---------|
| code-architect | Design reviews, refactoring planning, dependency analysis |
| code-simplifier | Refactors and cleans code after development |
| verify-app | Static analysis, automated tests, manual verification, edge cases |
| build-validator | Confirms successful project builds |
| oncall-guide | Production troubleshooting assistance |

### Commands

| Command | Purpose |
|---------|---------|
| /commit-push-pr | Full git workflow: status → diff → add → commit → push → PR |
| /quick-commit | Fast commit with auto-generated message |
| /test-and-fix | Run tests and fix failures |
| /review-changes | Analyze uncommitted modifications |
| /first-principles | Deconstruct problems to fundamentals |

### settings.json (JS/npm focused)

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run build:*)",
      "Bash(npm run lint:*)",
      "Bash(npm run test:*)",
      "Bash(git *)",
      "Bash(gh *)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(node:*)",
      "Bash(npx:*)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{
          "type": "command",
          "command": "npm run format 2>/dev/null || npx prettier --write \"$CLAUDE_FILE_PATH\" 2>/dev/null || true"
        }]
      }
    ]
  }
}
```

### Is It Enough?

**For basic workflows:** Yes. The agents and commands cover the common patterns Boris described.

**What it lacks:**
- MCP integrations (Slack, BigQuery, Sentry)
- GitHub action setup
- Ralph-wiggum plugin
- Any advanced verification hooks
- Chrome extension integration (internal Anthropic tooling)

---

## Better Community Alternatives

### 1. ChrisWiles/claude-code-showcase (4.1k stars)

**Source:** [github.com/ChrisWiles/claude-code-showcase](https://github.com/ChrisWiles/claude-code-showcase)

**The most comprehensive public setup.** Significantly more advanced than bcherny-claude.

#### Features

| Category | What It Has |
|----------|-------------|
| Agents | code-reviewer, github-workflow |
| Commands | onboard, ticket, pr-review, pr-summary, code-quality, docs-sync |
| Skills | testing-patterns, systematic-debugging, react-ui-patterns, graphql-schema, core-components, formik-patterns |
| Hooks | PreToolUse, PostToolUse, UserPromptSubmit, Stop (with skill evaluation engine) |
| MCP | JIRA, Linear, GitHub, Slack, Sentry, PostgreSQL |
| GitHub Actions | PR review, docs sync, code quality, dependency audit |

#### Unique Features

1. **Intelligent Skill Activation** - Analyzes prompts and suggests relevant skills
2. **JIRA/Linear Integration** - Complete ticket-to-PR lifecycle
3. **Scheduled Maintenance** - Automated quality sweeps
4. **Skill Evaluation Engine** - Confidence scoring for keyword/pattern matches

#### Monthly Cost Estimate

~$10-$50 depending on PR volume for GitHub Actions.

---

### 2. hesreallyhim/awesome-claude-code (20k+ stars)

**Source:** [github.com/hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)

**Curated list of 200+ resources.** Not a config itself, but a comprehensive index.

#### Key Resources Listed

| Category | Notable Items |
|----------|---------------|
| Orchestrators | Claude Squad (parallel agents), ralph-orchestrator, TSK (Rust CLI with Docker) |
| Workflows | RIPER (Research-Innovate-Plan-Execute-Review), AB Method, Claude Code PM |
| Hooks | TDD Guard, TypeScript Quality Hooks, CC Notify |
| Commands | 60+ documented slash commands |
| Monitoring | CC Usage, ccflare, Usage Monitor with burn rate predictions |

#### Notable Workflow Patterns

- **Subagent Orchestration**
- **Progressive Skills**
- **Parallel Tool Calling**
- **Master-Clone Architecture**
- **Wizard Workflows**

---

### 3. centminmod/my-claude-code-setup (1.6k stars)

**Source:** [github.com/centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup)

**Memory bank system** - persistent documentation across sessions.

#### Unique Features

1. **Memory Bank Synchronizer** - Keeps docs in sync with code
2. **Chain of Draft Mode** - 80% token reduction
3. **Code Searcher Agent** - Efficient codebase navigation
4. **Git Worktree Launchers** - Platform-specific (bash, PowerShell, CMD)
5. **Z.AI Integration** - Cost-effective alternative ($3/month)

#### Agents

| Agent | Purpose |
|-------|---------|
| memory-bank-synchronizer | Validates patterns and cross-references |
| code-searcher | Locates functions/classes efficiently |
| get-current-datetime | Timezone-aware timestamps |
| ux-design-expert | UI/UX guidance, Tailwind, Highcharts |

#### Commands

| Command | Purpose |
|---------|---------|
| /update-memory-bank | Sync documentation |
| /security-audit | OWASP-based analysis |
| /secure-prompts | Prompt injection detection |
| /refactor-code | Create plans without modifying |
| /cleanup-context | 15-25% token reduction |

---

### 4. feiskyer/claude-code-settings

**Source:** [github.com/feiskyer/claude-code-settings](https://github.com/feiskyer/claude-code-settings)

Focused on "vibe coding" - settings, commands, and agents for flow state.

---

### 5. zebbern/claude-code-guide

**Source:** [github.com/zebbern/claude-code-guide](https://github.com/zebbern/claude-code-guide)

Comprehensive guide with SKILL.md files, agents, commands, and workflows.

---

## Official Anthropic Best Practices

**Source:** [anthropic.com/engineering/claude-code-best-practices](https://www.anthropic.com/engineering/claude-code-best-practices)

### Recommended Workflows

1. **Explore-Plan-Code-Commit**
   - Read relevant files first
   - Create detailed plan (use "think" for extended thinking)
   - Implement and commit

2. **Test-Driven Development**
   - Write tests first
   - Confirm they fail
   - Have Claude implement to pass

3. **Visual Iteration**
   - Provide design mocks/screenshots
   - Claude implements and screenshots results
   - Iterate toward matching target

### Key Recommendations

| Recommendation | Why |
|----------------|-----|
| Be Specific | Detailed instructions improve first-attempt success |
| Provide Context | Use images, URLs, file references |
| Course Correct Early | Use `/clear` between tasks; Escape to interrupt |
| Use Checklists | Markdown checklists as working scratchpads |
| Multi-Claude Workflows | Separate instances for writing vs reviewing |
| Git Worktrees | Enable parallel independent tasks |
| Headless Mode | `-p` flag for CI/CD integration |

### CLAUDE.md Best Practices

- Keep concise and human-readable
- Document bash commands, code style, testing instructions
- No required format

---

## Council-v3 Gap Analysis

### What Council-v3 Has

| Component | Source | Status |
|-----------|--------|--------|
| 5 agents | bcherny-claude | ✅ Identical |
| 13 commands | bcherny-claude + v2 custom | ✅ Superset |
| PostToolUse hook | Custom (black) | ✅ Have it |
| Stop hook | Custom | ✅ Extra (Boris doesn't have in public) |
| Notification hook | Custom | ✅ Extra |
| CLAUDE.md | Custom | ✅ Have it |
| STATE.md/LOG.md | Custom | ✅ Extra pattern |
| Dispatcher | council-v2 | ✅ Unique value |
| Circuit breaker | council-v2 | ✅ Similar to ralph-wiggum |
| Voice input (FIFO) | council-v2 | ✅ Unique |
| Phone commands | Telegram/Pushover | ✅ Different from Boris's iOS |

### What Council-v3 is Missing

| Component | Boris Has | Better Repos Have | Priority |
|-----------|-----------|-------------------|----------|
| MCP integrations | Slack, BigQuery, Sentry | JIRA, Linear, PostgreSQL | **HIGH** if you need them |
| Ralph-wiggum plugin | Yes | ralph-orchestrator | MEDIUM |
| GitHub action | @.claude on PRs | PR review actions | MEDIUM |
| Skill evaluation | No | claude-code-showcase | LOW |
| Memory bank | No | my-claude-code-setup | LOW |
| Teleport | Yes | No | LOW |
| Chrome extension | Internal Anthropic | No | N/A (internal) |

### Honest Assessment

**Council-v3 has 80-90% of Boris's PUBLIC setup.**

The gaps:
1. **MCP integrations** - Only if you need Slack/BigQuery/Sentry/JIRA
2. **Ralph-wiggum** - For truly autonomous long-running tasks (circuit breaker covers most cases)
3. **GitHub action** - For team collaboration on CLAUDE.md

**Claude-code-showcase is objectively more comprehensive** for:
- Skills system
- JIRA/Linear integration
- GitHub Actions
- Advanced hooks

**But Boris himself says his setup is "surprisingly vanilla."**

---

## Recommendations

### For Council-v3 Specifically

#### Keep As-Is (Working)
- All 5 Boris-style agents
- All 13 commands
- PostToolUse, Stop, Notification hooks
- Dispatcher with FIFO, Telegram, Pushover
- Circuit breaker

#### Consider Adding

1. **MCP Integrations** (if useful for your workflow)
   ```json
   // .mcp.json
   {
     "mcpServers": {
       "slack": {
         "type": "http",
         "url": "https://slack.mcp.anthropic.com/mcp"
       }
     }
   }
   ```

2. **GitHub Action** (if you have a team)
   - Install with `/install-github-action`
   - Enables @.claude on PRs

3. **Skills from claude-code-showcase** (if you want domain-specific knowledge)
   - testing-patterns
   - systematic-debugging

#### Don't Bother With
- Skill evaluation engine (over-engineered)
- Memory bank system (STATE.md/LOG.md is simpler)
- Z.AI integration (unless budget constrained)

### The Real Answer

From Boris:
> "People over-complicate it. Just give Claude a tool to see the output of its code and describe the tool well. Claude will figure out the rest."

From community TL;DR:
> "The general vibe is 'cool setup, but must be nice' [referring to Boris's unlimited tokens]"

**Council-v3 is enough.** The unique value (voice input, phone commands, multi-agent dispatch) exceeds what most public repos offer.

The question isn't "do we have enough tooling?" It's "are we using what we have?"

---

## Sources

- [Boris's Twitter Thread](https://twitter-thread.com/t/2007179832300581177)
- [0xquinto/bcherny-claude](https://github.com/0xquinto/bcherny-claude) (community interpretation)
- [ChrisWiles/claude-code-showcase](https://github.com/ChrisWiles/claude-code-showcase) (most comprehensive)
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) (200+ resources)
- [centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup) (memory bank)
- [Anthropic Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [How Boris Uses Claude Code](https://paddo.dev/blog/how-boris-uses-claude-code/)
- [VentureBeat Article](https://venturebeat.com/technology/the-creator-of-claude-code-just-revealed-his-workflow-and-developers-are)

---

## Appendix: Full Boris Thread (13 Points)

1. **5 parallel Claudes** in terminal with notifications
2. **5-10 more on claude.ai/code** with teleport and phone sessions
3. **Opus 4.5 with thinking** for everything
4. **Shared CLAUDE.md** team contributes weekly
5. **@.claude on PRs** via GitHub action
6. **Plan mode** for most sessions
7. **Slash commands** in `.claude/commands/`
8. **Subagents** (code-simplifier, verify-app)
9. **PostToolUse hook** for formatting
10. **Pre-allowed permissions** via `/permissions`
11. **MCP integrations** (Slack, BigQuery, Sentry)
12. **Long-running tasks** (ralph-wiggum, Stop hooks, sandbox mode)
13. **Verification** - give Claude a way to verify its work (2-3x quality)
