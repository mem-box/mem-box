import * as vscode from 'vscode';
import {
    OperationQueue,
    processTerminalExecution,
    queueCapture
} from './capture';
import { MemoryBoxClient } from './client';

let memBoxClient: MemoryBoxClient | undefined;
let autoCapture = true;

const captureQueue = new OperationQueue();

export function activate(context: vscode.ExtensionContext) {
    // Load config
    const config = vscode.workspace.getConfiguration('memBox');

    // Initialize Mem Box client
    memBoxClient = new MemoryBoxClient();

    // Get DB config from settings
    const neo4jUri = config.get<string>('neo4jUri');
    const neo4jUser = config.get<string>('neo4jUser');
    const neo4jPassword = config.get<string>('neo4jPassword');

    const dbConfig = {
        neo4jUri: neo4jUri || undefined,
        neo4jUser: neo4jUser || undefined,
        neo4jPassword: neo4jPassword || undefined
    };

    // Start the bridge process with config
    memBoxClient.start(dbConfig).catch((err) => {
        console.error('Failed to start Mem Box bridge:', err);
        vscode.window.showErrorMessage(
            'Mem Box: Failed to start. Make sure mem-box is installed (pip install mem-box)'
        );
    });

    // Load auto-capture setting
    autoCapture = config.get('autoCapture', true);

    // Register terminal execution listener for auto-capture
    const executionListener = vscode.window.onDidEndTerminalShellExecution(async (event) => {
        if (!autoCapture || !memBoxClient) {
            return;
        }

        const commandLine = event.execution.commandLine.value;
        const exitCode = event.exitCode;
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        const captureSuccessOnly = vscode.workspace.getConfiguration('memoryBox').get('captureExitCodeZeroOnly', false);

        // Process the execution event
        const result = processTerminalExecution(
            commandLine,
            exitCode,
            workspaceFolder?.uri.fsPath,
            captureSuccessOnly
        );

        if (!result) {
            return;
        }

        // Queue the capture to avoid overwhelming the system
        queueCapture(captureQueue, memBoxClient, result);
    });

    // Register search command
    const searchCommand = vscode.commands.registerCommand(
        'memBox.searchCommands',
        async () => {
            if (!memBoxClient) {
                vscode.window.showErrorMessage('Mem Box is not initialized');
                return;
            }

            const query = await vscode.window.showInputBox({
                prompt: 'Search for commands',
                placeHolder: 'e.g., docker, git commit, npm install'
            });

            if (!query) {
                return;
            }

            try {
                const results = await memBoxClient.searchCommands(query, {
                    fuzzy: true,
                    limit: 20
                });

                if (results.length === 0) {
                    vscode.window.showInformationMessage('No commands found');
                    return;
                }

                // Show results in Quick Pick
                const items = results.map(cmd => ({
                    label: cmd.command,
                    description: cmd.description || '',
                    detail: `Used ${cmd.use_count} times | ${cmd.created_at}`,
                    command: cmd
                }));

                const selected = await vscode.window.showQuickPick(items, {
                    placeHolder: 'Select a command to copy or insert',
                    matchOnDescription: true,
                    matchOnDetail: true
                });

                if (selected) {
                    // Ask what to do with the selected command
                    const action = await vscode.window.showQuickPick([
                        { label: 'Copy to Clipboard', value: 'copy' },
                        { label: 'Insert into Active Terminal', value: 'insert' },
                        { label: 'Create New Terminal and Run', value: 'run' }
                    ], {
                        placeHolder: 'What would you like to do?'
                    });

                    if (action) {
                        switch (action.value) {
                            case 'copy':
                                await vscode.env.clipboard.writeText(selected.label);
                                vscode.window.showInformationMessage('Command copied to clipboard');
                                break;

                            case 'insert': {
                                const activeTerminal = vscode.window.activeTerminal;
                                if (activeTerminal) {
                                    activeTerminal.sendText(selected.label, false);
                                } else {
                                    vscode.window.showWarningMessage('No active terminal');
                                }
                                break;
                            }

                            case 'run': {
                                const newTerminal = vscode.window.createTerminal('Mem Box');
                                newTerminal.show();
                                newTerminal.sendText(selected.label);
                                break;
                            }
                        }
                    }
                }
            } catch (err) {
                vscode.window.showErrorMessage(`Search failed: ${err}`);
            }
        }
    );

    // Register manual add command
    const addCommand = vscode.commands.registerCommand(
        'memBox.addCommand',
        async () => {
            if (!memBoxClient) {
                vscode.window.showErrorMessage('Mem Box is not initialized');
                return;
            }

            const command = await vscode.window.showInputBox({
                prompt: 'Enter the command',
                placeHolder: 'e.g., docker ps -a'
            });

            if (!command) {
                return;
            }

            const description = await vscode.window.showInputBox({
                prompt: 'Enter a description (optional)',
                placeHolder: 'e.g., List all containers including stopped ones'
            });

            const tagsInput = await vscode.window.showInputBox({
                prompt: 'Enter tags, comma-separated (optional)',
                placeHolder: 'e.g., docker, containers'
            });

            const tags = tagsInput
                ? tagsInput.split(',').map(t => t.trim()).filter(t => t.length > 0)
                : undefined;

            try {
                const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
                const commandId = await memBoxClient.addCommand(command, description || '', {
                    tags,
                    context: workspaceFolder?.uri.fsPath
                });

                vscode.window.showInformationMessage(`Command added: ${commandId}`);
            } catch (err) {
                vscode.window.showErrorMessage(`Failed to add command: ${err}`);
            }
        }
    );

    // Register toggle auto-capture command
    const toggleCommand = vscode.commands.registerCommand(
        'memBox.toggleAutoCapture',
        async () => {
            autoCapture = !autoCapture;

            // Update configuration
            await config.update('autoCapture', autoCapture, vscode.ConfigurationTarget.Global);

            const status = autoCapture ? 'enabled' : 'disabled';
            vscode.window.showInformationMessage(`Mem Box auto-capture ${status}`);
        }
    );

    // Register all disposables
    context.subscriptions.push(
        executionListener,
        searchCommand,
        addCommand,
        toggleCommand,
        {
            dispose: () => {
                if (memBoxClient) {
                    memBoxClient.stop();
                }
            }
        }
    );
}

export function deactivate() {
    if (memBoxClient) {
        memBoxClient.stop();
    }
}
