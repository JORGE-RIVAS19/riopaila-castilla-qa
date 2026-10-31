# Constitución del proyecto

Principios no negociables que guían cada decisión técnica del asistente de Riopaila Castilla.

1. **Veracidad antes que fluidez.** El asistente prefiere decir "no lo encuentro" a inventar un dato.
   Toda afirmación se respalda con una fuente citada y verificable.
2. **Reproducibilidad.** Cualquier integrante obtiene el mismo corpus y el mismo entorno con
   `uv sync` y `uv run python scripts/scrape_empresa.py`. Nada se copia a mano.
3. **Respeto por la fuente.** Solo datos públicos, `robots.txt` respetado, servidor tratado con cortesía y
   cero datos personales.
4. **Privacidad por defecto.** El modelo por defecto corre en local (Ollama); la API es una opción explícita.
5. **El humano decide, el agente ejecuta, la evidencia valida.** Todo cambio entra por Pull Request revisado,
   con pruebas en verde.
