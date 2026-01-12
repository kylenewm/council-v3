# REFLECTIONS.md

Self-reflection log for real-world friction, struggles, and optimization ideas.

---

<!-- Append new reflections below this line -->

## 2026-01-12 Building Dispatcher Test Suite

**Situation:** Building a test suite for the 888-line dispatcher from scratch.

**Struggle:** Minor issue with GitSnapshot class - assumed wrong field names (`commit_hash`, `modified_files`) when actual fields are (`status_hash`, `head_hash`, `combined_hash`). Had to check gitwatch.py to get correct signature.

**Workaround:** Quick grep to find the dataclass definition, fixed the test.

**Suggestion:** When testing code that uses external dataclasses, check the actual class definition first rather than guessing field names. Could add type hints or docstrings to gitwatch.py to make this more discoverable.
