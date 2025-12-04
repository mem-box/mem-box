#!/usr/bin/env bash
# Memory Box Bash Integration
# Automatically captures commands to Memory Box
#
# Usage: Add to your ~/.bashrc:
#   source /path/to/memory-box/shell/bash-integration.sh
#
# Configuration (optional):
#   export MEMORY_BOX_CAPTURE_SUCCESS_ONLY=1  # Only capture successful commands
#   export MEMORY_BOX_PYTHON=python3           # Python executable path

# Configuration
MEMORY_BOX_CAPTURE_SUCCESS_ONLY="${MEMORY_BOX_CAPTURE_SUCCESS_ONLY:-0}"
MEMORY_BOX_PYTHON="${MEMORY_BOX_PYTHON:-python3}"

# Store the last command and exit code
__memory_box_last_command=""
__memory_box_last_exit_code=0

# Capture command before execution (bash doesn't have preexec, so we use DEBUG trap)
__memory_box_preexec() {
    # Get the command from BASH_COMMAND
    __memory_box_last_command="$BASH_COMMAND"
}

# Capture after command execution
__memory_box_precmd() {
    local exit_code=$?
    __memory_box_last_exit_code=$exit_code

    # Skip if no command or if it's the memory-box capture command itself
    if [[ -z "$__memory_box_last_command" ]] || [[ "$__memory_box_last_command" == *"memory-box capture"* ]]; then
        return
    fi

    # Skip internal commands
    case "$__memory_box_last_command" in
        __memory_box_*|*PROMPT_COMMAND*)
            return
            ;;
    esac

    # Capture the command
    local success_only_flag=""
    if [[ "$MEMORY_BOX_CAPTURE_SUCCESS_ONLY" == "1" ]]; then
        success_only_flag="--success-only"
    fi

    # Run capture in background to avoid blocking the prompt
    "$MEMORY_BOX_PYTHON" -m server.cli capture \
        "$__memory_box_last_command" \
        --exit-code "$exit_code" \
        --cwd "$PWD" \
        $success_only_flag \
        2>/dev/null &

    # Clear the command
    __memory_box_last_command=""
}

# Set up the hooks
# Use DEBUG trap to capture command before execution
trap '__memory_box_preexec' DEBUG

# Add to PROMPT_COMMAND to capture after execution
if [[ -z "$PROMPT_COMMAND" ]]; then
    PROMPT_COMMAND="__memory_box_precmd"
elif [[ "$PROMPT_COMMAND" != *"__memory_box_precmd"* ]]; then
    PROMPT_COMMAND="__memory_box_precmd;$PROMPT_COMMAND"
fi

echo "Memory Box bash integration loaded. Commands will be automatically captured."
