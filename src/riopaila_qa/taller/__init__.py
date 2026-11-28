"""Módulo 3 · Asistente del Taller Castilla (Planta Castilla, Riopaila Castilla).

Capa del taller agrícola que se suma al agente del Módulo 2: flota y consumos reales de SAP
(DuckDB), manuales técnicos con la foto de la página, gráficas, informes PDF, alertas de
consumo, predicción de reposición, identificación de repuestos por foto y novedades de campo
con confirmación humana. Los datos reales y los manuales viven solo en el servidor; el repositorio
trae una muestra anonimizada (``data/taller/muestra``) para pruebas y CI.
"""
