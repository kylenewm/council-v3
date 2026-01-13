# Ralph Queue Plugin

Task queue extension for Ralph Loop - queue multiple tasks and execute them sequentially.

## What It Does

- Queue multiple Ralph tasks with pipe syntax
- Execute them one after another automatically
- Each task runs as a full Ralph loop until completion
- When one completes, the next auto-starts

## Commands

### /ralph-queue

Add tasks to the queue:

```bash
/ralph-queue "task 1" | "task 2" | "task 3" --max-iterations 20 --completion-promise "DONE"
```

Options:
- `--max-iterations N` - Max iterations per task (default: 10)
- `--completion-promise TEXT` - Completion signal (default: "DONE")

### /ralph-queue-start

Start executing the queue:

```bash
/ralph-queue-start
```

### /ralph-queue-status

Check queue status:

```bash
/ralph-queue-status
```

### /ralph-queue-clear

Clear the queue:

```bash
/ralph-queue-clear
```

## How It Works

1. Tasks are stored in `.claude/ralph-queue.local.json`
2. `/ralph-queue-start` begins the first task as a Ralph loop
3. When Ralph completes, the queue stop hook:
   - Marks current task complete
   - Gets next pending task
   - Starts new Ralph loop with that task
4. Continues until queue empty

## Example: P0 Tasks

```bash
/ralph-queue "Implement copy-mode guard: Add pane_in_copy_mode() function to simple.py. Test with test_copy_mode.py. Output <promise>DONE</promise> when tests pass." | "Implement config validation: Add validate_config() to simple.py. Test with test_config_validation.py. Output <promise>DONE</promise> when tests pass." | "Add --dry-run mode to dispatcher. Test with test_dry_run.py. Output <promise>DONE</promise> when tests pass." --max-iterations 15 --completion-promise "DONE"

/ralph-queue-start
```

## Files

- `.claude/ralph-queue.local.json` - Queue state (gitignored)
- `.claude/ralph-loop.local.md` - Current Ralph task (managed by Ralph Loop plugin)

## Requirements

- Ralph Loop plugin must be installed
- This plugin's stop hook runs after Ralph's to check for next task
