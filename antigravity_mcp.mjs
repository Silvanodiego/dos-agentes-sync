// Codex stdio MCP -> authenticated local bridge -> Antigravity Manager.
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import * as z from 'zod/v4';
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

const bridge = 'http://127.0.0.1:8765';
const models = ['gemini-4-argon-high', 'claude-sonnet-5-5-high', 'claude-opus-5-5-high'];
const server = new McpServer({ name: 'antigravity-bridge', version: '1.0.0' }, {
  instructions: 'Delegate suitable analysis, research and reviews with antigravity_ask. It sends the supplied prompt to Antigravity through the local bridge. Gemini Argon is the default. Validate results locally; do not send secrets. Do not retry failed inference automatically.'
});

async function request(path, body) {
  const headers = {};
  if (body !== undefined) {
    const token = (await readFile(join(homedir(), '.antigravity-agent', 'local_bridge_token'), 'utf8')).trim();
    if (!token) throw new Error('Missing local bridge token');
    headers.Authorization = `Bearer ${token}`;
    headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(bridge + path, {
    method: body === undefined ? 'GET' : 'POST', headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(body === undefined ? 5000 : 75000)
  });
  const result = await response.json();
  if (!response.ok || result.status === 'error') {
    throw new Error(`Bridge HTTP ${response.status}: ${JSON.stringify(result)}`);
  }
  return result;
}

const output = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }] });
server.registerTool('antigravity_status', {
  description: 'Check the local Antigravity bridge without performing model inference.',
  inputSchema: {},
  annotations: { readOnlyHint: true, openWorldHint: false }
}, async () => {
  try { return output(await request('/')); }
  catch (error) { return { ...output({ error: error.message }), isError: true }; }
});
server.registerTool('antigravity_ask', {
  description: 'Delegate a task to Antigravity via the authenticated bridge on 8765 and proxy on 8045. Only the supplied prompt is sent; no files are read automatically. Returns the model response and the request ID recorded in the bridge log.',
  inputSchema: {
    prompt: z.string().min(1).max(30000).describe('Self-contained task and necessary context, without credentials.'),
    model: z.enum(models).default('gemini-4-argon-high')
  },
  annotations: { readOnlyHint: true, openWorldHint: true }
}, async ({ prompt, model }) => {
  try { return output(await request('/ask', { prompt, model })); }
  catch (error) { return { ...output({ error: error.message }), isError: true }; }
});

await server.connect(new StdioServerTransport());
