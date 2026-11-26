import test from 'node:test';
import assert from 'node:assert/strict';
import { geminiAsk, runLocal } from '../antigravity_mcp.mjs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const failure = 'ERROR_CHAT_FIJO: CDP 127.0.0.1:9222 no responde.';
function runner(results) {
  const calls = [];
  const run = async (...args) => {
    calls.push(args);
    const value = results.shift();
    if (value instanceof Error) throw value;
    return value;
  };
  return { run, calls };
}
test('respuesta limpia, CLI real, stdin UTF-8 y timeout de 200 segundos', async () => {
  const { run, calls } = runner(['  CONEXION_OK\n']);
  assert.deepEqual(await geminiAsk('Consulta ñ', run), {content:[{type:'text',text:'CONEXION_OK'}]});
  assert.equal(calls[0][0], String.raw`C:\dos_agentes_local\.venv\Scripts\python.exe`);
  assert.deepEqual(calls[0][1], [String.raw`C:\dos_agentes_local\chat_fijo_gemini.py`, '--project', 'DOS_AGENTES', '--timeout', '180', '--limpiar-borrador']);
  assert.deepEqual(calls[0][2], {input:'Consulta ñ',timeout:200000});
});
test('fallo CDP ejecuta verificador una vez y reintenta', async () => {
  const { run, calls } = runner([new Error(failure), 'OK', 'Recuperado']);
  assert.equal((await geminiAsk('p', run)).content[0].text, 'Recuperado');
  assert.equal(calls.length, 3);
  assert.equal(calls[1][0], 'powershell.exe');
  assert.equal(calls[1][1].at(-1), String.raw`C:\dos_agentes_local\scripts\verificar_flujo_10m.ps1`);
  assert.equal(calls[1][2].timeout, 90000);
});
test('segundo fallo devuelve error exacto sin otro intento aunque falle verificador', async () => {
  const { run, calls } = runner([new Error(failure), new Error('verificador fallo'), new Error(failure)]);
  assert.deepEqual(await geminiAsk('p', run), {content:[{type:'text',text:failure}],isError:true});
  assert.equal(calls.length, 3);
});
for (const message of ['Falta iniciar sesión de Google en CDP 9222', 'Tiempo agotado esperando respuesta de Gemini', 'ERROR_CHAT_FIJO: otro error']) {
  test(`no reenvia por ${message}`, async () => {
    const {run,calls} = runner([new Error(message)]);
    assert.deepEqual(await geminiAsk('p',run), {content:[{type:'text',text:message}],isError:true});
    assert.equal(calls.length,1);
  });
}
test('respuesta vacia es un error sin reenvio', async () => {
  const {run,calls}=runner(['   ']);
  assert.equal((await geminiAsk('p',run)).isError,true);
  assert.equal(calls.length,1);
});
test('subproceso real conserva stdin UTF-8 sin shell', async () => {
  const text='á ñ " & |';
  assert.equal(await runLocal(process.execPath,['-e',"process.stdin.setEncoding('utf8'); process.stdin.pipe(process.stdout)"],{input:text,timeout:5000}),text);
});
test('subproceso real termina por timeout', async () => {
  await assert.rejects(runLocal(process.execPath,['-e','setInterval(()=>{},1000)'],{timeout:100}), /Timeout/);
});
test('MCP stdio publica los dos contratos existentes y gemini_ask', async () => {
  const transport=new StdioClientTransport({command:process.execPath,args:['antigravity_mcp.mjs'],cwd:String.raw`C:\dos_agentes_local`});
  const client=new Client({name:'gemini-test',version:'1.0.0'});
  try {
    await client.connect(transport);
    const {tools}=await client.listTools();
    assert.deepEqual(tools.map(t=>t.name).sort(),['antigravity_ask','antigravity_status','gemini_ask']);
    const tool=tools.find(t=>t.name==='gemini_ask');
    assert.equal(tool.inputSchema.properties.prompt.type,'string');
    assert.deepEqual(tool.inputSchema.required,['prompt']);
  } finally { await client.close(); }
});
