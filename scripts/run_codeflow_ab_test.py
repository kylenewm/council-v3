#!/usr/bin/env python3
"""
A/B Test: CodeFlow MCP vs Traditional Search

Sends same prompt to two agents:
- Control (no MCP): Uses grep/glob/read only
- Experimental (with MCP): Has CodeFlow tools available

Compares: accuracy, tool calls, time
"""

import subprocess
import time
import json
from pathlib import Path
from datetime import datetime

# Test configuration
CODEBASE_PATH = "/Users/kylenewman/Downloads/codeflow-viz"
FIFO_PATH = Path.home() / ".council" / "in.fifo"

CONTROL_AGENT = "5"  # JungleGym-Control
EXPERIMENTAL_AGENT = "6"  # JungleGym-Experimental

TEST_QUESTION = """
Analyze the codebase at /Users/kylenewman/Downloads/codeflow-viz

Question: "What functions handle rule evaluation, and what does each one do?"

IMPORTANT:
- List each function name
- Describe what it does (1-2 sentences)
- Report how many tool calls you made
- Report which tools you used

Be thorough and accurate.
"""

CONTROL_PROMPT = f"""
CONTROL TEST - NO MCP TOOLS

{TEST_QUESTION}

CONSTRAINT: Only use Grep, Glob, Read, and Bash tools. Do NOT use any MCP tools.
"""

EXPERIMENTAL_PROMPT = f"""
EXPERIMENTAL TEST - USE MCP TOOLS

{TEST_QUESTION}

Use CodeFlow MCP tools if available:
- query_concepts (semantic search)
- search_functions (find by name)
- get_semantic_snapshot (overview)
- get_callers / get_callees (call graph)

Report which MCP tools you used.
"""


def send_to_agent(agent_id: str, message: str) -> bool:
    """Send message to agent via dispatcher FIFO."""
    if not FIFO_PATH.exists():
        print(f"Error: FIFO not found at {FIFO_PATH}")
        print("Start dispatcher with: python -m council.dispatcher.simple")
        return False

    try:
        cmd = f"{agent_id}: {message}"
        with open(FIFO_PATH, "w") as f:
            f.write(cmd + "\n")
        return True
    except Exception as e:
        print(f"Error sending to agent: {e}")
        return False


def run_test():
    """Run A/B test."""
    print("=" * 60)
    print("CodeFlow A/B Test")
    print("=" * 60)
    print(f"Control Agent: {CONTROL_AGENT} (no MCP)")
    print(f"Experimental Agent: {EXPERIMENTAL_AGENT} (with MCP)")
    print(f"Codebase: {CODEBASE_PATH}")
    print("=" * 60)

    # Check FIFO exists
    if not FIFO_PATH.exists():
        print(f"\nError: Dispatcher FIFO not found at {FIFO_PATH}")
        print("Start dispatcher first: python -m council.dispatcher.simple")
        return

    # Send to control agent
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Sending to Control Agent {CONTROL_AGENT}...")
    if not send_to_agent(CONTROL_AGENT, CONTROL_PROMPT):
        return
    print("  Sent!")

    # Small delay
    time.sleep(2)

    # Send to experimental agent
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Sending to Experimental Agent {EXPERIMENTAL_AGENT}...")
    if not send_to_agent(EXPERIMENTAL_AGENT, EXPERIMENTAL_PROMPT):
        return
    print("  Sent!")

    print("\n" + "=" * 60)
    print("Tests started! Monitor agents in tmux panes:")
    print(f"  Control: tmux select-pane -t %16")
    print(f"  Experimental: tmux select-pane -t %17")
    print("=" * 60)
    print("\nWhen both complete, compare:")
    print("  1. Which found more functions?")
    print("  2. Which descriptions are more accurate?")
    print("  3. How many tool calls each used?")
    print("  4. Which was faster?")


if __name__ == "__main__":
    run_test()
