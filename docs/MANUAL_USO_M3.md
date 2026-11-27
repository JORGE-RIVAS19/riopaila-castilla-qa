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

## Perfiles (los decide el servidor por tu número)

| Perfil | Quién | Ve | Puede |
|---|---|---|---|
| 🌎 Visitante | cualquier número aprobado | **Riopaila en cifras** (infografía y gráficas con fuente), documentos públicos, manuales y el taller con **datos de muestra anonimizados** | consultar |
| 🏢 Riopaila | jefes y otras áreas (`TALLER_ROLES=…=riopaila`) | además, **SAP real** | consultar |
| 🔧 Técnico / supervisor | personal del taller (`TALLER_ROLES` y `toolsBySender`) | todo, con SAP real | además, registrar novedades con confirmación |
| Número nuevo | — | recibe un código de *pairing*; el supervisor lo aprueba y queda como visitante | — |

> **Primer contacto:** WhatsApp oculta el número de quien escribe por primera vez. Antes de que alguien nuevo use el
> bot, escríbele “hola” **desde el celular del bot**; desde ese momento el servidor lo reconoce.

**Menú del visitante:** 1️⃣ *Riopaila en cifras* · 2️⃣ *Energía y etanol* · 3️⃣ *Cómo ayudo al taller* · 4️⃣ *Pregúntame
por la empresa*. Basta con responder el número.

## Para la demo (sábado 28)

1. Invitado: “Hola” → menú de visitante (OpenClaw, sin herramientas).
2. Invitado: “1” o “¿Qué es Riopaila en cifras?” → **infografía** con las cifras públicas y su fuente (M1/M2).
3. Invitado: “¿Hay consumos raros este mes?” → alertas sobre **datos de muestra** (el bot lo dice).
4. Jorge, 📷 foto de una etiqueta → código SAP **real** y advertencia si no coincide con el maestro.
5. Jorge, 🎙️ “¿Cómo cambio el filtro hidráulico del Puma 165?” → pasos + página del manual resaltada.
6. Jorge: “El 25375 está botando aceite, regístralo” → SÍ/NO → novedad registrada.
7. Invitado, lo mismo → “solo el personal del taller puede registrar novedades”.
