# Requerimiento — Agent Runtime mínimo, simple y Go-like

**Estado:** Propuesto para revisión  
**Alcance:** `server/app`  
**Objetivo:** simplificar el runtime del agente hasta el mínimo necesario, sin perder las capacidades actuales ni introducir lógica específica para pasar casos de prueba.

## 1. Objetivo

El runtime debe poder entenderse en menos de 5 minutos leyendo principalmente:

```text
agent.py
tools.py
prompt.py
```

Debe ser:

- simple de leer;
- explícito;
- fácil de seguir;
- sin código muerto;
- sin registros o estructuras duplicadas;
- sin compatibilidad legacy innecesaria;
- sin abstracciones especulativas;
- fácil de extender agregando una tool nueva.

## 2. Capacidades que se mantienen

El agente debe seguir pudiendo:

1. responder conversación general;
2. consultar información factual del portfolio con `search_portfolio`;
3. resolver fechas y horas con `resolve_datetime`;
4. crear recordatorios simulados con `set_reminder_mock`;
5. mantener contexto conversacional;
6. resolver consultas que requieran una o más tools;
7. transmitir la respuesta final al usuario mientras se genera.

FastAPI, SSE, `ConversationStore` y la lógica de retrieval del portfolio quedan fuera del rediseño salvo adaptación mínima de interfaz.

## 3. Diseño objetivo

```text
Usuario
  ↓
Agent
  ↓
Qwen + tools disponibles
  ↓
¿Respuesta final?
  ├─ Sí → transmitir respuesta al usuario
  └─ No → ejecutar tool
              ↓
          agregar resultado
              ↓
            Qwen
              ↓
          repetir hasta respuesta
```

No debe existir routing previo por dominio salvo que una necesidad real y demostrable lo requiera.

# 4. Requerimientos BDD

## Feature: Un único agente ejecuta la conversación

### Scenario: Consulta general sin tools

**Given** un usuario realiza una pregunta general  
**When** el agente envía la consulta a Qwen  
**Then** Qwen debe responder directamente  
**And** no debe ejecutarse ninguna tool  
**And** no debe existir una llamada previa a un classifier.

### Scenario: Consulta que necesita portfolio

**Given** el usuario pregunta información factual del portfolio  
**When** Qwen necesita evidencia para responder  
**Then** debe solicitar `search_portfolio`  
**And** Python debe validar y ejecutar la tool  
**And** el resultado debe volver a Qwen  
**And** Qwen debe generar la respuesta final sin inventar información.

### Scenario: Consulta temporal

**Given** el usuario pregunta por una fecha, hora, día o timezone  
**When** Qwen necesita resolver el valor temporal  
**Then** debe llamar `resolve_datetime`  
**And** Python debe ejecutar el cálculo de forma determinística  
**And** Qwen debe responder usando el resultado de la tool.

### Scenario: Recordatorio simulado

**Given** el usuario pide crear un recordatorio  
**When** Qwen procesa la solicitud  
**Then** debe llamar `set_reminder_mock`  
**And** el recordatorio debe seguir siendo simulado y no persistente  
**And** la respuesta final debe aclarar que no existe una notificación real.

### Scenario: Consulta que necesita varias capacidades

**Given** una consulta necesita más de una tool  
**When** Qwen solicita las tools necesarias  
**Then** el runtime debe ejecutar únicamente las tools declaradas  
**And** devolver sus resultados a Qwen  
**And** producir una única respuesta final.

## Feature: Tools simples y explícitas

### Scenario: Definición no redundante

**Given** una tool disponible  
**Then** debe existir un único camino claro entre:

```text
nombre
schema
handler
```

**And** no deben existir registries secundarios que representen la misma relación.

### Scenario: Ejecución de una tool

**Given** Qwen solicita una tool  
**When** Python recibe el `tool_call`  
**Then** debe validar el nombre  
**And** validar los argumentos  
**And** ejecutar el handler correspondiente  
**And** devolver el resultado usando el mismo `tool_call_id`.

### Scenario: Tool desconocida

**Given** Qwen solicita una tool no declarada  
**When** el runtime intenta resolverla  
**Then** debe rechazarla explícitamente  
**And** no debe ejecutar código fuera de la allowlist.

## Feature: Tool loop mínimo y seguro

### Scenario: Respuesta directa

**Given** Qwen devuelve texto y no solicita tools  
**When** el agente procesa la respuesta  
**Then** debe transmitir ese texto como respuesta final.

### Scenario: Tool call válida

**Given** Qwen devuelve una tool call válida  
**When** la tool termina  
**Then** el resultado debe agregarse al historial del turno  
**And** debe realizarse una nueva llamada a Qwen.

### Scenario: Límite de iteraciones

**Given** Qwen continúa solicitando tools sin producir una respuesta final  
**When** alcanza el máximo de rondas  
**Then** el runtime debe detenerse con un error explícito  
**And** no debe reutilizar, forzar ni inventar respuestas para ocultar el problema.

## Feature: Streaming sólo de la respuesta final

### Scenario: Respuesta final por streaming

**Given** una ronda produce la respuesta final  
**When** comienzan a llegar tokens de texto  
**Then** el usuario debe recibirlos a medida que llegan  
**And** el runtime no debe esperar a acumular la respuesta completa.

### Scenario: Ronda de tool interna

**Given** una ronda produce un `tool_call`  
**When** llegan fragmentos del tool call  
**Then** esos fragmentos no deben enviarse al usuario  
**And** tampoco deben enviarse argumentos, resultados de tools, reasoning ni metadata interna.

### Scenario: El modelo mezcla texto final y tool call

**Given** una ronda comenzó como respuesta final  
**When** luego aparece un `tool_call`  
**Then** el runtime debe tratarlo como violación de protocolo  
**And** fallar explícitamente en lugar de ocultarlo con heurísticas.

## Feature: Contexto conversacional

### Scenario: Conversación con contexto previo

**Given** existen mensajes anteriores  
**When** se procesa un nuevo mensaje  
**Then** el contexto permitido debe enviarse a Qwen  
**And** los mensajes `assistant -> tool -> assistant` deben mantener un protocolo válido.

# 5. Cambios requeridos

## Eliminar

- `dispatcher.py`;
- `Route` y `Dispatch`;
- `classify()`;
- classifier prompt y helpers exclusivos del classifier;
- `Worker` y `WorkerResult`;
- `self._workers`;
- fan-out y composición por rutas;
- `_REGISTERED_TOOLS`;
- `_TOOL_BY_NAME` si duplica la relación de tools;
- `tool_name()` si deja de ser necesario;
- compatibilidad legacy con respuestas `{"answer":"..."}`;
- cache/reuse de tool calls sin evidencia funcional;
- `force_answer` y lógica equivalente;
- cualquier código que sólo exista para una arquitectura anterior.

## Mantener

- schemas de `search_portfolio`, `resolve_datetime` y `set_reminder_mock`;
- handlers reales;
- validación de argumentos;
- allowlist de tools;
- `tool_call_id`;
- límite del tool loop;
- contexto conversacional;
- idioma del visitante;
- retrieval del portfolio;
- streaming de la respuesta final;
- SSE como interfaz de transporte.

## Simplificar

`agent.py` debe mostrar el flujo completo:

```text
construir mensajes
→ llamar Qwen
→ si hay tool call, ejecutarla
→ devolver resultado a Qwen
→ si hay respuesta final, transmitirla
```

`tools.py` debe contener únicamente contratos, validación y ejecución de tools.

`prompt.py` debe contener un único system prompt claro, directo y específico.

# 6. Reglas de implementación

- KISS primero.
- Control de flujo explícito.
- Early return cuando corresponda.
- No crear factories, registries, adapters o wrappers si no reducen complejidad.
- No crear abstracciones para futuros casos hipotéticos.
- No hardcodear preguntas del dataset.
- No cambiar comportamiento para acomodar un test.
- Cada helper debe justificar su existencia.
- Si una estructura duplica información ya disponible, eliminar una representación.
- El tracing debe observar el runtime, no condicionarlo.

# 7. Tareas

## T1 — Inventariar el runtime actual

Revisar:

```text
agent.py
worker.py
dispatcher.py
tools.py
prompt.py
trace.py
```

Clasificar cada símbolo importante como `KEEP`, `DELETE` o `MERGE` antes de modificar código.

## T2 — Simplificar tools

Crear un camino único y explícito desde nombre de tool hasta handler.

Mantener schemas y validaciones necesarias. Eliminar registries y wrappers redundantes.

## T3 — Diseñar el prompt único

Aplicar estrictamente:

```text
primera línea clara y directa
instrucciones con verbos de acción
pautas específicas de comportamiento
restricciones explícitas
sin duplicar el schema de cada tool
```

No incluir ejemplos literales del dataset.

## T4 — Reescribir `Agent.respond()`

Implementar un único tool loop con `stream=True`.

La respuesta final debe transmitirse token por token. Las rondas de tools permanecen internas.

## T5 — Eliminar classifier y workers

Eliminar archivos, imports, tipos, prompts y tests que sólo validen esa arquitectura.

No conservar adapters de compatibilidad interna.

## T6 — Reducir tracing

Conservar únicamente información operativa útil. Eliminar metadata de proveedor que no participe en diagnóstico real.

## T7 — Limpiar tests

Conservar tests de comportamiento observable y agregar cobertura para streaming, tools, contexto, errores y límite del loop.

## T8 — Buscar código muerto

Debe quedar cero referencias a:

```text
Route
Dispatch
classify
Worker
WorkerResult
_REGISTERED_TOOLS
_TOOL_BY_NAME
tool_name
force_answer
successful_calls
```

# 8. Criterios de aceptación

```text
[ ] Existe un solo Agent.
[ ] Existe un solo system prompt.
[ ] Qwen recibe las 3 tools directamente.
[ ] No existe classifier.
[ ] No existen Route/Dispatch.
[ ] No existen Worker/WorkerResult.
[ ] No existen registries duplicados de tools.
[ ] Hay un único tool loop fácil de seguir.
[ ] Una consulta general puede responder sin tool.
[ ] Portfolio usa search_portfolio cuando corresponde.
[ ] Fechas usan resolve_datetime cuando corresponde.
[ ] Reminders usan set_reminder_mock cuando corresponde.
[ ] Tool desconocida es rechazada.
[ ] Argumentos inválidos son rechazados.
[ ] Se preserva tool_call_id.
[ ] Existe límite explícito de rondas.
[ ] Las rondas de tools no transmiten contenido al usuario.
[ ] La respuesta final se transmite token por token sin esperar a completarse.
[ ] reasoning_content nunca llega al usuario.
[ ] No existe compatibilidad legacy innecesaria.
[ ] No hay código muerto.
[ ] El flujo completo puede explicarse leyendo agent.py, tools.py y prompt.py en menos de 5 minutos.
```

## Regla final

Para cada clase, función, helper o archivo del nuevo runtime debe poder responderse:

```text
¿Qué requisito concreto necesita esta pieza?
```

Si no existe una respuesta clara, la pieza se elimina.
