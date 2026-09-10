# DoD — Agent Runtime mínimo, simple y Go-like

**Estado:** Propuesto para revisión  
**BDD:** `BDD-agent-runtime-minimo.md`  
**SDD:** `SDD-agent-runtime-minimo.md`

Este cambio **no está terminado porque compile ni porque el smoke dé 10/10**.

Se considera terminado sólo cuando pasa todos los gates de este documento.

---

## 1. Gate estructural — el runtime es realmente mínimo

Debe cumplirse todo:

```text
[ ] Existe un solo Agent.
[ ] Existe un solo system prompt.
[ ] Qwen recibe directamente las 3 tools disponibles.
[ ] No existe classifier.
[ ] No existen Route ni Dispatch.
[ ] No existen Worker ni WorkerResult.
[ ] No existe fan-out por dominio.
[ ] No existen registries duplicados de tools.
[ ] Cada tool tiene un único camino visible desde nombre -> validación -> handler.
[ ] No existe código legacy para respuestas {"answer": "..."}.
[ ] No existe cache/reuse de tool calls sin un requisito funcional demostrado.
[ ] No existe force_answer ni lógica equivalente.
[ ] No hay imports, funciones, clases o archivos muertos.
```

Búsqueda final obligatoria: no deben quedar referencias activas a:

```text
Route
Dispatch
classify
Worker
WorkerResult
_REGISTERED_TOOLS
_TOOL_BY_NAME
tool_name
successful_calls
force_answer
```

Si alguna permanece, debe justificarse contra un requisito concreto del BDD. Si no puede justificarse, se elimina.

---

## 2. Gate de legibilidad — entendible en menos de 5 minutos

Una persona que no implementó el cambio debe poder seguir el flujo leyendo sólo:

```text
agent.py
→ tools.py
→ prompt.py
```

Debe poder explicar sin documentación adicional:

```text
mensaje
→ Qwen
→ tool opcional
→ ejecución
→ resultado a Qwen
→ respuesta final en streaming
```

No se acepta una explicación que dependa de registries ocultos, adapters, factories, callbacks o capas secundarias.

Cada función, clase o helper debe responder claramente:

> ¿Qué requisito funcional necesita esta pieza?

Si la respuesta es “podría servir después”, la pieza no entra en este cambio.

---

## 3. Gate determinístico — probar nuestro runtime sin depender de Qwen real

Los tests unitarios deben usar un fake de Qwen con streams programados.

Deben pasar **100%** los siguientes comportamientos:

```text
[ ] Texto final se entrega token por token mientras llega.
[ ] Una ronda de tool no emite texto al usuario.
[ ] Después de una tool, la respuesta final se transmite token por token.
[ ] reasoning_content nunca se transmite al usuario.
[ ] Tool-call fragmentada reconstruye correctamente id, name y arguments.
[ ] search_portfolio se ejecuta exactamente cuando el fake la solicita.
[ ] resolve_datetime se ejecuta exactamente cuando el fake la solicita.
[ ] set_reminder_mock se ejecuta exactamente cuando el fake la solicita.
[ ] Tool desconocida se rechaza.
[ ] JSON inválido se rechaza.
[ ] Argumento requerido faltante se rechaza.
[ ] Argumento extra o inválido se rechaza.
[ ] tool_call_id se conserva entre assistant tool_call y tool result.
[ ] El contexto previo llega a la siguiente ronda.
[ ] Texto final + tool_call en la misma ronda produce error de protocolo.
[ ] MAX_TOOL_ROUNDS detiene loops.
[ ] diagnostics no modifica el comportamiento funcional.
```

Estos tests prueban el runtime. No deben usar frases de usuario para forzar decisiones semánticas.

---

## 4. Gate de tools — lógica determinística independiente del LLM

Las tools se prueban directamente, sin modelo.

Debe pasar **100%**:

```text
[ ] resolve_datetime resuelve fechas explícitas.
[ ] resolve_datetime resuelve offsets relativos.
[ ] resolve_datetime valida timezone.
[ ] set_reminder_mock devuelve persisted=false.
[ ] set_reminder_mock devuelve will_notify=false.
[ ] set_reminder_mock mantiene status=simulated_only.
[ ] search_portfolio delega correctamente a Portfolio.search().
[ ] execute_tool rechaza nombres desconocidos.
[ ] Todas las tools validan sus argumentos antes de ejecutar.
```

Un fallo aquí se corrige en la tool o en el runtime, nunca en el prompt.

---

## 5. Gate de integración — API, SSE y conversación

La integración completa debe demostrar:

```text
[ ] `/v1/chat/stream` mantiene contrato SSE válido.
[ ] Los eventos `token` llegan incrementalmente durante la respuesta final.
[ ] Los tool calls y tool results no se filtran como tokens al usuario.
[ ] El evento `context` contiene el turno completo necesario para continuar la conversación.
[ ] ConversationStore conserva follow-ups.
[ ] Una desconexión HTTP corta el stream sin dejar el turno corrupto.
[ ] Un error produce el evento de error esperado sin filtrar detalles internos.
```

El router no debe conocer reglas de selección de tools ni lógica de Qwen.

---

## 6. Gate de comportamiento — Qwen real

El smoke actual es sólo una comprobación rápida. **No es evidencia suficiente de funcionalidad.**

La evaluación real debe cubrir al menos:

```text
general
portfolio
temporal
reminders
consultas mixtas
follow-ups
ambigüedad
casos negativos
contrastes semánticos
variantes de redacción
ES / EN
```

Las respuestas libres se evalúan por propiedades, no por igualdad literal.

Ejemplo:

```text
¿Qué es FastAPI?
→ no tool

¿Diego trabajó con FastAPI?
→ search_portfolio
```

Debe medirse como mínimo:

```text
tool-selection precision
tool-selection recall
false-tool rate
argument accuracy
grounding del portfolio
context success
multi-tool success
language preservation
protocol failures
answer presence
```

Criterio mínimo para aceptar el cambio:

```text
[ ] 100% en errores de protocolo y seguridad del runtime.
[ ] 100% en ejecución válida de tools seleccionadas.
[ ] >=95% de comportamiento correcto global en el dataset de desarrollo.
[ ] Ninguna categoría crítica puede quedar por debajo de 90%.
[ ] No puede existir una clase de fallo sistemático oculta por el promedio global.
```

Si una métrica falla, el resultado debe mostrar **qué categoría falla**, no sólo un pass rate total.

---

## 7. Gate de generalización — holdout

El dataset debe dividirse antes del ajuste final:

```text
development set
holdout set
```

Reglas:

```text
[ ] El prompt puede ajustarse usando sólo development.
[ ] Los casos de holdout no se usan para escribir reglas específicas.
[ ] El código y prompt se congelan antes de ejecutar holdout.
[ ] Holdout debe alcanzar >=95% global.
[ ] Ninguna categoría crítica del holdout puede quedar por debajo de 90%.
```

Si se modifica el prompt o runtime después de mirar un fallo del holdout, ese conjunto deja de ser holdout para esa iteración y debe reemplazarse por casos nuevos.

Esto evita optimizar el agente para frases conocidas.

---

## 8. Gate de robustez — variantes y contrastes

Para intenciones críticas deben existir variantes equivalentes.

Ejemplo:

```text
¿Diego trabajó con MuleSoft?
¿Tiene experiencia en Mule?
Contame su experiencia con MuleSoft.
What MuleSoft experience does Diego have?
```

Todas deben conservar la misma propiedad esperada.

También deben existir contrastes donde un pequeño cambio sí modifica el comportamiento:

```text
¿Qué es FastAPI?        → no tool
¿Diego usa FastAPI?     → search_portfolio

¿Qué es un reminder?    → no tool
Recordame llamar luego. → set_reminder_mock
```

No se acepta corregir un fallo agregando al prompt una excepción para una frase concreta.

Toda corrección debe resolver una causa general:

```text
descripción de tool ambigua
prompt ambiguo
schema incorrecto
runtime incorrecto
retrieval incorrecto
limitación real del modelo
```

---

## 9. Gate de estabilidad — comportamiento no accidental

Un subconjunto crítico debe ejecutarse varias veces con Qwen real.

Mínimo:

```text
20 casos críticos
× 5 ejecuciones
= 100 ejecuciones
```

Debe incluir:

```text
portfolio vs general
temporal
reminders
consultas mixtas
follow-ups
```

Criterio:

```text
[ ] >=95% de ejecuciones correctas en el conjunto de estabilidad.
[ ] Ningún caso crítico puede fallar repetidamente por la misma causa sin documentarse y resolverse.
```

Un caso que pasa una vez y falla repetidamente no se considera resuelto.

---

## 10. Gate de streaming y latencia percibida

El cambio debe demostrar que el runtime **no agrega buffering innecesario**.

Debe cumplirse:

```text
[ ] `stream=True` se mantiene para la llamada a Qwen.
[ ] El primer fragmento de respuesta final se emite al usuario cuando llega.
[ ] No se espera a `finish_reason` para empezar a transmitir una respuesta final.
[ ] Las rondas internas de tools nunca se transmiten al usuario.
[ ] Sólo id, name y arguments de tool calls se reconstruyen internamente.
[ ] No se reconstruye metadata del proveedor que no sea necesaria para ejecución o diagnóstico.
```

Se registran por separado:

```text
TTFT final
latencia total
latencia de tools
cantidad de rondas
```

No se exige un tiempo absoluto en esta iteración porque depende del hardware y del modelo. Sí se exige que el runtime no espere artificialmente la respuesta completa antes de enviar el primer token final.

---

## 11. Gate de tests existentes

Los tests actuales se revisan uno por uno.

Se conserva un test sólo si verifica comportamiento observable o un contrato necesario.

Se eliminan tests que sólo exijan la existencia de:

```text
classifier
Route / Dispatch
Worker / WorkerResult
registry interno
legacy JSON answer
reuse / force_answer
```

No se modifica el producto para mantener tests de una arquitectura eliminada.

Comprobación local mínima:

```bash
cd server
make check
```

Los evals con Qwen real se ejecutan después de pasar los gates determinísticos.

---

# Checklist final de merge

El cambio sólo puede mergearse cuando todo esto esté marcado:

```text
[ ] BDD satisfecho.
[ ] SDD implementado sin capas adicionales no justificadas.
[ ] Gate estructural completo.
[ ] Gate de legibilidad aprobado por revisión humana.
[ ] Tests determinísticos 100%.
[ ] Tests de tools 100%.
[ ] Integración API/SSE correcta.
[ ] Dataset de comportamiento ejecutado y analizado por categoría.
[ ] Development >=95% global.
[ ] Holdout >=95% global.
[ ] Categorías críticas >=90%.
[ ] Stability >=95% sobre ejecuciones repetidas.
[ ] 0 fallos de protocolo.
[ ] 0 filtrado de reasoning/tool internals al usuario.
[ ] Streaming final entrega tokens mientras se generan.
[ ] No existe código muerto.
[ ] No existen abstracciones o compatibilidad legacy sin requisito.
[ ] No se agregaron reglas específicas para hacer pasar frases del dataset.
```

## Regla de cierre

**Verde no significa terminado.**

El runtime está terminado sólo cuando puede demostrarse simultáneamente que:

```text
es pequeño
es entendible
es determinísticamente correcto
funciona con Qwen real
se generaliza a casos no vistos
es estable entre ejecuciones
y no sacrifica la experiencia de streaming del usuario
```
