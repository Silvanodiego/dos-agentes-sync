import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { auditedCall, newCallId, writeAudit, geminiAsk } from '../antigravity_mcp.mjs';

for (const [tool, prefix] of [['antigravity_ask','AG'], ['gemini_ask','GEM']]) {
  test(`${tool}: ID y auditoria OK con mock`, async () => {
    let entry;
    const result = await auditedCall(tool, async () => ({content:[{type:'text',text:'Resultado'}]}), async value => { entry=value; });
    assert.match(entry.callId, new RegExp(`^${prefix}-\\d{6}-[0-9A-F]{4}$`));
    assert.equal(result.content.at(-1).text, `[MCP_CALL_ID: ${entry.callId}]`);
    assert.equal(entry.status, 'OK');
    assert.equal(entry.tool, tool);
    assert.ok(Number.isInteger(entry.duration) && entry.duration >= 0);
    assert.ok(entry.date instanceof Date);
  });
}
test('reloj local y cuatro digitos hex aleatorios', () => {
  assert.match(newCallId('antigravity_ask', new Date(2026,10,27,1,2,3)), /^AG-010203-[0-9A-F]{4}$/);
});
test('errores devueltos y excepciones conservan firma y estado ERROR', async () => {
  for (const operation of [async()=>({content:[{type:'text',text:'fallo'}],isError:true}), async()=>{throw new Error('fallo');}]) {
    let entry;
    const result = await auditedCall('gemini_ask', operation, async value=>{entry=value;});
    assert.equal(result.isError,true);
    assert.equal(entry.status,'ERROR');
    assert.equal(result.content.at(-1).text,`[MCP_CALL_ID: ${entry.callId}]`);
  }
});
test('archivo real de auditoria, sin prompts ni respuestas, retencion 500 y escrituras concurrentes', async () => {
  const dir = await mkdtemp(join(tmpdir(),'mcp-audit-'));
  try {
    const file=join(dir,'logs','mcp_calls.log');
    await mkdir(join(dir,'logs'));
    await writeFile(file, Array.from({length:505},(_,i)=>`anterior-${i}`).join('\n')+'\n');
    const audit = entry=>writeAudit(entry,file);
    const results=await Promise.all(Array.from({length:5},()=>auditedCall('gemini_ask',()=>geminiAsk('PROMPT_PRIVADO',async()=> 'RESPUESTA_PRIVADA'),audit)));
    const text=await readFile(file,'utf8');
    const lines=text.trim().split('\n');
    assert.equal(lines.length,500);
    for (const result of results) {
      const id=result.content.at(-1).text.match(/\[MCP_CALL_ID: (.+)\]/)[1];
      assert.equal(lines.filter(line=>line.includes(`call_id=${id}`)).length,1);
    }
    assert.match(lines.at(-1), /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{2}:\d{2} herramienta=gemini_ask call_id=GEM-\d{6}-[0-9A-F]{4} estado=OK duracion_ms=\d+$/);
    assert.ok(!text.includes('PRIVAD'));
  } finally { await rm(dir,{recursive:true,force:true}); }
});
test('fallo de auditoria se informa y conserva ID', async () => {
  const result=await auditedCall('antigravity_ask',async()=>({content:[{type:'text',text:'respuesta'}]}),async()=>{throw new Error('disco');});
  assert.equal(result.isError,true);
  assert.match(result.content.at(-2).text,/ERROR_AUDITORIA_MCP/);
  assert.match(result.content.at(-1).text,/^\[MCP_CALL_ID: AG-\d{6}-[0-9A-F]{4}\]$/);
});
