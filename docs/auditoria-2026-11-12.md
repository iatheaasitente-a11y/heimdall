# Auditoría del 12 de noviembre de 2026

## Alcance y base

La revisión inicial se hizo sobre `main` en `512fd645e991553827ac89f88f8ef3e81cba3851`,
con árbol limpio. Los hallazgos de Telegram se verificaron en
`feat/telegram` (`566e307a843e33027056b9344fd9c00ba34fe47`), pues esa rama no
forma parte de la base `main` revisada. Los 23 hallazgos corresponden al código
observado y quedan pendientes al inicio de las fases de corrección.

## Hallazgos

| # | Gravedad | Archivo | Problema verificado y evidencia | Corrección prevista | Estado |
|---:|---|---|---|---|---|
| 1 | Alta | `app/llm/planificador.py`, `app/llm/roles.py` | `_preparar_modelo` comparaba `configuracion.nombre` literalmente con los nombres de `/api/ps`; el catálogo solo recortaba espacios. | Canonicalización en `ModeloConfigurado` y comparaciones de `/api/ps` con `:latest` implícito; cubierto por tests de nombres etiquetados y sin etiqueta. | corregido (F1) |
| 2 | Alta | `app/agents/personal.py`, `app/tools/base.py` | Después de la respuesta LLM, el agente busca la herramienta y la ejecuta directamente. No hay paso de confirmación; herramientas de cancelación, reprogramación y cambio de estado pueden ejecutarse si el esquema y la confianza pasan. | Solicitar confirmación en la ruta LLM; mantener sin cambios las reglas deterministas. | pendiente |
| 3 | Alta | `app/tools/base.py`, `app/chatbot.py` | `Herramienta.ejecutar` captura solo `ErrorDeServicio` y `ValueError`; el chatbot no captura fallos inesperados del router/herramienta alrededor de la operación ni guarda la respuesta hasta terminar. `sqlite3.Error`, `OSError` o `TypeError` pueden interrumpir el ciclo. | Convertir fallos inesperados en errores observables y conservar el turno mediante manejo transaccional adecuado, sin ocultar errores. | pendiente |
| 4 | Alta | `app/agents/personal.py` | `_esperando` copia texto de la conversación a `{"role": "system", ...}`; ese contenido deriva de la pregunta anterior y puede incluir texto no confiable del usuario. | Pasar la aclaración como contexto no privilegiado, sin rol `system`. | pendiente |
| 5 | Media | `app/llm/planificador.py`, `app/llm/voz.py` | `_crear_motor` seleccionaba `MotorOllama` para VOZ. `MotorOllamaVoz.transcribir` solo valida y lanza `NotImplementedError`, por lo que no es una ruta de voz utilizable. | VOZ falla explícitamente con `MotorVozNoDisponible`; el esqueleto de transcripción declara que no es operativo y no hace solicitudes. Tests confirman que el planificador no llama a Ollama. | corregido (F1) |
| 6 | Media | `app/llm/vision.py` | `validar_imagen` hace `read_bytes()` antes de comprobar el límite. El planificador valida y luego el motor vuelve a validar, causando lecturas repetidas del mismo archivo. | Comprobar tamaño antes de leer y pasar los bytes ya validados a la inferencia para evitar lecturas duplicadas. | pendiente |
| 7 | Media | `app/database/schema.sql` | Hay claves foráneas con `ON DELETE CASCADE`, incluidos mensajes; no existen triggers que rechacen `UPDATE` o `DELETE` de mensajes. | Añadir triggers que impidan modificar o borrar mensajes. No cambiar cascadas; documentarlas como decisión pendiente. | pendiente |
| 8 | Media | `app/database/esquema.py`, `app/database/schema.sql` | La instalación ejecuta `CREATE ... IF NOT EXISTS`; no hay tabla/pragma de versión ni migraciones aplicables. | Añadir un sistema mínimo de `schema_version` con migraciones secuenciales. | pendiente |
| 9 | Media-baja | `app/llm/configuracion.py` | Con `HEIMDALL_LLM=ollama` y sin `HEIMDALL_MODELO_TEXTO`, `crear_motor` retorna `None` sin señal de configuración incompleta. | Lanzar un error de configuración explícito en ese caso. | pendiente |
| 10 | Media-baja | `app/database/connection.py` | `crear_conexion` configura claves foráneas y `busy_timeout`, pero no habilita WAL. | Habilitar WAL para bases en archivo; no forzar ese modo en `:memory:`. | pendiente |
| 11 | Baja-media | `app/llm/ollama.py` | El constructor solo comprueba que la ruta termine en `/api/chat`; no limita esquema ni host a HTTP(S) local. | Aceptar únicamente `http`/`https` y host local, rechazando destinos remotos. | pendiente |
| 12 | Baja-media | `app/tools/esquemas.py` | Los textos visibles como títulos, nombres, descripciones y mensajes no declaran límites máximos; los campos `float` usan cotas, pero no `allow_inf_nan=False`. | Declarar longitudes máximas razonables y rechazar NaN/infinito en valores numéricos. | pendiente |
| 13 | Baja | `.env.example`, `.gitignore` | `.env.example` está vacío. `.gitignore` ignora `.env`, pero no patrones `.env.*`, logs, audio WAV/OGA ni `tmp/`. | Documentar solo nombres de variables sin secretos y ampliar exclusiones solicitadas. | pendiente |
| 14 | Baja | `.github/workflows/ci.yml`, `requirements.txt` | El workflow no declara `permissions: contents: read`; `pytest` está en el manifiesto común de dependencias junto con producción. | Limitar permisos de CI y separar dependencias de prueba sin añadir paquetes. | pendiente |
| 15 | Baja | `scripts/registrar.ps1` | La fila Markdown concatena valores sin escapar `|`. Si no encuentra la fila separadora, `FindIndex` devuelve `-1` y el cálculo inserta en índice `0`. | Escapar separadores y detenerse con error explícito si falta la cabecera. | pendiente |
| 16 | Baja | `app/llm/vision.py` | `_dimensiones_jpeg` exige que el archivo termine exactamente en `FFD9`; por ello rechaza JPEG válidos con bytes posteriores al marcador EOI. | Admitir bytes posteriores a EOI sin relajar la validación del encabezado y dimensiones. | pendiente |
| 17 | Información | `app/llm/planificador.py`, `app/chatbot.py`, `app/composicion.py` | Existe `crear_planificador`, pero `crear_motor` retorna `MotorOllama` y el chatbot llama directamente a ese motor; el planificador multimodelo no participa en el flujo del chatbot. | Documentar la desconexión y su alcance; no integrarla en estas fases. | pendiente |
| 18 | Alta | `app/telegram/conector.py` (rama `feat/telegram`) | El conector procesa y guarda mensajes con servicios, pero no llama a `commit`. En el uso con `sesion_sqlite`, el commit ocurre al salir del bloque, no por actualización. | Confirmar cada actualización procesada en su propia transacción, sin perder errores de almacenamiento. | pendiente |
| 19 | Alta | `app/telegram/` (rama `feat/telegram`) | No hay punto de arranque/configuración que conecte el conector y no existe un origen definido para el mapa `chat_id → usuario_id`. | **No implementar.** Falta que el usuario defina el punto de arranque y el origen/política del mapeo antes de exponer el canal. | pendiente |
| 20 | Media | `app/telegram/conector.py` (rama `feat/telegram`) | `obtener_actualizaciones` avanza `_offset` por todo el lote antes de que `ejecutar` procese sus elementos; un fallo intermedio puede saltar actualizaciones aún no tratadas. | Avanzar y confirmar el offset después de cada actualización procesada correctamente. | pendiente |
| 21 | Media | `app/telegram/conector.py` (rama `feat/telegram`) | `ejecutar` no captura errores por actualización; cualquier fallo de transporte o procesamiento termina el bucle. | Registrar errores sin datos sensibles, capturar por actualización y continuar tras una pausa. | pendiente |
| 22 | Media-baja | `app/telegram/conector.py` (rama `feat/telegram`) | La respuesta se envía como `json.dumps(resultado)` y expone la estructura interna, incluidos UUID y campos de herramientas. | Añadir un formateador de salida que no revele identificadores internos. | pendiente |
| 23 | Baja | `app/telegram/conector.py` (rama `feat/telegram`) | La autorización compara solo `message.chat.id`; no comprueba `from.id` ni que el chat sea privado. | Validar autor y tipo de chat, o limitar explícitamente el conector a chats privados. | pendiente |

El hallazgo 19 es un límite obligatorio de parada para la fase Telegram: se
documentará lo que falta y no se implementará ni inferirá una política de
identidad o activación.
