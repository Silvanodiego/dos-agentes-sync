// No inference unless explicitly requested with --infer.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
const client = new Client({ name: 'verificacion-local', version: '1.0.0' });
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [fileURLToPath(new URL('./antigravity_mcp.mjs', import.meta.url))],
  stderr: 'inherit'
});
try {
  await client.connect(transport);
  const tools = await client.listTools();
  assert.deepEqual(tools.tools.map(t => t.name).sort(), ['antigravity_ask', 'antigravity_status']);
  console.log('MCP handshake y tools/list: OK');
  const status = await client.callTool({ name: 'antigravity_status', arguments: {} });
  assert.ok(!status.isError, JSON.stringify(status));
  assert.equal(JSON.parse(status.content[0].text).version, 4);
  console.log('MCP -> puente v4: OK');
  if (process.argv.includes('--infer')) {
    const marker = 'PUENTE_E2E_OK_' + new Date().toISOString().replace(/\D/g, '').slice(0, 14);
    const result = await client.callTool({
      name: 'antigravity_ask',
      arguments: { model: 'gemini-4-argon-high', prompt: `Prueba de conectividad. Responde exactamente con este texto, sin agregar nada: ${marker}` }
    }, undefined, { timeout: 85000 });
    assert.ok(!result.isError, JSON.stringify(result));
    const data = JSON.parse(result.content[0].text);
    assert.equal(data.status, 'ok');
    assert.equal(data.model, 'gemini-4-argon-high');
    assert.ok(data.response.includes(marker), data.response);
    assert.ok(data.request_id);
    console.log(JSON.stringify({ result: 'E2E OK', model: data.model, response: data.response, request_id: data.request_id }));
  }
} finally {
  await client.close();
}
