---
description: "Generate daily standup report from all council agents"
allowed-tools: [Read, Bash, Glob, Grep]
---

# Standup Report Generator

Generate a daily standup report by aggregating git activity and STATE.md files from all configured council agents.

## Instructions

1. **Read the council config** from `~/.council/config.yaml` to get the list of agents and their worktrees

2. **For each agent**, gather:
   - **Git log** (last 24 hours): `git log --since="24 hours ago" --oneline` in their worktree
   - **STATE.md** contents from their worktree root (if exists)

3. **Format the output** as a standup report grouped by agent:

```
# Daily Standup - [DATE]

## Agent: [NAME]
Worktree: [PATH]

### Yesterday (Git Activity)
- [commit messages from last 24h]

### Today (Current Work)
[From STATE.md "Current Task" or similar section]

### Blockers
[From STATE.md "Blockers" section, or "None" if empty]

---
[Repeat for each agent]
```

4. **Handle edge cases**:
   - If no commits in 24h: "No activity"
   - If no STATE.md: "No state file found"
   - If worktree doesn't exist: "Worktree not found"

## Example Output

```
# Daily Standup - 2026-01-13

## Agent: CodeflowViz
Worktree: ~/Downloads/codeflow-viz

### Yesterday
- abc123 Add flow visualization component
- def456 Fix edge rendering bug

### Today
Working on node clustering algorithm

### Blockers
None

---

## Agent: DeepResearch
Worktree: ~/Downloads/deep-research-v0

### Yesterday
No activity

### Today
Implementing RAG pipeline

### Blockers
- Waiting on API key for embedding service
```
