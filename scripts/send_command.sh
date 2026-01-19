#!/bin/bash
#
# send_command.sh - Send a command to the council dispatcher via Unix socket
#
# Usage:
#   send_command.sh "1: do something"
#   send_command.sh "status"
#   echo "queue 1 'task'" | send_command.sh
#
# The dispatcher must be running with socket mode enabled.
# Default socket path: ~/.council/council.sock
#

set -e

SOCKET_PATH="${COUNCIL_SOCKET:-$HOME/.council/council.sock}"

# Check if socket exists
if [ ! -S "$SOCKET_PATH" ]; then
    echo "Error: Socket not found at $SOCKET_PATH" >&2
    echo "Is the dispatcher running?" >&2
    exit 1
fi

# Get command from argument or stdin
if [ $# -gt 0 ]; then
    COMMAND="$*"
else
    # Read from stdin
    read -r COMMAND
fi

if [ -z "$COMMAND" ]; then
    echo "Usage: $0 <command>" >&2
    echo "   or: echo 'command' | $0" >&2
    exit 1
fi

# Send command via netcat (nc)
# Use -U for Unix socket, -q 0 to quit after EOF
echo "$COMMAND" | nc -U "$SOCKET_PATH"

# Check exit status
if [ $? -eq 0 ]; then
    echo "Sent: $COMMAND"
else
    echo "Error: Failed to send command" >&2
    exit 1
fi
