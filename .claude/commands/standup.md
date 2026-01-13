# Standup Report

Generate daily standup from all council agents.

## Steps

1. Read config:
```bash
cat ~/.council/config.yaml
```

2. For each agent worktree, get last 24h commits:
```bash
git -C <worktree> log --since="24 hours ago" --oneline
```

3. Read STATE.md from each worktree (if exists)

4. Format output:

```
# Daily Standup - [DATE]

## Agent: [NAME]
Worktree: [PATH]

### Yesterday (Git Activity)
- [commit messages]

### Today (Current Work)
[From STATE.md]

### Blockers
[From STATE.md or "None"]

---
[Repeat for each agent]
```

## Edge Cases
- No commits: "No activity"
- No STATE.md: "No state file"
- Missing worktree: "Worktree not found"
