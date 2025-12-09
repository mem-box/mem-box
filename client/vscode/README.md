# Memory Box - VS Code Extension

This is a complete VS Code extension that **automatically captures terminal commands** and lets you search/reuse them.

## How It Works

1. **Automatic Capture**: The extension listens to `vscode.window.onDidEndTerminalShellExecution` events
2. **Every command you run** in any VS Code terminal is automatically captured to Memory Box
3. **Search & Reuse**: Use the command palette to search commands and insert them back into terminals

## Files

- **package.json** - Extension manifest and configuration
- **tsconfig.json** - TypeScript configuration
- **src/extension.ts** - Main extension code that hooks into terminal events
- **src/memory-box-client.ts** - Client for communicating with Memory Box bridge
- **README.md** - This file

## Setup

### 1. Install Memory Box (Python package)

```bash
pip install memory-box
```

Or from source:
```bash
cd /workspace
uv sync
```

### 2. Install Extension Dependencies

```bash
cd examples/vscode-extension
npm install
```

### 3. Build the Extension

```bash
npm run compile
```

### 4. Test the Extension

1. Open this folder in VS Code
2. Press `F5` to launch Extension Development Host
3. Open a terminal in the Extension Development Host window
4. Run any command (e.g., `echo "Hello"`)
5. Open Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`)
6. Type "Memory Box: Search Commands"
7. You should see your command!

## Features

### 🎯 Automatic Terminal Capture

Every command you run in **any VS Code terminal** is automatically captured when it finishes executing.

```typescript
// This hooks into VS Code's shell integration
vscode.window.onDidEndTerminalShellExecution(async (event) => {
    const commandLine = event.execution.commandLine.value;
    const exitCode = event.exitCode;
    
    // Automatically save to Memory Box
    await memoryBoxClient.addCommand(commandLine, '');
});
```

**Requirements:**
- VS Code Shell Integration must be enabled (it is by default for bash, zsh, pwsh)
- Only works in integrated terminals (not external terminals)

### 🔍 Search Commands

Use `Memory Box: Search Commands` to find previously run commands:
- Fuzzy search across all your commands
- Shows usage count and timestamps
- Copy to clipboard, insert to terminal, or run immediately

### ➕ Manual Entry

Use `Memory Box: Add Command Manually` to add commands with descriptions and tags.

### ⚙️ Settings

- `memoryBox.autoCapture` - Enable/disable automatic capture (default: true)
- `memoryBox.captureExitCodeZeroOnly` - Only capture successful commands (default: true)
- `memoryBox.pythonPath` - Path to Python (default: "python")

## How Terminal Integration Works

VS Code provides [Shell Integration](https://code.visualstudio.com/docs/terminal/shell-integration) which allows extensions to:

1. **Detect when commands start**: `onDidStartTerminalShellExecution`
2. **Detect when commands end**: `onDidEndTerminalShellExecution`
3. **Access command details**: Command text, exit code, working directory

This extension uses `onDidEndTerminalShellExecution` to capture **every command** from **all terminals** automatically.

### Supported Shells

- ✅ Bash
- ✅ Zsh
- ✅ PowerShell
- ✅ Fish (with shell integration enabled)
- ❌ Cmd.exe (limited support)

### What Gets Captured

- ✅ Command text
- ✅ Exit code
- ✅ Workspace context (current folder)
- ❌ Command output (by design - use `execution.read()` if needed)
- ❌ Environment variables

## Bridge Protocol

The bridge uses JSON over stdin/stdout:

### Request Format

```json
{
    "method": "add_command",
    "params": {
        "command": "docker ps",
        "description": "List containers",
        "tags": ["docker"]
    }
}
```

### Response Format

```json
{
    "result": "command-id-123",
    "error": null
}
```

### Available Methods

- **ping** - Test connection
- **add_command** - Add a command
- **search_commands** - Search with fuzzy matching
- **get_command** - Get by ID
- **list_commands** - List with filters
- **delete_command** - Delete by ID
- **get_all_tags** - Get all tags
- **get_all_categories** - Get all categories

## Architecture

```
VS Code Extension (TypeScript)
    ↓
MemoryBoxClient (stdin/stdout JSON)
    ↓
memory-box-bridge (Python process)
    ↓
MemoryBox API
    ↓
Neo4jClient (Database)
```

## Publishing

To package and publish this extension:

```bash
# Install vsce (VS Code Extension manager)
npm install -g @vscode/vsce

# Package the extension
vsce package

# This creates memory-box-vscode-0.1.0.vsix

# Install locally
code --install-extension memory-box-vscode-0.1.0.vsix

# Or publish to marketplace
vsce publish
```

## Development

```bash
# Watch mode for development
npm run watch

# Then press F5 in VS Code to launch Extension Development Host
```

## Troubleshooting

### Bridge won't start

1. Check Python is in PATH: `which python`
2. Check Memory Box is installed: `pip list | grep memory-box`
3. Test bridge manually: `echo '{"method":"ping","params":{}}' | memory-box-bridge`

### Commands not being captured

1. **Check Shell Integration is enabled**: 
   - Open a terminal
   - Run a command
   - Look for the blue highlight when command finishes (indicates shell integration is working)
   
2. **Check terminal type**:
   - Shell integration works best with bash, zsh, powershell
   - May not work with cmd.exe or older shells

3. **Check extension logs**:
   - Open Output panel (`Cmd+Shift+U` / `Ctrl+Shift+U`)
   - Select "Memory Box" from dropdown
   - Look for "Captured command" messages

4. **Verify auto-capture is enabled**:
   - Open Command Palette
   - Run "Memory Box: Toggle Auto-Capture"
   - Check that it says "enabled"

### Connection errors

1. **Check bridge process is running**:
   ```bash
   # Test bridge manually
   echo '{"method": "ping", "params": {}}' | memory-box-bridge
   # Should output: {"result": "pong", "error": null}
   ```

2. **Check Memory Box is installed**:
   ```bash
   pip list | grep memory-box
   # Should show: memory-box X.X.X
   ```

3. **Check Python path**:
   - Open VS Code Settings
   - Search for "memoryBox.pythonPath"
   - Make sure it points to the right Python (e.g., `/usr/bin/python3`)

4. **Check extension host logs**:
   - Help → Toggle Developer Tools
   - Look in Console for errors

## Key Differences from Other Approaches

### ❌ **What We're NOT Doing**

- **Shell hooks** (modifying `.bashrc` / `.zshrc`) - Too invasive
- **PTY wrapper** - Complex and fragile
- **Polling terminals** - Unreliable and slow

### ✅ **What We ARE Doing**

- **VS Code's built-in Shell Integration API** - Clean, reliable, officially supported
- **Event-driven** - `onDidEndTerminalShellExecution` fires automatically
- **Per-workspace** - Only captures commands in VS Code integrated terminals
- **Zero configuration** - Works out of the box if shell integration is enabled

## Architecture

```
VS Code Terminal (bash/zsh/pwsh)
    ↓ (shell integration)
VS Code API: onDidEndTerminalShellExecution
    ↓ (event listener)
Extension: extension.ts
    ↓ (JSON over stdin/stdout)
MemoryBoxClient: memory-box-client.ts
    ↓ (spawns child process)
Python Bridge: memory-box-bridge
    ↓ (library API)
MemoryBox API: memory_box/api.py
    ↓
Neo4j Database
```

## Why This Approach Works

1. **VS Code does the hard part**: Shell integration handles PTY complexities
2. **Event-driven**: No polling, no hooks, no interception
3. **Reliable**: Works across all supported shells
4. **Context-aware**: Knows which workspace, which terminal
5. **Exit codes**: Can filter by success/failure
6. **Cross-platform**: Works on macOS, Linux, Windows (WSL/PowerShell)

## Next Steps

1. Build a complete VS Code extension
2. Add UI for browsing commands
3. Implement context-aware suggestions
4. Add command snippets/templates

## License

Same as Memory Box project
