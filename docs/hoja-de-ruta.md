# Hoja de ruta

## Estado actual

Las fases 1–13 de la cadena de implementación están completas. El registro de
ramas, commits, validaciones, documentación y criterios está en
[`revision-fases.md`](./revision-fases.md).

La aplicación tiene dominio, esquemas, persistencia SQLite, seis servicios,
herramientas, motores LLM, agentes, composición y una interfaz de terminal.
El modelo LLM está apagado por defecto; el chatbot usa reglas deterministas
primero. NBA solo tiene una fuente falsa.

## Auditoría de Hugin

Hecha en `docs/auditoria-hugin.md`. No se porta código fuente completo; las
ideas de fechas, reglas deterministas y evaluación de frases se adaptaron en
fases separadas. Memoria/RAG, persistencia alternativa, avisos operativos,
copias, sincronización y canales empresariales quedan fuera del alcance actual.

## Lenguaje temporal

Hecho: `app/domain/lenguaje_fechas.py` resuelve fechas hacia delante, acepta
ayer y anteayer solo con `permitir_pasado=True`, y marca las horas sin franja
como no acotadas para que el agente pueda pedir aclaración.

## Herramientas por nombre

Hecho: hábitos, objetivos, eventos y recordatorios se pueden seleccionar por
UUID o por nombre/título exacto, sin distinguir mayúsculas ni tildes. Las
búsquedas se limitan al usuario y devuelven candidatos si no hay una única
coincidencia. También se pueden listar hábitos y recordatorios.

## Reglas y comprensión del agente

Hecho: el agente delega en herramientas para crear eventos y recordatorios,
registrar o consultar hábitos, actualizar objetivos y listar el día. Si falta
una fecha, una hora queda sin franja, la duración de un evento o un nombre no
es único, pregunta antes de ejecutar la operación. Las respuestas del motor se
validan contra el catálogo y su contexto incluye hasta cuatro turnos y la
pregunta pendiente.

## Banco de frases

El banco `tests/datos/frases.csv` contiene 100 frases etiquetadas, con 70 para
ajuste y 30 reservadas. La medición de reglas alcanza el 30,0 % de resultados
correctos en ambos conjuntos (21/70 y 9/30); la cobertura de respuestas es
48,6 % y 43,3 %, respectivamente. Un resultado correcto es la ejecución de la
herramienta etiquetada o, para `sin_intencion`, que no se active ninguna regla.
Las reglas no se ajustaron con el conjunto de reserva.

## Fases siguientes

### Bloque A — Chatbot funcional

| Fase | Objetivo | Criterio de terminado | Dependencias |
|---|---|---|---|
| A1. Integración | Integrar en una rama de entrega la cadena documentada de las fases 1–13. | Las fases quedan incorporadas en orden; `pytest -q`, importaciones y calidad pasan en un checkout limpio. | Fases 1–13 confirmadas. |
| A2. Comparación Ollama | Probar en la GTX 1060 `llama3.2:3b` frente a `qwen3:4b-instruct-2507` con las mismas frases y configuración. | Registrar para ambos modelos respuestas correctas, aclaraciones, latencia en frío/caliente y consumo; documentar el modelo elegido. No afirmar resultados antes de la ejecución real. | A1; Ollama y ambos modelos disponibles; habilitar selección explícita del modelo en el chatbot si hace falta. |
| A3. Validación funcional | Validar persistencia, delegación a servicios, reglas primero y fallback al modelo con pruebas manuales. | Reproducir la referencia de fase 12 (21/70 y 9/30 resultados correctos; 30,0 % en cada conjunto) y completar las frases manuales de [`prueba-real.md`](./prueba-real.md) sin inventar datos ni omitir aclaraciones necesarias. | A1 y A2. |

### Bloque B — Ampliaciones posteriores

| Fase | Objetivo | Criterio de terminado | Dependencias |
|---|---|---|---|
| B1. Avisos | Implementar un programador que envíe los recordatorios pendientes. | Un recordatorio debido se envía una sola vez, los errores quedan visibles y las pruebas usan un emisor falso. | A3; servicios y estados de recordatorios. |
| B2. Fuente NBA real | Añadir una implementación de `FuenteNBA` conectada a una fuente elegida. | Contrato cubierto con pruebas y errores de proveedor explícitos; la fuente falsa sigue disponible; credenciales fuera del repositorio. | A1; decisión de proveedor y acceso a sus datos. |
| B3. Panel visual | Crear una interfaz Streamlit con pestañas Chat, Hoy, Hábitos, Objetivos y Conversaciones. | Las pestañas delegan en servicios, conservan el aislamiento por usuario y no ofrecen botones para borrar datos. | A1; composición y servicios. |
| B4. Telegram | Exponer el asistente por Telegram sin duplicar lógica de negocio. | El adaptador pasa identidad y mensajes al router; pruebas con transporte falso y sin credenciales reales. | A3; política de identidad y configuración del bot. |
| B5. Aviso de cámara | Incorporar el aviso de la cámara como herramienta delegada. | La herramienta tiene esquema y permisos explícitos, notifica por un adaptador probado y no accede directamente a persistencia. | A1; definir evento, consentimiento y canal de aviso. |

## Puntos a revisar

1. `de_usuario` exige `usuario_id`; `Mensaje` y `RegistroHabito` no lo tienen.
2. `total_del_dia` y `racha_diaria` usan `valor` y `cumple`; el campo
   `completado` de `RegistroHabito` no interviene.
3. Los esquemas rechazan fechas sin zona; el dominio sigue aceptándolas si se
   crea el objeto a mano.
4. `Evento` solo valida al crearse; si se cambian las fechas después, no se
   revalida.
5. `racha_diaria` empieza en hoy o, si hoy aún no cumple, en ayer.
6. `actualizar_progreso` completa solo con 100 exacto.
7. `resumen_del_dia` solo considera hábitos de frecuencia diaria.
8. `historial_para_modelo` recorta con `limite` después de quitar mensajes
   vacíos.
