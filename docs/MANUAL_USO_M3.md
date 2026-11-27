# Manual de uso · Asistente del Taller Castilla

Escríbele al número del bot por WhatsApp como le escribirías a un compañero del taller. Puedes mandar texto,
**notas de voz** o **fotos**. El bot responde con datos de SAP, páginas de manuales y gráficas.

## Qué le puedo preguntar

| Tema | Ejemplos |
|---|---|
| Manuales y procedimientos | “¿Cómo se cambia el filtro hidráulico del Puma 165?” · “Puntos de engrase de la alzadora 2254” · “Calibración del embrague del Puma” |
| Eléctrico de las mulas | “¿Qué fusible es el del radio en la mula?” · “Diagrama del pito del Kenworth” · “El tablero CECU no enciende” |
| Equipos y gasto | “¿Cuánto ha gastado la cosechadora 27316 este año?” · “Top 10 de tractores con más gasto en 90 días” · “Hazme la gráfica del 25375” |
| Repuestos y códigos | “¿Hay código SAP para la referencia 47715391?” · “¿En qué equipos se usa el kit de sellos 11423828?” · “¿Qué es lo que más se le cambia a los Puma 165?” |
| Alertas y planeación | “¿Hay consumos raros este mes?” · “¿Qué le toca cambiar pronto al 25375?” · “Mándame el informe PDF de las alzadoras” |
| Fotos | 📷 una pieza + “¿qué es y qué código tiene?” |
| Fallas (solo personal del taller) | “El 25375 está botando aceite por la bomba, regístralo” → el bot pregunta **SÍ/NO** antes de guardar |
| La empresa (M2) | “¿Qué produce Riopaila Castilla?” · “¿Cuál fue la utilidad neta de 2024?” |

## Cómo leer las respuestas

- **📘 Manual, pág. N**: la foto adjunta es esa página; lo que preguntaste va resaltado en amarillo.
- **Cifras**: salen de SAP con su **fecha de corte** (último movimiento cargado). El modelo no calcula: si hace falta
  una resta o un porcentaje, lo hace Python.
- **Alertas**: “12×” significa que en la ventana reciente se consumió 12 veces lo esperado según el año anterior.
- **Predicción**: se basa en el intervalo mediano entre cambios del propio equipo; la confianza baja indica
  intervalos irregulares.
- **Foto de una pieza**: es una hipótesis. Confirma la referencia antes de pedir.

## Permisos

| Rol | Puede |
|---|---|
| Invitado (cualquier número en la lista blanca) | consultar todo, sin escribir |
| Técnico / supervisor (números de `TALLER_ROLES` y `toolsBySender`) | además, registrar novedades con confirmación |
| Número nuevo | recibe un código de *pairing*; el supervisor lo aprueba y queda como invitado |

> **Primer contacto:** WhatsApp oculta el número de quien escribe por primera vez. Antes de que alguien nuevo use el
> bot, escríbele “hola” **desde el celular del bot**; desde ese momento el servidor lo reconoce.

## Para la demo (sábado 28)

1. “Hola, ¿qué puedes hacer?” → responde la puerta (OpenClaw), sin herramientas.
2. “¿Qué fusible es el del radio en la mula?” → foto de la caja con el fusible resaltado.
3. 🎙️ nota de voz: “¿cómo cambio el filtro hidráulico del Puma 165?” → pasos + página del manual.
4. “¿Hay consumos raros este mes?” → alertas explicadas.
5. “Hazme la gráfica de gasto de las cosechadoras” → gráfica.
6. 📷 foto de un filtro → identificación + código SAP.
7. “El 25375 está botando aceite, regístralo” → pregunta SÍ/NO → “SÍ” → novedad registrada.
8. Desde el teléfono de un invitado, lo mismo → explica que solo el taller puede registrar.
