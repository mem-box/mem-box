import * as assert from 'assert';
import { EventEmitter } from 'events';
import * as proxyquire from 'proxyquire';
import type { MemoryBoxClient as MemoryBoxClientType } from '../client';

// Mock child process
class MockChildProcess extends EventEmitter {
    stdin = {
        write: (data: string, callback?: (error?: Error) => void) => {
            // Auto-respond to ping requests
            try {
                const request = JSON.parse(data);
                if (request.method === 'ping') {
                    setImmediate(() => {
                        this.stdout.emit('data', Buffer.from('{"result":"pong","error":null}\n'));
                    });
                }
            } catch {
                // Not JSON, ignore
            }
            if (callback) { callback(); }
            return true;
        }
    };
    stdout = new EventEmitter();
    stderr = new EventEmitter();
    kill() {
        // Simulate process exit when killed
        setImmediate(() => {
            this.emit('exit', 0, null);
        });
    }
}

describe('MemoryBoxClient', () => {
    let client: MemoryBoxClientType;
    let mockProcess: MockChildProcess;
    let MemoryBoxClient: typeof import('../client').MemoryBoxClient;

    beforeEach(() => {
        // Create mock process
        mockProcess = new MockChildProcess();

        // Use proxyquire to inject our mock
        const module = proxyquire.load('../client', {
            'child_process': {
                spawn: (command: string, args: string[]) => {
                    // Create a new mock process for each spawn call
                    const process = new MockChildProcess();

                    // Handle different spawn types
                    if (args && args.includes('-c') && args.includes('import server.bridge')) {
                        // isInstalled() check - simulate success
                        setImmediate(() => {
                            process.emit('exit', 0, null);
                        });
                    } else if (args && args.includes('pip')) {
                        // installPackage() - simulate success or skip
                        setImmediate(() => {
                            process.emit('exit', 0, null);
                        });
                    } else {
                        // Actual bridge process - use the shared mockProcess
                        return mockProcess;
                    }

                    return process;
                }
            }
        });

        MemoryBoxClient = module.MemoryBoxClient;
        client = new MemoryBoxClient();
    });

    afterEach(async () => {
        if (client) {
            await client.stop();
        }
    });

    describe('initialization', () => {
        it('should create a client instance', () => {
            assert.ok(client);
            assert.strictEqual(typeof client.addCommand, 'function');
            assert.strictEqual(typeof client.searchCommands, 'function');
            assert.strictEqual(typeof client.start, 'function');
            assert.strictEqual(typeof client.stop, 'function');
        });

        it('should initialize with default python path', () => {
            const client2 = new MemoryBoxClient();
            assert.ok(client2);
        });

        it('should accept custom python path', () => {
            const client2 = new MemoryBoxClient('/custom/python');
            assert.ok(client2);
        });
    });

    describe('lifecycle management', () => {
        it('should allow multiple stop calls without errors', async () => {
            await client.stop();
            await client.stop();
            await client.stop();
        });

        it('should handle stop before start', async () => {
            await client.stop();
        });
    });

    describe('concurrent operations', () => {
        beforeEach(async () => {
            await client.start();
        });

        it('should queue multiple commands being added at the same time', async () => {
            const promise1 = client.addCommand('cmd1');
            const promise2 = client.addCommand('cmd2');
            const promise3 = client.addCommand('cmd3');

            // Simulate responses in FIFO order
            setImmediate(() => {
                mockProcess.stdout.emit('data', Buffer.from('{"result":"id1","error":null}\n'));
                mockProcess.stdout.emit('data', Buffer.from('{"result":"id2","error":null}\n'));
                mockProcess.stdout.emit('data', Buffer.from('{"result":"id3","error":null}\n'));
            });

            const [id1, id2, id3] = await Promise.all([promise1, promise2, promise3]);
            assert.strictEqual(id1, 'id1');
            assert.strictEqual(id2, 'id2');
            assert.strictEqual(id3, 'id3');
        });

        it('should queue multiple searches happening at the same time', async () => {
            const promise1 = client.searchCommands('query1');
            const promise2 = client.searchCommands('query2');

            // Simulate responses in FIFO order
            setImmediate(() => {
                mockProcess.stdout.emit('data', Buffer.from('{"result":[{"id":"1","command":"test"}],"error":null}\n'));
                mockProcess.stdout.emit('data', Buffer.from('{"result":[{"id":"2","command":"test2"}],"error":null}\n'));
            });

            const [results1, results2] = await Promise.all([promise1, promise2]);
            assert.strictEqual(results1.length, 1);
            assert.strictEqual(results2.length, 1);
        });

        it('should successfully delete a command', async () => {
            const promise = client.deleteCommand('id1');

            mockProcess.stdout.emit('data', Buffer.from('{"result":true,"error":null}\n'));

            const result = await promise;
            assert.strictEqual(result, true);
        });

        it('should retrieve a specific command by ID', async () => {
            const promise = client.getCommand('id1');

            const cmd = { id: 'id1', command: 'test', description: 'desc' };
            mockProcess.stdout.emit('data', Buffer.from(`{"result":${JSON.stringify(cmd)},"error":null}\n`));

            const result = await promise;
            assert.ok(result);
            assert.strictEqual(result.id, 'id1');
            assert.strictEqual(result.command, 'test');
        });

        it('should reject with error message when bridge reports an error', async () => {
            const promise = client.addCommand('test');

            mockProcess.stdout.emit('data', Buffer.from('{"result":null,"error":"Database connection failed"}\n'));

            await assert.rejects(
                promise,
                (error: Error) => {
                    assert.strictEqual(error.message, 'Database connection failed');
                    return true;
                }
            );
        });
    });

    describe('adding commands with different parameters', () => {
        beforeEach(async () => {
            await client.start();
        });

        it('should send command text when adding a simple command', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.addCommand('echo test');
            mockProcess.stdout.emit('data', Buffer.from('{"result":"test-id","error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.strictEqual(request.method, 'add_command');
            assert.strictEqual(request.params.command, 'echo test');
        });

        it('should include description when provided', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.addCommand('echo test', 'Test description');
            mockProcess.stdout.emit('data', Buffer.from('{"result":"test-id","error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.strictEqual(request.params.command, 'echo test');
            assert.strictEqual(request.params.description, 'Test description');
        });

        it('should include tags, category, and context when provided', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.addCommand('echo test', 'Description', {
                tags: ['test'],
                category: 'testing',
                context: '/workspace'
            });
            mockProcess.stdout.emit('data', Buffer.from('{"result":"test-id","error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.deepStrictEqual(request.params.tags, ['test']);
            assert.strictEqual(request.params.category, 'testing');
            assert.strictEqual(request.params.context, '/workspace');
        });
    });

    describe('searching with different filters', () => {
        beforeEach(async () => {
            await client.start();
        });

        it('should send search query text', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.searchCommands('test query');
            mockProcess.stdout.emit('data', Buffer.from('{"result":[],"error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.strictEqual(request.method, 'search_commands');
            assert.strictEqual(request.params.query, 'test query');
        });

        it('should include tags, category, and limit when filtering', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.searchCommands('test', {
                tags: ['tag1'],
                category: 'cat1',
                limit: 10
            });
            mockProcess.stdout.emit('data', Buffer.from('{"result":[],"error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.deepStrictEqual(request.params.tags, ['tag1']);
            assert.strictEqual(request.params.category, 'cat1');
            assert.strictEqual(request.params.limit, 10);
        });
    });

    describe('deleting and retrieving commands', () => {
        beforeEach(async () => {
            await client.start();
        });

        it('should send command ID when deleting', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.deleteCommand('some-id');
            mockProcess.stdout.emit('data', Buffer.from('{"result":true,"error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.strictEqual(request.method, 'delete_command');
            assert.strictEqual(request.params.command_id, 'some-id');
        });

        it('should send command ID when retrieving', async () => {
            const writes: string[] = [];
            mockProcess.stdin.write = (data: string, callback?: (error?: Error) => void) => {
                writes.push(data);
                if (callback) { callback(); }
                return true;
            };

            const promise = client.getCommand('some-id');
            mockProcess.stdout.emit('data', Buffer.from('{"result":null,"error":null}\n'));
            await promise;

            const lastWrite = writes[writes.length - 1];
            const request = JSON.parse(lastWrite);
            assert.strictEqual(request.method, 'get_command');
            assert.strictEqual(request.params.command_id, 'some-id');
        });
    });

    describe('configuration handling', () => {
        it('should accept config object in start', async () => {
            await client.start({
                neo4jUri: 'bolt://localhost:7687',
                neo4jUser: 'neo4j',
                neo4jPassword: 'test'
            });
        });

        it('should allow start with partial config', async () => {
            await client.start({
                neo4jUri: 'bolt://localhost:7687'
            });
        });

        it('should allow start with no config', async () => {
            await client.start();
        });
    });
});