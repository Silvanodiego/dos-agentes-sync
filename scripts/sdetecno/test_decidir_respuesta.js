'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'decidir_respuesta.js'), 'utf8');
const execute = new vm.Script('(function(){' + source + '\n})()');
let count = 0;
function run(input, direct = '') {
  const warnings = [];
  const result = execute.runInNewContext({
    $: name => { assert.equal(name, 'Filtrar mensaje'); return { first: () => ({ json: {
      chatId: 'isolated-test', lockId: 'lock-test', respuestaDirecta: direct,
    } }) }; },
    $input: { first: () => ({ json: input }) },
    console: { warn: message => warnings.push(message) },
  });
  assert.equal(result.length, 1);
  assert.equal(result[0].json.chatId, 'isolated-test');
  assert.equal(result[0].json.lockId, 'lock-test');
  return { ...result[0].json, warnings };
}
function test(name, fn) { fn(); count++; console.log('OK ' + name); }
const text = JSON.stringify({ accion: 'responder', respuesta: 'Conectate a la red Internet.' });
for (const [name, payload] of [
  ['content.parts (production shape)', { content: { parts: [{ text }], role: 'model' }, finishReason: 'STOP', index: 0 }],
  ['legacy candidates', { candidates: [{ content: { parts: [{ text }] } }] }],
  ['text', { text }], ['output', { output: text }],
  ['split parts', { content: { parts: [{ text: text.slice(0, 20) }, { text: text.slice(20) }] } }],
  ['ignore thought parts', { content: { parts: [{ text: 'private reasoning', thought: true }, { text }] } }],
  ['markdown and BOM', { text: '\uFEFF  ```json\n' + text + '\n```  ' }],
  ['malformed candidates fallback', { candidates: [{ content: { parts: [{ text: '{}' }] } }], content: { parts: [{ text }] } }],
  ['part type guard', { content: { parts: [null, {}, { text: 22 }, { text }] } }],
]) test(name, () => { const r = run(payload); assert.equal(r.respuesta, 'Conectate a la red Internet.'); assert.equal(r.accion, 'responder'); assert.equal(r.errorFormato, undefined); assert.equal(r.warnings.length, 0); });
for (const payload of [null, undefined, {}, { candidates: [] }, { content: { parts: {} } },
  { content: { parts: [null, { text: 7 }] } }, { text: '{invalid' }, { text: '[]' }, { text: 'null' },
  { text: JSON.stringify({ respuesta: '' }) }, { text: JSON.stringify({ respuesta: 123 }) },
  { output: { respuesta: 'unexpected object' } }, { text: 'prefix ' + text },
  { text: JSON.stringify({ accion: 'comprar', respuesta: 'Buy now' }) },
  { text: JSON.stringify({ accion: 'constructor', respuesta: 'invalid action' }) },
]) test('format error ' + count, () => {
  const r = run(payload); assert.equal(r.accion, 'responder'); assert.ok(r.errorFormato);
  assert.match(r.respuesta, /No pude interpretar/); assert.doesNotMatch(r.respuesta, /registrad|resuelt|revis|deriv/);
  assert.equal(r.warnings.length, 1);
});
for (const accion of ['derivar', 'reenviar_codigo']) test('explicit ' + accion, () => assert.equal(run({ text: JSON.stringify({ accion, respuesta: 'Atención solicitada.' }) }).accion, accion));
test('direct verified answer bypasses model', () => { const r = run(null, 'Respuesta verificada.'); assert.equal(r.respuesta, 'Respuesta verificada.'); assert.equal(r.errorFormato, undefined); });
test('missing action defaults safely', () => assert.equal(run({ text: JSON.stringify({ respuesta: 'Hola.' }) }).accion, 'responder'));
test('legacy source precedence', () => assert.equal(run({ candidates: [{ content: { parts: [{ text }] } }], text: JSON.stringify({ respuesta: 'Other.' }) }).respuesta, 'Conectate a la red Internet.'));
console.log('PASS ' + count + ' tests; no external requests or messages.');
