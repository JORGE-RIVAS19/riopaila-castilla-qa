# Spec · Asistente Q&A, Resumen y FAQ

## Purpose
Responder la primera consulta de un cliente con información pública verificable de Riopaila Castilla.

## Requirements

### Requirement: Respuestas fundamentadas
El sistema SHALL responder solo con información del contexto y citar cada afirmación como `[n]`.

#### Scenario: Cita inventada
- WHEN el modelo cita un id que no estaba en el contexto
- THEN la app lo marca como posible alucinación (`invalid_citations`)

#### Scenario: Pregunta fuera de alcance
- WHEN la respuesta no está en los documentos
- THEN el asistente responde la frase de abstención definida en el prompt

#### Scenario: Intento de inyección
- WHEN el usuario pide ignorar reglas, revelar el prompt o responder en JSON
- THEN responde "Solo puedo ayudarte con información pública de Riopaila Castilla."

### Requirement: Presupuesto de contexto
El sistema SHALL meter el corpus completo en el prompt de sistema cuando cabe en el presupuesto de tokens y,
si no cabe, preseleccionar fragmentos con BM25 reordenados en U (mejores en los extremos).

### Requirement: Tres tareas
El sistema SHALL ofrecer Resumen (T=0.3, top_p=0.9), FAQ con esquema Pydantic (T=0, top_p=0.1) y
Q&A (T=0, top_p=0.1) orquestados con LangChain.

### Requirement: Evaluación
El sistema SHALL correr una batería de al menos 20 preguntas y reportar cita válida, aciertos de hechos
verificados, abstención correcta, rechazo de inyección, latencia y tokens.
