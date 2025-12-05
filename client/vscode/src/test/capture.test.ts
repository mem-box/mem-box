import * as assert from 'assert';
import { captureCommands, OperationQueue, processTerminalExecution, queueCapture, splitCommands } from '../capture';

describe('Capture Logic', () => {
    describe('Command splitting', () => {
        it('should return single command as-is', () => {
            const result = splitCommands('docker ps');
            assert.strictEqual(result.length, 1);
            assert.strictEqual(result[0], 'docker ps');
        });

        it('should trim whitespace', () => {
            const result = splitCommands('  docker ps  ');
            assert.strictEqual(result.length, 1);
            assert.strictEqual(result[0], 'docker ps');
        });
    });

    describe('Newline separation', () => {
        it('should split by newlines', () => {
            const result = splitCommands('docker ps\ndocker images\nls -la');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'docker ps');
            assert.strictEqual(result[1], 'docker images');
            assert.strictEqual(result[2], 'ls -la');
        });

        it('should handle empty lines', () => {
            const result = splitCommands('docker ps\n\ndocker images');
            assert.strictEqual(result.length, 2);
            assert.strictEqual(result[0], 'docker ps');
            assert.strictEqual(result[1], 'docker images');
        });
    });

    describe('Shell separator: ||', () => {
        it('should split by ||', () => {
            const result = splitCommands('command1 || command2');
            assert.strictEqual(result.length, 2);
            assert.strictEqual(result[0], 'command1');
            assert.strictEqual(result[1], 'command2');
        });

        it('should handle multiple ||', () => {
            const result = splitCommands('cmd1 || cmd2 || cmd3');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'cmd1');
            assert.strictEqual(result[1], 'cmd2');
            assert.strictEqual(result[2], 'cmd3');
        });
    });

    describe('Shell separator: &&', () => {
        it('should split by &&', () => {
            const result = splitCommands('git add . && git commit -m "msg"');
            assert.strictEqual(result.length, 2);
            assert.strictEqual(result[0], 'git add .');
            assert.strictEqual(result[1], 'git commit -m "msg"');
        });

        it('should handle multiple &&', () => {
            const result = splitCommands('cd dir && npm install && npm test');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'cd dir');
            assert.strictEqual(result[1], 'npm install');
            assert.strictEqual(result[2], 'npm test');
        });
    });

    describe('Shell separator: ;', () => {
        it('should split by semicolon', () => {
            const result = splitCommands('echo hello; echo world');
            assert.strictEqual(result.length, 2);
            assert.strictEqual(result[0], 'echo hello');
            assert.strictEqual(result[1], 'echo world');
        });

        it('should handle multiple semicolons', () => {
            const result = splitCommands('cmd1; cmd2; cmd3');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'cmd1');
            assert.strictEqual(result[1], 'cmd2');
            assert.strictEqual(result[2], 'cmd3');
        });
    });

    describe('Mixed separators', () => {
        it('should handle mix of && and ||', () => {
            const result = splitCommands('cmd1 && cmd2 || cmd3');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'cmd1');
            assert.strictEqual(result[1], 'cmd2');
            assert.strictEqual(result[2], 'cmd3');
        });

        it('should handle mix of all separators', () => {
            const result = splitCommands('cmd1 && cmd2 || cmd3; cmd4');
            assert.strictEqual(result.length, 4);
            assert.strictEqual(result[0], 'cmd1');
            assert.strictEqual(result[1], 'cmd2');
            assert.strictEqual(result[2], 'cmd3');
            assert.strictEqual(result[3], 'cmd4');
        });

        it('should handle newlines with shell separators', () => {
            const result = splitCommands('cmd1 && cmd2\ncmd3 || cmd4');
            assert.strictEqual(result.length, 4);
            assert.strictEqual(result[0], 'cmd1');
            assert.strictEqual(result[1], 'cmd2');
            assert.strictEqual(result[2], 'cmd3');
            assert.strictEqual(result[3], 'cmd4');
        });
    });

    describe('Real-world examples', () => {
        it('should handle docker multi-paste', () => {
            const input = `docker ps
docker ps -a
docker images
docker network ls`;
            const result = splitCommands(input);
            assert.strictEqual(result.length, 4);
            assert.strictEqual(result[0], 'docker ps');
            assert.strictEqual(result[1], 'docker ps -a');
            assert.strictEqual(result[2], 'docker images');
            assert.strictEqual(result[3], 'docker network ls');
        });

        it('should handle build chain', () => {
            const result = splitCommands('npm install && npm run build && npm test');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'npm install');
            assert.strictEqual(result[1], 'npm run build');
            assert.strictEqual(result[2], 'npm test');
        });

        it('should handle fallback pattern', () => {
            const result = splitCommands('command1 || command2 || echo "all failed"');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'command1');
            assert.strictEqual(result[1], 'command2');
            assert.strictEqual(result[2], 'echo "all failed"');
        });

        it('should handle complex shell script', () => {
            const input = `cd /workspace && npm install
npm test || echo "tests failed"
docker build -t myapp .; docker run myapp`;
            const result = splitCommands(input);
            assert.strictEqual(result.length, 6);
            assert.strictEqual(result[0], 'cd /workspace');
            assert.strictEqual(result[1], 'npm install');
            assert.strictEqual(result[2], 'npm test');
            assert.strictEqual(result[3], 'echo "tests failed"');
            assert.strictEqual(result[4], 'docker build -t myapp .');
            assert.strictEqual(result[5], 'docker run myapp');
        });
    });

    describe('Edge cases', () => {
        it('should handle empty string', () => {
            const result = splitCommands('');
            assert.strictEqual(result.length, 0);
        });

        it('should handle only whitespace', () => {
            const result = splitCommands('   \n\n   ');
            assert.strictEqual(result.length, 0);
        });

        it('should handle only separators', () => {
            const result = splitCommands('&& || ;');
            assert.strictEqual(result.length, 0);
        });

        it('should handle commands with extra spaces around separators', () => {
            const result = splitCommands('cmd1  &&  cmd2  ||  cmd3');
            assert.strictEqual(result.length, 3);
            assert.strictEqual(result[0], 'cmd1');
            assert.strictEqual(result[1], 'cmd2');
            assert.strictEqual(result[2], 'cmd3');
        });
    });

    describe('Parallel command capture', () => {
        it('should call addCommand for each command in parallel', async () => {
            const capturedCommands: Array<{ cmd: string; desc: string; opts: { context?: string; status: string } }> = [];

            // Mock client
            const mockClient = {
                addCommand: async (cmd: string, desc: string, opts: { context?: string; status: string }) => {
                    capturedCommands.push({ cmd, desc, opts });
                    return 'mock-id';
                }
            };

            const commands = ['cmd1', 'cmd2', 'cmd3'];
            const options = { context: '/workspace', status: 'success' };

            await captureCommands(mockClient as never, commands, options);

            // Verify all commands were captured
            assert.strictEqual(capturedCommands.length, 3);
            assert.strictEqual(capturedCommands[0].cmd, 'cmd1');
            assert.strictEqual(capturedCommands[1].cmd, 'cmd2');
            assert.strictEqual(capturedCommands[2].cmd, 'cmd3');

            // Verify options were passed
            assert.strictEqual(capturedCommands[0].opts.context, '/workspace');
            assert.strictEqual(capturedCommands[0].opts.status, 'success');
        });

        it('should not throw when individual commands fail', async () => {
            let callCount = 0;

            const mockClient = {
                addCommand: async (cmd: string) => {
                    callCount++;
                    if (cmd === 'cmd2') {
                        throw new Error('Failed to add command');
                    }
                    return 'mock-id';
                }
            };

            const commands = ['cmd1', 'cmd2', 'cmd3'];

            // Should not throw despite cmd2 failing
            await captureCommands(mockClient as never, commands, { status: 'success' });

            // All three commands should have been attempted
            assert.strictEqual(callCount, 3);
        });
    });

    describe('Terminal execution processing', () => {
        it('should return null for empty command line', () => {
            const result = processTerminalExecution('', 0, '/workspace', false);
            assert.strictEqual(result, null);
        });

        it('should return null for whitespace-only command line', () => {
            const result = processTerminalExecution('   \n  ', 0, '/workspace', false);
            assert.strictEqual(result, null);
        });

        it('should return null for failed command when captureSuccessOnly is true', () => {
            const result = processTerminalExecution('docker ps', 1, '/workspace', true);
            assert.strictEqual(result, null);
        });

        it('should process failed command when captureSuccessOnly is false', () => {
            const result = processTerminalExecution('docker ps', 1, '/workspace', false);
            assert.ok(result);
            assert.strictEqual(result!.commands.length, 1);
            assert.strictEqual(result!.commands[0], 'docker ps');
            assert.strictEqual(result!.options.status, 'failed');
            assert.strictEqual(result!.options.context, '/workspace');
        });

        it('should process successful command with success status', () => {
            const result = processTerminalExecution('docker ps', 0, '/workspace', false);
            assert.ok(result);
            assert.strictEqual(result!.commands.length, 1);
            assert.strictEqual(result!.commands[0], 'docker ps');
            assert.strictEqual(result!.options.status, 'success');
        });

        it('should split multi-line commands', () => {
            const input = 'docker ps\ndocker images\nls -la';
            const result = processTerminalExecution(input, 0, '/workspace', false);
            assert.ok(result);
            assert.strictEqual(result!.commands.length, 3);
            assert.strictEqual(result!.commands[0], 'docker ps');
            assert.strictEqual(result!.commands[1], 'docker images');
            assert.strictEqual(result!.commands[2], 'ls -la');
        });

        it('should split commands with shell separators', () => {
            const input = 'npm install && npm test || echo failed';
            const result = processTerminalExecution(input, 0, '/workspace', false);
            assert.ok(result);
            assert.strictEqual(result!.commands.length, 3);
            assert.strictEqual(result!.commands[0], 'npm install');
            assert.strictEqual(result!.commands[1], 'npm test');
            assert.strictEqual(result!.commands[2], 'echo failed');
        });

        it('should handle undefined workspace context', () => {
            const result = processTerminalExecution('ls', 0, undefined, false);
            assert.ok(result);
            assert.strictEqual(result!.options.context, undefined);
        });

        it('should handle undefined exit code as failed', () => {
            const result = processTerminalExecution('ls', undefined, '/workspace', false);
            assert.ok(result);
            assert.strictEqual(result!.options.status, 'failed');
        });
    });

    describe('OperationQueue', () => {
        it('should execute operations sequentially', async () => {
            const queue = new OperationQueue();
            const executionOrder: number[] = [];

            // Enqueue 3 operations
            queue.enqueue(async () => {
                await new Promise(resolve => setTimeout(resolve, 10));
                executionOrder.push(1);
            });
            queue.enqueue(async () => {
                await new Promise(resolve => setTimeout(resolve, 5));
                executionOrder.push(2);
            });
            queue.enqueue(async () => {
                executionOrder.push(3);
            });

            // Wait a bit for all to complete
            await new Promise(resolve => setTimeout(resolve, 50));

            // Should execute in order
            assert.deepStrictEqual(executionOrder, [1, 2, 3]);
        });

        it('should not block queue when an operation fails', async () => {
            const queue = new OperationQueue();
            const executionOrder: number[] = [];

            queue.enqueue(async () => {
                executionOrder.push(1);
            });
            queue.enqueue(async () => {
                executionOrder.push(2);
                throw new Error('Operation failed');
            });
            queue.enqueue(async () => {
                executionOrder.push(3);
            });

            await new Promise(resolve => setTimeout(resolve, 50));

            // All three should execute despite #2 throwing
            assert.deepStrictEqual(executionOrder, [1, 2, 3]);
        });

        it('should handle rapid enqueues', async () => {
            const queue = new OperationQueue();
            const count = { value: 0 };

            // Rapidly enqueue 10 operations
            for (let i = 0; i < 10; i++) {
                queue.enqueue(async () => {
                    count.value++;
                });
            }

            await new Promise(resolve => setTimeout(resolve, 50));

            assert.strictEqual(count.value, 10);
        });
    });

    describe('Queue capture integration', () => {
        it('should queue capture with valid client and result', async () => {
            const queue = new OperationQueue();
            const capturedCommands: string[] = [];

            const mockClient = {
                addCommand: async (cmd: string) => {
                    capturedCommands.push(cmd);
                    return 'mock-id';
                }
            };

            const result = {
                commands: ['cmd1', 'cmd2'],
                options: { context: '/workspace', status: 'success' as const }
            };

            queueCapture(queue, mockClient as never, result);

            await new Promise(resolve => setTimeout(resolve, 50));

            assert.strictEqual(capturedCommands.length, 2);
            assert.strictEqual(capturedCommands[0], 'cmd1');
            assert.strictEqual(capturedCommands[1], 'cmd2');
        });

        it('should handle undefined client gracefully', async () => {
            const queue = new OperationQueue();

            const result = {
                commands: ['cmd1'],
                options: { status: 'success' as const }
            };

            // Should not throw
            queueCapture(queue, undefined, result);

            await new Promise(resolve => setTimeout(resolve, 50));
            // Test passes if no error thrown
        });

        it('should handle many rapid queue captures', async () => {
            const queue = new OperationQueue();
            const capturedCommands: string[] = [];

            const mockClient = {
                addCommand: async (cmd: string) => {
                    await new Promise(resolve => setTimeout(resolve, 1));
                    capturedCommands.push(cmd);
                    return 'mock-id';
                }
            };

            // Simulate 20 rapid terminal executions with multiple commands each
            for (let i = 0; i < 20; i++) {
                const result = {
                    commands: [`batch${i}-cmd1`, `batch${i}-cmd2`, `batch${i}-cmd3`],
                    options: { context: '/workspace', status: 'success' as const }
                };
                queueCapture(queue, mockClient as never, result);
            }

            await new Promise(resolve => setTimeout(resolve, 200));

            // Should capture all 60 commands (20 batches × 3 commands)
            assert.strictEqual(capturedCommands.length, 60);

            // Verify first and last batches
            assert.strictEqual(capturedCommands[0], 'batch0-cmd1');
            assert.strictEqual(capturedCommands[1], 'batch0-cmd2');
            assert.strictEqual(capturedCommands[2], 'batch0-cmd3');
            assert.strictEqual(capturedCommands[57], 'batch19-cmd1');
            assert.strictEqual(capturedCommands[58], 'batch19-cmd2');
            assert.strictEqual(capturedCommands[59], 'batch19-cmd3');
        });

        it('should handle mixed success and failure commands', async () => {
            const queue = new OperationQueue();
            const results: Array<{ cmd: string; status: string }> = [];

            const mockClient = {
                addCommand: async (cmd: string, desc: string, opts: { status: string }) => {
                    results.push({ cmd, status: opts.status });
                    return 'mock-id';
                }
            };

            // Queue multiple captures with different statuses
            queueCapture(queue, mockClient as never, {
                commands: ['success1', 'success2'],
                options: { status: 'success' }
            });

            queueCapture(queue, mockClient as never, {
                commands: ['failed1', 'failed2', 'failed3'],
                options: { status: 'failed' }
            });

            queueCapture(queue, mockClient as never, {
                commands: ['success3'],
                options: { status: 'success' }
            });

            await new Promise(resolve => setTimeout(resolve, 100));

            assert.strictEqual(results.length, 6);
            assert.strictEqual(results[0].cmd, 'success1');
            assert.strictEqual(results[0].status, 'success');
            assert.strictEqual(results[2].cmd, 'failed1');
            assert.strictEqual(results[2].status, 'failed');
            assert.strictEqual(results[5].cmd, 'success3');
            assert.strictEqual(results[5].status, 'success');
        });
    });
});
