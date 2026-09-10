# Turn execution trace

El diagnóstico observa la ejecución; no controla el runtime ni expone razonamiento interno.

Cuando diagnostics está habilitado, el trace contiene únicamente información útil para entender el turno:

```text
trace_id
started_at / finished_at
duration_ms
final_ttft_ms
status
input
model
rounds
  round
  response
    finish_reason
    duration_ms
  tool_calls
    id
    name
    arguments_raw
    arguments
    duration_ms
    ok
    result
output
returned_context
error
```

`final_ttft_ms` mide el tiempo hasta el primer fragmento de la respuesta final que se entrega al usuario.

No se registran ni se exponen:

```text
reasoning_content
classifier routes
workers
provider chunk metadata
prompt progress
sampler internals
```

Los tool calls aparecen en el trace de diagnóstico, pero nunca se emiten como eventos `token` al visitante.
