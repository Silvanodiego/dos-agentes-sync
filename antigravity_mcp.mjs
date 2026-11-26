// Codex stdio MCP -> authenticated local bridge -> Antigravity Manager.
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import * as z from 'zod/v4';
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFile } from 'node:child_process';

const bridge = 'http://127.0.0.1:8765';
const models = ['gemini-4-argon-high', 'claude-sonnet-5-5-high', 'claude-opus-5-5-high'];
export const server = new McpServer({ name: 'antigravity-bridge', version: '1.0.0' }, {
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


const root = String.raw`C:\dos_agentes_local`;

// El prompt viaja por stdin, nunca en argumentos de proceso ni por un shell.
export function runLocal(file, args, { input = '', timeout = 200000 } = {}) {
  return new Promise((resolveResult, reject) => {
    const child = execFile(file, args, {
      cwd: root, windowsHide: true, timeout, killSignal: 'SIGKILL',
      encoding: 'utf8', maxBuffer: 4 * 1024 * 1024,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
    }, (error, stdout, stderr) => {
      if (error) {
        // Conservar la salida original; no usar error.message, que incluye argv.
        const failure = new Error(error.killed
          ? `Timeout: proceso terminado tras ${timeout / 1000} segundos${stderr.trim() ? '\n' + stderr.trim() : ''}`
          : stderr.trim() || stdout.trim() || error.message);
        failure.code = error.code;
        reject(failure);
      } else resolveResult(stdout.trim());
    });
    child.stdin.on('error', () => {}); // execFile informa tambien los fallos de inicio.
    child.stdin.end(input, 'utf8');
  });
}

function cdpConnectionFailure(error) {
  const text = error.message;
  if (/authentic|credencial|iniciar sesi[oó]n|unauthorized|forbidden|401|403/i.test(text)) return false;
  return /CDP[^\n]*(?:9222|conectar)|(?:connect|ECONNREFUSED|ECONNRESET)[^\n]*9222/i.test(text);
}

export async function geminiAsk(prompt, run = runLocal) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await run(join(root, '.venv', 'Scripts', 'python.exe'),
        [join(root, 'chat_fijo_gemini.py'), '--project', 'DOS_AGENTES', '--timeout', '180', '--limpiar-borrador'],
        { input: prompt, timeout: 200000 });
      if (!response.trim()) throw new Error('Gemini devolvio una respuesta vacia.');
      return { content: [{ type: 'text', text: response.trim() }] };
    } catch (error) {
      if (attempt === 0 && cdpConnectionFailure(error)) {
        try {
          await run('powershell.exe', ['-NoProfile', '-WindowStyle', 'Hidden',
            '-ExecutionPolicy', 'Bypass', '-File', join(root, 'scripts', 'verificar_flujo_10m.ps1')],
            { timeout: 90000 });
        } catch {
          // Aun si el verificador devuelve fallo, realizar el unico reintento solicitado.
        }
        continue;
      }
      return { content: [{ type: 'text', text: error.message }], isError: true };
    }
  }
}

server.registerTool('gemini_ask', {
  description: 'Consulta el Chat Fijo Gemini de DOS_AGENTES via CDP 9222. Devuelve texto limpio; recupera y reintenta una vez solo ante fallo de conexion CDP. Cada proceso tiene timeout de 200 segundos.',
  inputSchema: { prompt: z.string().min(1).describe('Consulta sin credenciales para el chat fijo Gemini.') },
  annotations: { readOnlyHint: false, openWorldHint: true }
}, async ({ prompt }) => geminiAsk(prompt));

// Permite importar el mismo servidor en pruebas sin abrir stdio.
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  await server.connect(new StdioServerTransport());
}
