# Plan: conectar un LLM a la estructura

Principio: el modelo interpreta, Python calcula, SQLite conserva. El modelo no
escribe números ni fechas.

## Reglas de diseño
1. El LLM devuelve solo datos estructurados (intención, campos, confianza),
   nunca la respuesta final con cifras.
2. Reglas primero; el LLM solo entra donde las reglas no llegan.
3. Apagado por defecto. Si falla o no está disponible, el sistema sigue con las reglas.
4. Frenos: timeout sin reintentos, tope de consultas por conversación y
   descarte si la confianza es baja.
5. Dos motores intercambiables por variable de entorno: local (Ollama) o nube.
6. Umbrales medidos con un banco de frases etiquetadas, no puestos a ojo.
7. La capa `llm` solo importa `llm`. Ampliar `REGLAS` en
   `tests/test_importaciones.py` y reflejarlo en `arquitectura.md`.
8. El `usuario_id` lo pone el sistema, nunca el modelo.
9. Las reglas temporales usan un parser puro con reloj/zona recibidos como
   argumentos; un valor ambiguo se aclara en vez de completarse por intuición.

## Fases
| # | Fase | Estado |
|---|---|---|
| 1 | Cerrar servicios base; resolver revisiones y CI | hecho |
| 2 | Herramientas (`app/tools`) con esquemas JSON sobre servicios | hecho |
| 3 | Capa `llm`: interfaz, motores local/nube y falso para tests | hecho |
| 4 | Agente abstracto y agente personal (reglas primero) | hecho |
| 5 | Fábrica, router, chatbot por terminal y medición con CSV | pendiente |
| 6 | Extra: interfaz NBA, fuente falsa y herramienta opcional | hecho |
