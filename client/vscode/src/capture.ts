import { MemoryBoxClient } from './client';

/**
 * Manages a queue of async operations to prevent overwhelming the system
 */
export class OperationQueue {
    private queue: Promise<void> = Promise.resolve();

    /**
     * Add an operation to the queue
     */
    enqueue(operation: () => Promise<void>): void {
        this.queue = this.queue.then(operation).catch(() => {
            // Silently catch errors to prevent queue from breaking
        });
    }
}

/**
 * Split a command line into individual commands by newlines and shell separators
 */
export function splitCommands(commandLine: string): string[] {
    const commands: string[] = [];
    commandLine.split('\n').forEach(line => {
        const parts = line.split(/\|\||&&|;/);
        parts.forEach(cmd => {
            const trimmed = cmd.trim();
            if (trimmed.length > 0) {
                commands.push(trimmed);
            }
        });
    });
    return commands;
}

/**
 * Capture multiple commands in parallel
 */
export async function captureCommands(
    client: MemoryBoxClient,
    commands: string[],
    options: { context?: string; status: string }
): Promise<void> {
    await Promise.allSettled(
        commands.map(cmd =>
            client.addCommand(cmd, '', options)
        )
    );
}

/**
 * Process a terminal execution event and return the commands to capture
 * Returns null if the event should be skipped
 */
export function processTerminalExecution(
    commandLine: string,
    exitCode: number | undefined,
    workspaceContext: string | undefined,
    captureSuccessOnly: boolean
): { commands: string[]; options: { context?: string; status: string } } | null {
    // Skip if command is empty
    if (!commandLine || commandLine.trim().length === 0) {
        return null;
    }

    // Check if we should only capture successful commands
    if (captureSuccessOnly && exitCode !== 0) {
        return null;
    }

    // Determine status from exit code
    const status = exitCode === 0 ? 'success' : 'failed';

    // Split into individual commands
    const commands = splitCommands(commandLine);

    return {
        commands,
        options: {
            context: workspaceContext,
            status
        }
    };
}

/**
 * Queue a capture operation for a terminal execution result
 */
export function queueCapture(
    queue: OperationQueue,
    client: MemoryBoxClient | undefined,
    result: { commands: string[]; options: { context?: string; status: string } }
): void {
    queue.enqueue(async () => {
        if (!client) {
            return;
        }

        await captureCommands(client, result.commands, result.options);
    });
}
