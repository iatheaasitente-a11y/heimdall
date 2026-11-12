# Prueba manual con Ollama

Esta guía valida el chatbot real de terminal; no forma parte de `pytest`, que
no requiere Ollama. El CLI selecciona `llama3.2:3b` por defecto cuando
`HEIMDALL_LLM=ollama`. La comparación con `qwen3:4b-instruct-2507` requiere
inyectar ese modelo explícitamente o añadir una selección de modelo al CLI,
pendiente del Bloque A de la hoja de ruta.

## Preparación

1. Instalar y arrancar Ollama. En la GTX 1060, seguir el estado del controlador
   y la alternativa Vulkan documentados en [`entorno-local.md`](./entorno-local.md).
2. Descargar los modelos que se compararán:

   ```powershell
   ollama pull llama3.2:3b
   ollama pull qwen3:4b-instruct-2507
   ```

3. Confirmar que el servidor responde y que los dos modelos aparecen:

   ```powershell
   ollama list
   ```

4. Desde la raíz del proyecto, activar el entorno e indicar el motor:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   $env:HEIMDALL_LLM = "ollama"
   $env:HEIMDALL_LLM_TIMEOUT = "10"
   python -m app.chatbot
   ```

   La primera carga puede tardar unos 25 segundos. El calentamiento del chatbot
   admite al menos 30 segundos; las consultas usan el timeout configurado.

## Frases manuales

Probar cada frase en una conversación distinta o anotar el estado previo de la
base SQLite. Para las frases sobre hábitos y objetivos, crear antes los datos
de prueba correspondientes.

| Frase | Resultado esperado |
|---|---|
| ¿Qué tengo hoy? | Invoca el resumen del día. |
| Crea una reunión mañana a las cinco de la tarde durante una hora | Crea el evento con fecha, franja y duración expresas. |
| He bebido dos litros de agua hoy | Registra el progreso del hábito Agua si existe; si no, pide aclaración. |
| ¿Cuál es mi racha de agua hoy? | Consulta la racha del hábito Agua si existe. |
| Recuérdame llamar a mamá el jueves a las diez de la mañana | Programa un recordatorio en la fecha y hora resueltas. |
| Actualiza mi objetivo Leer 10 libros al 25% | Actualiza el objetivo si existe y es identificable. |
| Crea una reunión mañana a las cinco | Pregunta la franja horaria o la duración que falte; no las inventa. |
| Recuérdame llamar a mamá mañana | Pregunta la hora; no la inventa. |
| No crees el evento todavía | No crea ningún evento. |

Para cada modelo, registrar nombre/tag, hardware y configuración, resultado
esperado y observado, aclaraciones, tiempo de primera respuesta y de respuestas
calientes, y consumo aproximado. No comparar ejecuciones con datos iniciales
distintos.

## Cierre

Escribir `/salir` para cerrar. Revisar la base de prueba y conservarla si se
necesita analizar el resultado; no borrar datos durante la validación. Registrar
los resultados reales en el informe de integración antes de declarar funcional
el Bloque A.
