# Revisión de fases

La columna de tests indica `suite completa / importaciones / calidad`. Los
documentos enumerados son los que se actualizaron en cada fase; `—` indica que
el commit de esa fase no modificó documentación. La fase 13 se identifica como
este commit porque no es posible incluir su propio hash dentro del árbol que lo
genera.

| Fase | Rama | Commit | Tests | Docs actualizados | Criterio |
|---|---|---|---:|---|---|
| 1. Conversaciones | `feat/servicio-conversaciones` | `3e8cbbd` | 410 / 28 / 2 | `arquitectura.md`, `decisiones.md`, `hoja-de-ruta.md`, `servicios.md` | Cumple |
| 2. Herramientas | `feat/herramientas` | `1863ab4` | 427 / 28 / 2 | `arquitectura.md`, `plan-llm.md`, `servicios.md` | Cumple |
| 3. Capa LLM | `feat/capa-llm` | `d778ac4` | 451 / 28 / 2 | `arquitectura.md`, `plan-llm.md` | Cumple |
| 4. Agente personal | `feat/agentes` | `f8da985` | 461 / 28 / 2 | `arquitectura.md`, `plan-llm.md` | Cumple |
| 5. Chatbot | `feat/chatbot` | `907147f` | 480 / 31 / 2 | — | Cumple; además se verificó un checkout limpio |
| 6. Módulo NBA | `feat/modulo-nba` | `650074d` | 487 / 33 / 2 | `arquitectura.md`, `decisiones.md`, `hoja-de-ruta.md`, `plan-llm.md`, `servicios.md` | Cumple con fuente falsa, sin API real |
| 7. Auditoría Hugin | `feat/auditoria-hugin` | `5deea6a` | 487 / 33 / 2 | `auditoria-hugin.md`, `hoja-de-ruta.md` | Cumple; Hugin no se modificó ni importó |
| 8. Lenguaje de fechas | `feat/fechas` | `d78228f` | 545 / 33 / 2 | `arquitectura.md`, `decisiones.md`, `dominio.md`, `hoja-de-ruta.md`, `plan-llm.md` | Cumple; 58 pruebas específicas |
| 9. Nombres y listados | `feat/resolucion-por-nombre` | `245a9fe` | 556 / 33 / 2 | `arquitectura.md`, `hoja-de-ruta.md`, `servicios.md` | Cumple |
| 10. Reglas del agente | `feat/reglas-del-agente` | `9dd5a89` | 577 / 33 / 2 | `arquitectura.md`, `hoja-de-ruta.md` | Cumple |
| 11. Validación y contexto | `feat/entender-reforzado` | `bc6b841` | 583 / 33 / 2 | `arquitectura.md`, `hoja-de-ruta.md`, `plan-llm.md` | Cumple |
| 12. Frases y medición | `feat/frases-y-medicion` | `1d1cae1` | 583 / 33 / 2 | `hoja-de-ruta.md`, `plan-llm.md` | Cumple; 30,0 % ajuste y 30,0 % reserva |
| 13. Revisión final | `feat/revision-final` | Este commit | 583 / 33 / 2 | `revision-fases.md`, `hoja-de-ruta.md`, `plan-llm.md`, `prueba-real.md` | Cumple al pasar la validación limpia |

## Observaciones

- Los resultados de la fase 12 se calculan sobre 70 frases de ajuste y 30 de
  reserva. Se informa también la cobertura de respuestas, que no equivale a
  una acción correcta.
- La comparación real de Ollama no se ha ejecutado como parte de esta cadena;
  está planificada en el Bloque A.
- Las fuentes reales NBA, avisos, Streamlit, Telegram y el aviso de cámara
  siguen fuera de la implementación actual, según el Bloque B.
