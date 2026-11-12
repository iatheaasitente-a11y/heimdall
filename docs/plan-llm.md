# Plan: conectar un LLM a la estructura

Principio: el modelo interpreta, Python calcula, SQLite conserva. El modelo no escribe números ni fechas.

## Reglas de diseño
1. El LLM solo devuelve datos estructurados (intención, campos, confianza), nunca la respuesta final con cifras.
2. Reglas primero; el LLM solo entra donde las reglas no llegan.
3. Apagado por defecto. Si falla o no está disponible, el sistema sigue con las reglas.
4. Frenos: tiempo máximo sin reintentos, tope de consultas por conversación y descarte si la confianza es baja.
5. Dos motores intercambiables por variable de entorno: local (Ollama) o nube.
6. Umbrales medidos con un banco de frases etiquetadas, no puestos a ojo.
7. La capa `llm` solo importa `llm`. Ampliar `REGLAS` en `tests/test_importaciones.py` y reflejarlo en `arquitectura.md`.
8. El `usuario_id` lo pone el sistema, nunca el modelo.

## Fases
| # | Fase | Estado |
|---|---|---|
| 1 | Cerrar base: servicios de Hábitos, Objetivos y Conversaciones; resolver puntos a revisar; CI | pendiente |
| 2 | Herramientas (`app/tools`) con esquema JSON sobre los servicios | pendiente |
| 3 | Capa `llm`: interfaz, motor local, motor nube opcional y motor falso para tests | pendiente |
| 4 | Agente abstracto y agente personal (reglas primero) | pendiente |
| 5 | Fábrica, router y chatbot por terminal; medición con CSV de frases | pendiente |
| 6 | Extra: módulo NBA | pendiente |