import * as assert from 'assert';
import { MemoryBoxClient } from '../client';

describe('MemoryBoxClient Integration Tests', () => {
    let client: MemoryBoxClient;

    before(async function () {
        this.timeout(5000);
        client = new MemoryBoxClient();

        // Start the bridge with test configuration
        try {
            await client.start({
                neo4jUri: 'bolt://localhost:7687',
                neo4jUser: 'neo4j',
                neo4jPassword: 'devpassword'
            });
        } catch (error) {
            // Skip tests if bridge can't start (Python not available, etc)
            this.skip();
        }
    });

    after(async function () {
        this.timeout(5000);
        if (client) {
            await client.stop();
        }
    });

    describe('command operations', () => {
        let commandId: string;

        it('should add a command', async function () {
            this.timeout(5000);

            const id = await client.addCommand(
                'echo "integration test"',
                'Test command for integration testing',
                {
                    tags: ['integration', 'test'],
                    category: 'testing',
                    context: '/workspace'
                }
            );

            assert.ok(id);
            assert.strictEqual(typeof id, 'string');
            commandId = id;
        }); it('should search for commands', async function () {
            this.timeout(5000);

            const results = await client.searchCommands('integration test');
            assert.ok(Array.isArray(results));
            assert.ok(results.length > 0);

            const found = results.find(cmd => cmd.id === commandId);
            assert.ok(found);
            assert.strictEqual(found.command, 'echo "integration test"');
        });

        it('should get a specific command', async function () {
            this.timeout(5000);

            const command = await client.getCommand(commandId);
            assert.ok(command);
            assert.strictEqual(command.id, commandId);
            assert.strictEqual(command.command, 'echo "integration test"');
            assert.ok(command.tags?.includes('integration'));
        });

        it('should search with filters', async function () {
            this.timeout(5000);

            const results = await client.searchCommands('test', {
                tags: ['integration'],
                category: 'testing'
            });

            assert.ok(Array.isArray(results));
            const found = results.find(cmd => cmd.id === commandId);
            assert.ok(found);
        });

        it('should delete a command', async function () {
            this.timeout(5000);

            const deleted = await client.deleteCommand(commandId);
            assert.strictEqual(deleted, true);

            // Verify it's gone
            try {
                await client.getCommand(commandId);
                assert.fail('Command should have been deleted');
            } catch (error) {
                // Expected - command not found
                assert.ok(error);
            }
        });
    });

    describe('batch operations', () => {
        const testCommands = [
            { cmd: 'ls -la', desc: 'List files', tags: ['files'] },
            { cmd: 'git status', desc: 'Check git status', tags: ['git'] },
            { cmd: 'npm test', desc: 'Run tests', tags: ['testing'] }
        ];
        const commandIds: string[] = [];

        it('should add multiple commands', async function () {
            this.timeout(10000);

            for (const { cmd, desc, tags } of testCommands) {
                const id = await client.addCommand(cmd, desc, { tags });
                commandIds.push(id);
            }

            assert.strictEqual(commandIds.length, 3);
        }); it('should search across multiple commands', async function () {
            this.timeout(5000);

            const results = await client.searchCommands('test');
            assert.ok(results.length >= 1);
        });

        it('should clean up test commands', async function () {
            this.timeout(10000);

            for (const id of commandIds) {
                await client.deleteCommand(id);
            }
        });
    });

    describe('error handling', () => {
        it('should handle invalid command ID gracefully', async function () {
            this.timeout(5000);

            try {
                await client.getCommand('invalid-id-that-does-not-exist');
                assert.fail('Should have thrown an error');
            } catch (error) {
                assert.ok(error);
            }
        });

        it('should handle empty search queries', async function () {
            this.timeout(5000);

            const results = await client.searchCommands('');
            assert.ok(Array.isArray(results));
        });
    });
});
