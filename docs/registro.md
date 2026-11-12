# Registro de cambios

Bitácora de todo lo que se hace en el proyecto. Una entrada por cambio, la más reciente arriba.
Se añade con `scripts\registrar.ps1` y se enlaza desde cada pull request.

| Fecha | Tipo | Qué se hizo | PR |
|---|---|---|---|
| 2026-11-12 | infra | Confirmado Ollama con llama3.2:3b al 100% en GPU por Vulkan (CUDA desactivado) | #4 |
| 2026-11-12 | infra | Instalados Node.js 26.13.1, Ollama 0.40.16 y OpenCode 1.19.5; documentado el entorno local y la incidencia CUDA con la GTX 1060 | #3 |
| 2026-11-12 | fix | Añadido tzdata a requirements: Windows no trae base de zonas horarias (ZoneInfoNotFoundError Europe/Madrid) | #1 |
| 2026-11-12 | docs | Registro de cambios, plantilla de PR, CI y plan de conexión con el LLM | #1 |
| 2026-11-12 | infra | Copia del repositorio en la cuenta iatheaasitente-a11y y entorno local preparado | - |
