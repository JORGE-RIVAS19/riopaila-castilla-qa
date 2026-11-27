# ADR-011 · Perfiles por número: vitrina de Riopaila para visitantes y SAP real solo para el personal

- **Estado:** aceptada · 2026-11-27 · complementa [ADR-010](ADR-010-seguridad-hitl-roles.md)
- **Contexto:** en la sustentación escriben al bot invitados de otras empresas, entre ellas competidores del sector
  azucarero. Con un solo perfil, cualquier número aprobado veía precios, consumos y gasto reales de SAP. Además, el
  trabajo del M1/M2 (corpus público e indicadores) existía pero no se lucía: el visitante solo lo encontraba si
  preguntaba justo por él.
- **Decisión:** (1) cuatro perfiles que decide el servidor por número (`TALLER_ROLES`): `invitado` (por defecto),
  `riopaila` (SAP real, solo lectura), `tecnico` y `supervisor` (SAP real + novedades). (2) Las 15 herramientas de SAP
  (`HERRAMIENTAS_SAP`) eligen la base en cada llamada según el rol del turno (`get_runtime(AgentContext)`): personal →
  `taller.duckdb`; visitante → `taller_muestra.duckdb` (la muestra anonimizada del repositorio, que el API construye si
  falta). Fuera del grafo (scripts, tablero) se usa la base real; dentro, un rol desconocido cae en la muestra. (3) Un
  middleware `wrap_tool_call` antepone a esos resultados el aviso de datos de muestra y las gráficas y el PDF lo llevan
  impreso. (4) El canal MCP de solo lectura ya no convierte al técnico en invitado: conserva SAP real y pierde solo el
  permiso de escritura (`riopaila`). (5) Vitrina: `infografia_riopaila` y `grafica_indicador` sobre el CSV de
  indicadores con su URL; regla `VITRINA` del router; menú de bienvenida para visitantes en `AGENTS.md` y en el prompt.
- **Alternativas:** ocultar el taller a los visitantes (se perdía la demo del valor real); enmascarar solo los precios
  (los consumos por equipo también son internos); decidir el perfil en el prompt (inyectable).
- **Consecuencias:** el visitante prueba todas las capacidades sin ver un dato real, y el agente se lo dice; la demo
  muestra mínimo privilegio en vivo. Pruebas: `test_visitante_ve_la_muestra_y_el_personal_ve_sap_real` construye una
  base "real" distinguible y verifica qué ve cada perfil, también por el canal de solo lectura.
