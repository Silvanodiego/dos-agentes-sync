// n8n Code node: Decidir respuesta. Commercial authorization stays downstream.
const f = $('Filtrar mensaje').first().json;
const responseText = parts => Array.isArray(parts)
  ? parts.filter(p => p && p.thought !== true && typeof p.text === 'string').map(p => p.text).join('')
  : '';
function parseReply(input) {
  if (!input || typeof input !== 'object') return { error: 'missing_payload' };
  const sources = [
    responseText(input.candidates?.[0]?.content?.parts),
    responseText(input.content?.parts),
    input.text,
    input.output,
  ];
  for (const source of sources) {
    if (typeof source !== 'string' || !source.trim()) continue;
    let value;
    try {
      const raw = source.replace(/^\uFEFF/, '').trim()
        .replace(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/i, '$1').trim();
      value = JSON.parse(raw);
    } catch (_) { continue; }
    if (!value || Array.isArray(value) || typeof value !== 'object' ||
        typeof value.respuesta !== 'string' || !value.respuesta.trim()) continue;
    // Actions never execute purchases or payments here. Unknown actions fail closed.
    if (value.accion !== undefined &&
        !['responder', 'derivar', 'reenviar_codigo'].includes(value.accion)) continue;
    return { respuesta: value.respuesta.trim(), accion: value.accion || 'responder' };
  }
  return { error: 'invalid_reply_format' };
}
let respuesta = typeof f.respuestaDirecta === 'string' ? f.respuestaDirecta : '';
let accion = 'responder';
let errorFormato = '';
if (!respuesta.trim()) {
  const parsed = parseReply($input.first().json);
  if (parsed.error) {
    errorFormato = parsed.error;
    console.warn('bot_reply_format_error:' + errorFormato);
    respuesta = 'No pude interpretar la respuesta automática. Escribí «planes» para ver las opciones, o contame qué necesitás.';
  } else {
    respuesta = parsed.respuesta;
    accion = parsed.accion;
  }
}
return [{ json: { ...f, chatId: f.chatId, lockId: f.lockId, respuesta, accion,
  ...(errorFormato ? { errorFormato } : {}) } }];
